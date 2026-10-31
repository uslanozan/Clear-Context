"""Evidence-relative need assessments with literal citations, never global truth labels."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from clear_context.schemas.retrieval import ClaimReference, ResearchNeed
from clear_context.schemas.source_time import PublicationContext

EvidenceRelation = Literal["supports", "contradicts", "insufficient"]
EvidenceCoverage = Literal["complete", "partial", "none"]
NeedStatus = Literal["supported", "contradicted", "mixed", "insufficient"]
EvidenceRelevance = Literal["relevant", "irrelevant", "uncertain"]
EvidenceBasis = Literal["direct", "inference", "none"]
ConflictType = Literal["none", "same_component", "different_components", "unclear"]
JudgmentExecutionStatus = Literal[
    "assessed",
    "invalid_judgment",
    "invalid_model_response",
    "model_output_truncated",
    "transport_error",
    "rate_limited",
    "model_request_failed",
    "not_run_after_failure",
    "call_budget_exhausted",
    "live_judging_disabled",
]


class EvidenceContext(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    id: str
    need_id: str
    selection_id: str
    paragraph_id: str
    page_id: str
    source_id: str
    source_url: str
    fetched_at: float
    reported_publication_dates: list[str]
    publication_context: PublicationContext = Field(default_factory=PublicationContext)
    # Set when reverse image search found this page for the user's image or video.
    media_relation: Literal["same_image", "similar_image", "fact_check"] | None = None
    selected_start: int
    selected_end: int
    start: int
    end: int
    quote: str
    before_truncated: bool
    after_truncated: bool


class JudgmentPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str
    selection_ids: list[str]
    claims: list[ClaimReference]
    needs: list[ResearchNeed]
    evidence: list[EvidenceContext]
    source_reliability_assessed: Literal[False] = False


class SourceExcerpt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    quote: str = Field(min_length=1, max_length=3000)


class EvidenceAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    evidence_id: str
    relation: EvidenceRelation
    coverage: EvidenceCoverage
    explanation: str = Field(min_length=1, max_length=600)
    excerpts: list[SourceExcerpt] = Field(max_length=5)


class NeedAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    need_id: str
    evidence_assessments: list[EvidenceAssessment]
    missing_information: list[str] = Field(max_length=10)
    explanation: str = Field(min_length=1, max_length=600)


class JudgmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessments: list[NeedAssessment]


class CoverageSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    coverage: EvidenceCoverage
    evidence_ids: list[str]
    explanation: str = Field(min_length=1, max_length=600)


class TemporalBasis(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mode: Literal["not_required", "explicit_source_text", "publication_context", "unresolved"]
    evidence_ids: list[str]
    explanation: str = Field(min_length=1, max_length=600)


class ReconciledNeedAssessment(NeedAssessment):
    coverage_summary: CoverageSummary
    time_basis: TemporalBasis


class ReconciledJudgmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessments: list[ReconciledNeedAssessment]


class CompactExcerpt(SourceExcerpt):
    quote: str = Field(min_length=1, max_length=400)


class CompactEvidenceAssessment(EvidenceAssessment):
    explanation: str = Field(min_length=1, max_length=240)
    excerpts: list[CompactExcerpt] = Field(max_length=2)


class CompactCoverageSummary(CoverageSummary):
    explanation: str = Field(min_length=1, max_length=240)


class CompactTemporalBasis(TemporalBasis):
    explanation: str = Field(min_length=1, max_length=240)


class CompactNeedAssessment(ReconciledNeedAssessment):
    evidence_assessments: list[CompactEvidenceAssessment]
    coverage_summary: CompactCoverageSummary
    time_basis: CompactTemporalBasis
    explanation: str = Field(min_length=1, max_length=240)
    missing_information: list[str] = Field(max_length=10)


class CompactJudgmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessments: list[CompactNeedAssessment]


class RelevanceEvidenceAssessment(CompactEvidenceAssessment):
    relevance: EvidenceRelevance
    basis: EvidenceBasis


class RelevanceNeedAssessment(ReconciledNeedAssessment):
    evidence_assessments: list[RelevanceEvidenceAssessment]
    coverage_summary: CompactCoverageSummary
    time_basis: CompactTemporalBasis
    explanation: str = Field(min_length=1, max_length=240)
    scope_note: str = Field(min_length=1, max_length=240)
    conflict_type: ConflictType


class RelevanceJudgmentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    assessments: list[RelevanceNeedAssessment]


def evidence_aliases(packet: JudgmentPacket) -> dict[str, str]:
    """Map request-local aliases to immutable evidence identities."""
    return {f"E{i}": evidence.id for i, evidence in enumerate(packet.evidence, 1)}


def response_model(contract: str):
    if contract == "legacy_v1":
        return JudgmentResponse
    if contract == "reconciled_v1_1":
        return ReconciledJudgmentResponse
    if contract == "compact_v1_2":
        return CompactJudgmentResponse
    if contract == "relevance_v1":
        return RelevanceJudgmentResponse
    raise ValueError("Unknown judgment response contract.")


def need_status(assessment: NeedAssessment) -> NeedStatus:
    positive = [e for e in assessment.evidence_assessments if e.relation == "supports"]
    negative = [e for e in assessment.evidence_assessments if e.relation == "contradicts"]
    if positive and negative:
        return "mixed"
    if isinstance(assessment, ReconciledNeedAssessment):
        complete = (
            assessment.coverage_summary.coverage == "complete"
            and not assessment.missing_information
            and assessment.time_basis.mode != "unresolved"
        )
        if complete and negative:
            return "contradicted"
        if complete and positive:
            return "supported"
        return "insufficient"
    if any(e.coverage == "complete" for e in negative):
        return "contradicted"
    if any(e.coverage == "complete" for e in positive) and not assessment.missing_information:
        return "supported"
    return "insufficient"


def validate_judgment(content: str, packet: JudgmentPacket, contract: str = "legacy_v1"):
    result = response_model(contract).model_validate_json(content)
    if contract in {"compact_v1_2", "relevance_v1"}:
        aliases = evidence_aliases(packet)
        value = result.model_dump()
        for assessment in value["assessments"]:
            for item in assessment["evidence_assessments"]:
                if item["evidence_id"] not in aliases:
                    raise ValueError("Unknown exact evidence alias.")
                item["evidence_id"] = aliases[item["evidence_id"]]
            for field in ["coverage_summary", "time_basis"]:
                if any(alias not in aliases for alias in assessment[field]["evidence_ids"]):
                    raise ValueError("Unknown exact evidence alias.")
                assessment[field]["evidence_ids"] = [
                    aliases[alias] for alias in assessment[field]["evidence_ids"]
                ]
        result_type = (
            RelevanceJudgmentResponse if contract == "relevance_v1" else ReconciledJudgmentResponse
        )
        result = result_type.model_validate(value)
    expected = {n.id for n in packet.needs}
    if (
        len(result.assessments) != len(expected)
        or {a.need_id for a in result.assessments} != expected
    ):
        raise ValueError("Every requested need must appear exactly once.")
    for assessment in result.assessments:
        evidence = {e.id: e for e in packet.evidence if e.need_id == assessment.need_id}
        assigned = assessment.evidence_assessments
        if len(assigned) != len(evidence) or {e.evidence_id for e in assigned} != set(evidence):
            raise ValueError("Assess every supplied need-bound evidence ID exactly once.")
        if any(not gap.strip() for gap in assessment.missing_information):
            raise ValueError("Missing-information items cannot be blank.")
        for item in assigned:
            source = evidence[item.evidence_id]
            if isinstance(item, RelevanceEvidenceAssessment):
                if item.relevance != "relevant" and (
                    item.relation != "insufficient"
                    or item.coverage != "none"
                    or item.basis != "none"
                ):
                    raise ValueError(
                        "Irrelevant or uncertain evidence cannot establish a relation."
                    )
                if item.relation != "insufficient" and item.basis == "none":
                    raise ValueError("Directional evidence needs a direct or inferred basis.")
            if item.relation != "insufficient" and (item.coverage == "none" or not item.excerpts):
                raise ValueError("Directional relations need material coverage and citations.")
            if item.relation == "insufficient" and item.coverage == "complete":
                raise ValueError("Insufficient evidence cannot have complete coverage.")
            quotes = [x.quote for x in item.excerpts]
            if len(quotes) != len(set(quotes)):
                raise ValueError("Duplicate citations.")
            for excerpt in item.excerpts:
                offset = source.quote.find(excerpt.quote)
                if offset < 0 or offset != source.quote.rfind(excerpt.quote):
                    raise ValueError("Citation must literally match the supplied source context.")
        if isinstance(assessment, ReconciledNeedAssessment):
            if isinstance(assessment, RelevanceNeedAssessment):
                has_both = {"supports", "contradicts"} <= {x.relation for x in assigned}
                if has_both == (assessment.conflict_type == "none"):
                    raise ValueError("Conflict type must agree with directional evidence.")
            summary, temporal = assessment.coverage_summary, assessment.time_basis
            for ids in [summary.evidence_ids, temporal.evidence_ids]:
                if len(ids) != len(set(ids)) or not set(ids) <= set(evidence):
                    raise ValueError(
                        "Summary and time basis must reference unique IDs in this need."
                    )
            directional = {x.evidence_id for x in assigned if x.relation != "insufficient"}
            if not set(summary.evidence_ids) <= directional:
                raise ValueError("Coverage must cite material directional evidence.")
            if (summary.coverage == "none") != (not summary.evidence_ids):
                raise ValueError("Coverage summary and evidence references disagree.")
            if summary.coverage == "complete" and (
                assessment.missing_information or temporal.mode == "unresolved"
            ):
                raise ValueError("Complete need coverage cannot have unresolved gaps or time.")
            if (
                temporal.mode in {"explicit_source_text", "publication_context"}
                and not temporal.evidence_ids
            ):
                raise ValueError("A temporal basis needs source references.")
            if temporal.mode == "not_required" and temporal.evidence_ids:
                raise ValueError("Unneeded temporal context cannot claim source references.")
            if temporal.mode == "explicit_source_text" and any(
                not next(x for x in assigned if x.evidence_id == i).excerpts
                for i in temporal.evidence_ids
            ):
                raise ValueError("An explicit textual time basis needs literal excerpts.")
            if temporal.mode == "publication_context" and any(
                evidence[i].publication_context.status != "unambiguous"
                for i in temporal.evidence_ids
            ):
                raise ValueError(
                    "Ambiguous or missing publication dates cannot establish publication context."
                )
        if need_status(assessment) == "insufficient" and not assessment.missing_information:
            raise ValueError("Insufficient needs must identify missing information.")
    return result


def resolved_citations(result: JudgmentResponse, packet: JudgmentPacket) -> list[dict]:
    evidence = {e.id: e for e in packet.evidence}
    citations = []
    for assessment in result.assessments:
        for item in assessment.evidence_assessments:
            source = evidence[item.evidence_id]
            for excerpt in item.excerpts:
                start = source.start + source.quote.index(excerpt.quote)
                citations.append(
                    {
                        "need_id": assessment.need_id,
                        "evidence_id": source.id,
                        "page_id": source.page_id,
                        "source_url": source.source_url,
                        "start": start,
                        "end": start + len(excerpt.quote),
                        "quote": excerpt.quote,
                    }
                )
    return citations
