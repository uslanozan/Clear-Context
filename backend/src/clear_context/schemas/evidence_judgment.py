"""Evidence-relative need assessments with literal citations, never global truth labels."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from clear_context.schemas.retrieval import ClaimReference, ResearchNeed


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
    relation: Literal["supports", "contradicts", "insufficient"]
    coverage: Literal["complete", "partial", "none"]
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


def need_status(assessment: NeedAssessment) -> str:
    positive = [e for e in assessment.evidence_assessments if e.relation == "supports"]
    negative = [e for e in assessment.evidence_assessments if e.relation == "contradicts"]
    if positive and negative:
        return "mixed"
    if any(e.coverage == "complete" for e in negative):
        return "contradicted"
    if any(e.coverage == "complete" for e in positive) and not assessment.missing_information:
        return "supported"
    return "insufficient"


def validate_judgment(content: str, packet: JudgmentPacket) -> JudgmentResponse:
    result = JudgmentResponse.model_validate_json(content)
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
