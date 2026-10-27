import json
from collections import deque
from time import monotonic
from typing import Literal
from uuid import UUID, uuid4

import httpx
from pydantic import Field, ValidationError

from clear_context.core.prompts import RenderedPrompt, load_claim_extraction_prompt
from clear_context.core.settings import ModelSelection, Settings
from clear_context.domain.investigation import (
    Assessment,
    Claim,
    ClaimExtraction,
    ExtractionChunk,
    ExtractionCoverage,
    Finding,
    InvestigationReport,
    ModelUsage,
    Record,
)
from clear_context.providers.errors import ProviderError
from clear_context.services.text_chunks import (
    TextChunk,
    bisect,
    context_ranges,
    locate_quote,
    partition,
    visible_ranges,
)

META_COMPLETIONS_URL = "https://api.meta.ai/v1/chat/completions"


class ExtractedClaims(Record):
    claims: list[str] = Field(min_length=1, max_length=12)


class ExtractedClaim(Record):
    quote: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    context_quotes: list[str] = Field(max_length=3)
    context_status: Literal["standalone", "context_linked", "ambiguous"]


class ChunkClaims(Record):
    claims: list[ExtractedClaim] = Field(max_length=64)
    has_more: bool


class MetaInvestigationProvider:
    def __init__(
        self,
        settings: Settings,
        model: ModelSelection,
        transport: httpx.BaseTransport | None = None,
        *,
        prompt: RenderedPrompt | None = None,
    ):
        if (
            settings.app_mode != "meta"
            or not settings.allow_paid_api_calls
            or not settings.meta_api_key.get_secret_value().strip()
        ):
            raise ValueError("Meta mode requires paid-call opt-in and a non-empty API key.")
        self.settings = settings
        self.model = model
        self.transport = transport
        self.prompt = prompt or load_claim_extraction_prompt(settings)

    def extract_claims(self, text: str) -> ClaimExtraction:
        if self.prompt.version == "v1":
            return self._extract_legacy(text)
        return self._extract_document(text)

    def _request(
        self,
        text: str,
        schema: dict,
        maximum_tokens: int,
        timeout: float,
        chunk: TextChunk | None = None,
    ) -> tuple[str, ModelUsage]:
        capacity = (
            self.settings.meta_max_claims
            if self.prompt.version == "v1"
            else self.settings.extraction_response_capacity
        )
        schema["properties"]["claims"]["maxItems"] = capacity
        payload = {
            "model": self.model.api_model_id,
            "messages": [
                {
                    "role": "system",
                    "content": self.prompt.system,
                },
                {"role": "user", "content": text},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "extracted_claims",
                    "strict": True,
                    "schema": schema,
                },
            },
            "max_completion_tokens": maximum_tokens,
            "reasoning_effort": "low",
            "store": False,
            "stream": False,
        }
        try:
            with httpx.Client(
                timeout=timeout,
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                response = client.post(
                    META_COMPLETIONS_URL,
                    json=payload,
                    headers={
                        "Authorization": "Bearer " + self.settings.meta_api_key.get_secret_value()
                    },
                )
        except httpx.TimeoutException:
            raise ProviderError("meta_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("meta_connection_failed") from None
        if response.status_code != 200:
            codes = {
                401: "meta_authentication_failed",
                403: "meta_access_denied",
                429: "meta_rate_limited",
            }
            code = codes.get(response.status_code, "meta_request_failed")
            raise ProviderError(code) from None
        receipt = None
        try:
            body = response.json()
            usage = body.get("usage") or {}
            details = usage.get("prompt_tokens_details") or {}
            receipt = ModelUsage(
                task="claim_extraction",
                model_id=self.model.api_model_id,
                prompt_version=self.prompt.version,
                prompt_sha256=self.prompt.sha256,
                input_tokens=usage.get("prompt_tokens"),
                output_tokens=usage.get("completion_tokens"),
                cached_input_tokens=details.get("cached_tokens"),
                chunk_start=chunk.start if chunk else None,
                chunk_end=chunk.end if chunk else None,
            )
            if len(body["choices"]) != 1:
                raise ValueError("Expected one completion.")
            choice = body["choices"][0]
            message = choice["message"]
            if choice["finish_reason"] != "stop":
                receipt.outcome = "truncated"
                raise ProviderError("meta_incomplete_output", receipt)
            if message.get("refusal"):
                receipt.outcome = "invalid"
                raise ProviderError("meta_refused", receipt)
            if message.get("tool_calls") or not isinstance(message["content"], str):
                raise ValueError("Expected text content without tool calls.")
            return message["content"], receipt
        except ProviderError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, ValidationError):
            if receipt:
                receipt.outcome = "invalid"
            raise ProviderError("meta_invalid_response", receipt) from None

    def _extract_legacy(self, text: str) -> ClaimExtraction:
        content, receipt = self._request(
            text,
            ExtractedClaims.model_json_schema(),
            self.settings.meta_max_completion_tokens,
            self.settings.meta_timeout_seconds,
        )
        try:
            extracted = ExtractedClaims.model_validate_json(content)
            if len(extracted.claims) > self.settings.meta_max_claims:
                raise ValueError("Too many claims.")
            if len(set(extracted.claims)) != len(extracted.claims):
                raise ValueError("Duplicate claims.")
            if any(not claim.strip() or claim not in text for claim in extracted.claims):
                raise ProviderError("meta_ungrounded_claim")
        except ProviderError:
            raise
        except (ValueError, TypeError, KeyError, IndexError, AttributeError, ValidationError):
            raise ProviderError("meta_invalid_response") from None
        return ClaimExtraction(
            claims=[Claim(id=uuid4(), text=claim) for claim in extracted.claims],
            model_usage=[receipt],
        )

    def _extract_document(self, text: str) -> ClaimExtraction:
        settings = self.settings
        queue = deque((item, []) for item in partition(text, settings.extraction_chunk_characters))
        claims, usage, chunks, notes = [], [], [], []
        deadline = monotonic() + settings.extraction_max_seconds
        reserved_tokens = 0
        calls = 0
        while queue:
            chunk, fallback = queue.popleft()
            remaining = settings.extraction_max_output_tokens - reserved_tokens
            time_left = deadline - monotonic()
            if calls >= settings.extraction_max_calls or remaining < 128 or time_left <= 0:
                for pending, previous in [(chunk, fallback), *queue]:
                    chunks.append(
                        ExtractionChunk(
                            start=pending.start,
                            end=pending.end,
                            status="partial",
                            reason="budget_exhausted",
                        )
                    )
                    claims.extend(previous)
                notes.append("Extraction budget ended before all target ranges were processed.")
                break
            context = context_ranges(text, chunk, settings.extraction_context_characters)
            user_input = json.dumps(
                {
                    "target": text[chunk.start : chunk.end],
                    "context": [text[item.start : item.end] for item in context],
                },
                ensure_ascii=False,
            )
            maximum_tokens = min(settings.meta_max_completion_tokens, remaining)
            calls += 1
            reserved_tokens += maximum_tokens
            extracted_claims, saturated = [], False
            usage_before = len(usage)
            reason = None
            try:
                content, receipt = self._request(
                    user_input,
                    ChunkClaims.model_json_schema(),
                    maximum_tokens,
                    min(settings.meta_timeout_seconds, time_left),
                    chunk,
                )
                usage.append(receipt)
                response = ChunkClaims.model_validate_json(content)
                if len(response.claims) > settings.extraction_response_capacity:
                    raise ValueError("Too many claims for one response.")
                for item in response.claims:
                    span = locate_quote(
                        text, item.quote, visible_ranges([chunk, *context]), overlaps=chunk
                    )
                    context_spans = [
                        locate_quote(text, quote, [chunk, *context])
                        for quote in item.context_quotes
                    ]
                    if item.context_status == "context_linked" and not context_spans:
                        raise ValueError("Resolved context needs a source quote.")
                    repeated = text.find(item.quote, span.start + 1, chunk.end) >= 0
                    extracted_claims.append(
                        Claim(
                            id=uuid4(),
                            text=item.quote,
                            statement=item.statement,
                            source_span=span,
                            context_spans=context_spans,
                            context_status="ambiguous" if repeated else item.context_status,
                        )
                    )
                saturated = (
                    response.has_more
                    or len(response.claims) >= settings.extraction_response_capacity
                )
                receipt.outcome = "capacity_reached" if saturated else "accepted"
                reason = "response_capacity" if saturated else None
            except ProviderError as error:
                if error.usage is not None:
                    usage.append(error.usage)
                reason = error.code
                saturated = error.code == "meta_incomplete_output"
            except (ValueError, TypeError, ValidationError):
                if usage:
                    usage[-1].outcome = "invalid"
                extracted_claims = []
                reason = "invalid_chunk_output"
            if len(usage) > usage_before and usage[-1].output_tokens is not None:
                reserved_tokens -= maximum_tokens - min(maximum_tokens, usage[-1].output_tokens)
            if (
                saturated
                and chunk.end - chunk.start > settings.extraction_min_chunk_characters * 2
                and calls < settings.extraction_max_calls
            ):
                left, right = bisect(text, chunk)
                chunks.append(
                    ExtractionChunk(start=chunk.start, end=chunk.end, status="split", reason=reason)
                )
                for child in (right, left):
                    inherited = [
                        claim
                        for claim in extracted_claims
                        if claim.source_span and child.start <= claim.source_span.start < child.end
                    ]
                    queue.appendleft((child, inherited))
                continue
            chunks.append(
                ExtractionChunk(
                    start=chunk.start,
                    end=chunk.end,
                    status="partial" if reason else "processed",
                    reason=reason,
                )
            )
            claims.extend(extracted_claims or fallback)
            if reason in {
                "meta_authentication_failed",
                "meta_access_denied",
                "meta_rate_limited",
                "meta_connection_failed",
                "meta_timeout",
                "meta_request_failed",
            }:
                for pending, previous in queue:
                    chunks.append(
                        ExtractionChunk(
                            start=pending.start, end=pending.end, status="partial", reason=reason
                        )
                    )
                    claims.extend(previous)
                break
        unique = {}
        for claim in claims:
            key = (claim.source_span.start, claim.source_span.end, claim.statement)
            unique.setdefault(key, claim)
        partial = any(chunk.status == "partial" for chunk in chunks)
        return ClaimExtraction(
            claims=sorted(unique.values(), key=lambda claim: claim.source_span.start),
            model_usage=usage,
            coverage=ExtractionCoverage(
                status="partial" if partial else "processed",
                model_calls=calls,
                chunks=chunks,
                notes=[
                    "Processed ranges do not prove exhaustive semantic claim coverage.",
                    "Statements are model interpretations; source spans are literal quotes.",
                    *notes,
                ],
            ),
        )

    def evaluate_evidence(self, investigation_id: UUID, claims: list[Claim]) -> InvestigationReport:
        return InvestigationReport(
            investigation_id=investigation_id,
            mode="meta",
            claims=claims,
            sources=[],
            evidence=[],
            findings=[
                Finding(
                    id=uuid4(),
                    claim_id=claim.id,
                    assessment=Assessment.UNRESOLVED,
                    explanation="No external evidence was retrieved; the claim is not verified.",
                )
                for claim in claims
            ],
            limitations=[
                "Meta extracted claims; source retrieval and evidence assessment are pending.",
                "Claim extraction does not establish truth or image context.",
            ],
        )
