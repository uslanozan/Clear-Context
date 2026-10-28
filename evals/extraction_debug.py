"""Replay extraction responses and capture bounded, inspectable API traces."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ClaimAttributes(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    statement: str = Field(min_length=1)
    group: str = Field(min_length=1)


class ExtractedClaim(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    claim: str = Field(min_length=1)
    claim_attributes: ClaimAttributes


class ExtractionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    extractions: list[ExtractedClaim]


def fingerprint(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return sha256(encoded).hexdigest()


def reject_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def canonical_text(text: str, *, punctuation: bool = False):
    characters, positions = [], []
    for index, character in enumerate(text):
        if character == "\u200b":
            continue
        if punctuation:
            character = {"’": "'", "‘": "'"}.get(character, character)
        characters.append(character)
        positions.append(index)
    return "".join(characters), positions


def quote_diagnostic(quote: str, source: str) -> dict:
    start = source.find(quote)
    if start >= 0:
        return {
            "classification": "exact",
            "exact": True,
            "source_span": {"start": start, "end": start + len(quote)},
        }
    for punctuation in (False, True):
        target, _ = canonical_text(quote, punctuation=punctuation)
        haystack, positions = canonical_text(source, punctuation=punctuation)
        if not target:
            continue
        matches = []
        cursor = 0
        while (found := haystack.find(target, cursor)) >= 0:
            matches.append(found)
            cursor = found + 1
        if not matches:
            continue
        classification = (
            "invisible_or_apostrophe_difference"
            if punctuation
            else "invisible_character_difference"
        )
        result = {
            "classification": classification,
            "exact": False,
            "candidate_count": len(matches),
            "diagnostic_only": True,
        }
        if len(matches) == 1:
            start = positions[matches[0]]
            end = positions[matches[0] + len(target) - 1] + 1
            candidate = source[start:end]
            result.update(
                candidate_span={"start": start, "end": end},
                original_source_candidate=candidate,
                quote_invisible_count=quote.count("\u200b"),
                source_candidate_invisible_count=candidate.count("\u200b"),
            )
        return result
    return {
        "classification": "unmatched_source_quote",
        "exact": False,
        "diagnostic_only": True,
    }


class Trace:
    """Persist ordered stages; credentials and request headers are never archived."""

    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=False)
        self.directory = directory
        self.sequence = 0

    def event(self, stage: str, **details):
        self.sequence += 1
        record = {
            "sequence": self.sequence,
            "at": datetime.now(UTC).isoformat(),
            "stage": stage,
            **details,
        }
        with (self.directory / "events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()

    def artifact(self, name: str, value: Any):
        (self.directory / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )


def inspect_content(content: str, source: str, trace: Trace | None = None) -> dict:
    emit = trace.event if trace else lambda *args, **kwargs: None
    emit(
        "content_received",
        content_sha256=sha256(content.encode("utf-8")).hexdigest(),
        characters=len(content),
    )
    try:
        decoded = json.loads(content, object_pairs_hook=reject_duplicate_keys)
        emit("json_decoded", status="passed")
    except (ValueError, TypeError):
        emit("json_decoded", status="failed")
        return {
            "json_valid": False,
            "schema_valid": False,
            "outcome": "invalid_json",
            "claims": [],
            "semantic_qa": "not_evaluated",
        }
    try:
        parsed = ExtractionResponse.model_validate(decoded)
        emit("schema_validated", status="passed", claim_count=len(parsed.extractions))
    except ValidationError as error:
        emit(
            "schema_validated",
            status="failed",
            errors=[
                {"location": list(e["loc"]), "type": e["type"]}
                for e in error.errors(include_input=False)
            ],
        )
        return {
            "json_valid": True,
            "schema_valid": False,
            "outcome": "invalid_schema",
            "claims": [],
            "semantic_qa": "not_evaluated",
        }
    claims = []
    for index, claim in enumerate(parsed.extractions, 1):
        diagnostic = quote_diagnostic(claim.claim, source)
        record = {
            "number": index,
            "quote": claim.claim,
            "statement": claim.claim_attributes.statement,
            "group": claim.claim_attributes.group,
            **diagnostic,
        }
        claims.append(record)
        emit("quote_checked", claim_number=index, **diagnostic)
    outcome = (
        "empty_extraction"
        if not claims
        else "exact_quotes"
        if all(c["exact"] for c in claims)
        else "literal_mismatch"
    )
    emit("inspection_completed", outcome=outcome, semantic_qa="not_evaluated")
    return {
        "json_valid": True,
        "schema_valid": True,
        "outcome": outcome,
        "claims": claims,
        "quote_classifications": dict(Counter(c["classification"] for c in claims)),
        "semantic_qa": "not_evaluated",
    }


class CaptureTransport(httpx.BaseTransport):
    """Record exact outgoing JSON and incoming bytes for one explicit API call."""

    def __init__(self, trace: Trace, expected_source: str, expected_effort: str):
        self.trace = trace
        self.expected_source = expected_source
        self.expected_effort = expected_effort
        self.inner = httpx.HTTPTransport(retries=0)
        self.calls = 0
        self.response_body = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        if self.calls:
            raise RuntimeError("One-call transport budget reached")
        if str(request.url) != "https://api.meta.ai/v1/chat/completions":
            raise ValueError("Unexpected API destination")
        payload = json.loads(request.content)
        if (
            payload.get("model") != "muse-spark-1.3"
            or payload.get("reasoning_effort") != self.expected_effort
        ):
            raise ValueError("Model or effort differs from the planned condition")
        messages = payload.get("messages", [])
        source_present = any(
            self.expected_source in (message.get("content") or "")
            for message in messages
        )
        # D embeds source text inside JSON; verify the decoded field as well.
        for message in messages:
            if message.get("role") != "user":
                continue
            try:
                nested = json.loads(message.get("content") or "")
                source_present |= (
                    isinstance(nested, dict)
                    and nested.get("source") == self.expected_source
                )
            except (ValueError, TypeError):
                pass
        if not source_present:
            raise ValueError("Complete expected source absent from request")
        self.trace.artifact("request.json", payload)
        self.trace.event(
            "request_verified",
            request_sha256=fingerprint(payload),
            model=payload["model"],
            effort=payload["reasoning_effort"],
            full_source_present=True,
            output_limit=payload.get(
                "max_completion_tokens", payload.get("max_tokens")
            ),
        )
        self.calls += 1
        start = perf_counter()
        self.trace.event("http_started", attempt=self.calls)
        try:
            response = self.inner.handle_request(request)
            response.read()
        except httpx.HTTPError as error:
            self.trace.event("http_failed", error_type=type(error).__name__)
            raise
        (self.trace.directory / "response-body.txt").write_bytes(response.content)
        self.trace.event(
            "http_completed",
            status_code=response.status_code,
            elapsed_seconds=round(perf_counter() - start, 3),
            response_sha256=sha256(response.content).hexdigest(),
            headers={
                key: response.headers[key]
                for key in ("date", "content-type", "x-request-id", "request-id")
                if key in response.headers
            },
        )
        try:
            self.response_body = response.json()
            self.trace.artifact("response.json", self.response_body)
        except ValueError:
            self.trace.event("response_envelope_invalid")
        return response

    def close(self):
        self.inner.close()
