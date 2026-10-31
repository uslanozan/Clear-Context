"""Bounded assessment of saved evidence; follow-up research is orchestrated by callers."""

import asyncio
import json
import time
from dataclasses import dataclass
from time import perf_counter

from clear_context.providers.meta_judgment import build_judgment_request
from clear_context.providers.meta_structured import ModelResponseFailure
from clear_context.repositories.retrieval import encode, identity
from clear_context.schemas.component_judgment import (
    COMPONENT_CONTRACTS,
    AnchoredComponentAssessment,
    AnchoredComponentResponse,
    ComponentAssessment,
    ComponentResponse,
    parent_claim,
    validate_components,
)
from clear_context.schemas.evidence_judgment import (
    JudgmentResponse,
    NeedAssessment,
    evidence_aliases,
    need_status,
    resolved_citations,
    response_model,
    validate_judgment,
)
from clear_context.services.report_text import report_text


@dataclass(frozen=True)
class JudgmentJob:
    case_id: str
    need_ids: tuple[str, ...]
    selection_ids: tuple[str, ...]


class EvidenceJudgmentService:
    def __init__(
        self,
        repository,
        provider,
        method,
        limits,
        system,
        model,
        clock=time.time,
        response_contract="legacy_v1",
    ):
        self.repository, self.provider = repository, provider
        self.method, self.limits, self.system, self.model = method, limits, system, model
        self.clock = clock
        self.response_contract = response_contract
        self.calls = self.active = self.max_active = 0
        self.halted = False

    def prepare(self, job: JudgmentJob):
        packet = self.repository.packet(job.case_id, job.need_ids, job.selection_ids)
        request = build_judgment_request(
            self.system,
            packet,
            self.model.api_model_id,
            self.limits.effort,
            self.limits.max_completion_tokens,
            self.response_contract,
        )
        if len(request["messages"][1]["content"]) > self.limits.max_input_chars:
            raise ValueError("Judgment input exceeds its size budget; no silent truncation.")
        key = identity("judge_", encode(request))
        return packet, request, key

    async def assess(self, jobs: list[JudgmentJob]):
        # Fail all invalid associations before a paid request is possible.
        prepared = [(job, *self.prepare(job)) for job in jobs]
        semaphore = asyncio.Semaphore(self.limits.max_concurrency)

        async def process(job, packet, request, key):
            row = {
                "case_id": job.case_id,
                "need_ids": list(job.need_ids),
                "request_key": key,
                "cached": False,
                "scope": "provided_evidence_only",
                "source_reliability_assessed": False,
            }
            async with semaphore:
                started = perf_counter()
                usage = {}
                content = None
                try:
                    if not packet.evidence:
                        if self.response_contract == "components_v3":
                            output = AnchoredComponentResponse(
                                components=[
                                    AnchoredComponentAssessment(
                                        description=packet.needs[0].description,
                                        status="insufficient",
                                        explanation=report_text(
                                            "no_evidence", parent_claim(packet)
                                        ),
                                        evidence=[],
                                        claim_quote=parent_claim(packet),
                                    )
                                ]
                            )
                        elif self.response_contract == "components_v2":
                            output = ComponentResponse(
                                components=[
                                    ComponentAssessment(
                                        description=packet.needs[0].description,
                                        status="insufficient",
                                        explanation=report_text(
                                            "no_evidence", parent_claim(packet)
                                        ),
                                        evidence=[],
                                    )
                                ]
                            )
                        else:
                            output = JudgmentResponse(
                                assessments=[
                                    NeedAssessment(
                                        need_id=n.id,
                                        evidence_assessments=[],
                                        missing_information=[n.description],
                                        explanation="No selected evidence available.",
                                    )
                                    for n in packet.needs
                                ]
                            )
                        if self.response_contract in {
                            "reconciled_v1_1",
                            "compact_v1_2",
                            "relevance_v1",
                        }:
                            value = output.model_dump()
                            for assessment in value["assessments"]:
                                assessment.update(
                                    coverage_summary={
                                        "coverage": "none",
                                        "evidence_ids": [],
                                        "explanation": "No selected evidence.",
                                    },
                                    time_basis={
                                        "mode": "unresolved",
                                        "evidence_ids": [],
                                        "explanation": "No evidence to ground temporal context.",
                                    },
                                )
                            if self.response_contract == "relevance_v1":
                                for assessment in value["assessments"]:
                                    assessment.update(
                                        scope_note="No evidence to assess scope.",
                                        conflict_type="none",
                                    )
                            output = response_model(
                                "relevance_v1"
                                if self.response_contract == "relevance_v1"
                                else "reconciled_v1_1"
                            ).model_validate(value)
                        at = self.clock()
                    else:
                        research = self.repository.research
                        cached = research.cached("judgment", key, self.clock())
                        if cached:
                            body = json.loads(cached["payload"])
                            at = cached["fetched_at"]
                            row["cached"] = True
                        else:
                            if self.halted:
                                return row | {"status": "not_run_after_failure"}
                            if self.calls >= self.limits.max_model_calls:
                                return row | {"status": "call_budget_exhausted"}
                            self.calls += 1
                            self.active += 1
                            self.max_active = max(self.max_active, self.active)
                            research.log(
                                "judgment_started",
                                self.clock(),
                                case_id=job.case_id,
                                key=key,
                                request=request,
                                active=self.active,
                            )
                            try:
                                body = await self.provider.complete(
                                    request, self.limits.timeout_seconds
                                )
                            finally:
                                self.active -= 1
                            at = self.clock()
                        usage = body.get("usage") or {}
                        content = body["choices"][0]["message"]["content"]
                        if self.response_contract in COMPONENT_CONTRACTS:
                            output, component_citations = validate_components(
                                content,
                                packet,
                                self.response_contract,
                            )
                        else:
                            output = validate_judgment(
                                body["choices"][0]["message"]["content"],
                                packet,
                                self.response_contract,
                            )
                        if not row["cached"]:
                            research.save_cache(
                                "judgment", key, body, at, self.limits.cache_ttl_seconds
                            )
                    if self.response_contract in COMPONENT_CONTRACTS:
                        result = {
                            "scope": "provided_evidence_only",
                            "source_reliability_assessed": False,
                            "need_id": packet.needs[0].id,
                            "claim_id": packet.needs[0].claim_id,
                            "components": output.model_dump()["components"],
                            "citations": component_citations if packet.evidence else [],
                            "evidence_aliases": evidence_aliases(packet),
                            "claim_verdicts": None,
                        }
                    else:
                        result = {
                            "scope": "provided_evidence_only",
                            "source_reliability_assessed": False,
                            "assessments": [
                                a.model_dump()
                                | {
                                    "status": need_status(a),
                                    "source_count": len(
                                        {
                                            e.source_id
                                            for e in packet.evidence
                                            if e.need_id == a.need_id
                                        }
                                    ),
                                }
                                for a in output.assessments
                            ],
                            "citations": resolved_citations(output, packet),
                            "claim_verdicts": None,
                        }
                    if self.response_contract in {"compact_v1_2", "relevance_v1"}:
                        result["evidence_aliases"] = evidence_aliases(packet)
                    receipt = self.repository.save(
                        packet, self.method, self.model.api_model_id, key, result, usage, at
                    )
                    row.update(status="assessed", judgment_id=receipt, result=result, usage=usage)
                    self.repository.research.log(
                        "judgment_completed",
                        self.clock(),
                        judgment_id=receipt,
                        cached=row["cached"],
                    )
                except (ModelResponseFailure, ValueError, KeyError, IndexError, TypeError) as error:
                    # Provider failures stop further calls; one malformed answer affects only
                    # its own need.
                    self.halted = self.halted or isinstance(error, ModelResponseFailure)
                    if isinstance(error, ModelResponseFailure):
                        usage = error.usage or usage
                        if error.finish_reason:
                            row["finish_reason"] = error.finish_reason
                    row.update(
                        status=error.code
                        if isinstance(error, ModelResponseFailure)
                        else "invalid_judgment",
                        usage=usage,
                    )
                    # Keep the validation reason and raw answer for QA; they hold no credentials.
                    self.repository.research.log(
                        "judgment_failed",
                        self.clock(),
                        case_id=job.case_id,
                        status=row["status"],
                        reason=str(error)[:500],
                        raw_content=content[:20000] if isinstance(content, str) else None,
                    )
                row["elapsed_seconds"] = round(perf_counter() - started, 3)
                return row

        return await asyncio.gather(*(process(*item) for item in prepared))
