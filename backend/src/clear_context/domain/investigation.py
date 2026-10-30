from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Modes change search, reading and assessment budgets, never the methods.
ResearchMode = Literal["fast", "balanced", "deep"]


class InvestigationStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Assessment(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    MIXED = "mixed"
    UNRESOLVED = "unresolved"


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ModelUsage(Record):
    task: str
    model_id: str
    prompt_version: str | None = None
    prompt_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)
    chunk_start: int | None = Field(default=None, ge=0)
    chunk_end: int | None = Field(default=None, ge=0)
    outcome: Literal["accepted", "capacity_reached", "truncated", "invalid"] | None = None


class TextSpan(Record):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_span(self) -> Self:
        if self.end <= self.start or len(self.text) != self.end - self.start:
            raise ValueError("Span length must match its Unicode code-point offsets.")
        return self


class ExtractionChunk(Record):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    status: Literal["processed", "split", "partial"]
    reason: str | None = None


class ExtractionCoverage(Record):
    status: Literal["processed", "partial"]
    model_calls: int = Field(ge=0)
    chunks: list[ExtractionChunk]
    notes: list[str] = Field(default_factory=list)


class Claim(Record):
    group: str | None = None
    id: UUID
    text: str = Field(min_length=1)
    statement: str | None = Field(default=None, min_length=1)
    source_span: TextSpan | None = None
    context_spans: list[TextSpan] = Field(default_factory=list)
    context_status: Literal["standalone", "context_linked", "ambiguous"] | None = None

    @model_validator(mode="after")
    def validate_source_quote(self) -> Self:
        if self.source_span and self.source_span.text != self.text:
            raise ValueError("Claim text must equal its original source quote.")
        return self


class ClaimExtraction(Record):
    claims: list[Claim]
    model_usage: list[ModelUsage] = Field(default_factory=list)
    coverage: ExtractionCoverage | None = None


class Source(Record):
    id: UUID
    url: str
    title: str
    content: str


class Evidence(Record):
    id: UUID
    claim_id: UUID
    source_id: UUID
    excerpt: str = Field(min_length=1)


class Finding(Record):
    id: UUID
    claim_id: UUID
    assessment: Assessment
    explanation: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    components: list["FindingComponent"] = Field(default_factory=list)


class FindingComponent(Record):
    description: str = Field(min_length=1)
    # not_assessed: the detail was never evaluated (failed call or deferred need);
    # insufficient: it was evaluated and the evidence did not settle it.
    status: Literal["supported", "contradicted", "conflicting", "insufficient", "not_assessed"]
    explanation: str = Field(min_length=1)
    evidence_ids: list[UUID] = Field(default_factory=list)
    evidence_relations: dict[str, Literal["supports", "contradicts"]] = Field(default_factory=dict)
    # Passages reviewed for the same research need; not judged relevant to this detail.
    context_evidence_ids: list[UUID] = Field(default_factory=list)


class ImageMatch(Record):
    page_url: str = Field(min_length=1)
    page_title: str | None = None
    image_url: str | None = None
    match: Literal["full", "partial"]


class MediaOrigin(Record):
    """Where the image was found online; matches are leads, not proof of first publication."""

    status: Literal["not_checked", "matches_found", "no_matches", "failed"]
    provider: str | None = None
    reason: str | None = None
    matches: list[ImageMatch] = Field(default_factory=list)
    best_guess_labels: list[str] = Field(default_factory=list)


class MediaAnalysis(Record):
    """Model-read content of one file; transcription and observations can contain errors."""

    status: Literal["analyzed", "not_analyzed", "failed"]
    content_type: (
        Literal["photo", "post_screenshot", "text_screenshot", "graphic", "video", "other"] | None
    ) = None
    visible_text: str = ""
    observations: list[str] = Field(default_factory=list)
    context_cues: list[str] = Field(default_factory=list)
    note: str | None = None


class MediaFinding(Record):
    id: UUID
    kind: Literal["image", "video"]
    mime_type: str
    filename: str
    analysis: MediaAnalysis
    origin: MediaOrigin


class InvestigationReport(Record):
    investigation_id: UUID
    mode: Literal["mock", "meta"] = "mock"
    revision: int = Field(default=1, ge=1)
    claims: list[Claim]
    sources: list[Source]
    evidence: list[Evidence]
    findings: list[Finding]
    limitations: list[str]
    model_usage: list[ModelUsage] = Field(default_factory=list)
    extraction_coverage: ExtractionCoverage | None = None
    # User text plus text read from images; claim spans refer to this when present.
    analyzed_text: str | None = None
    media: list[MediaFinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        for records in (self.claims, self.sources, self.evidence, self.findings):
            if len({record.id for record in records}) != len(records):
                raise ValueError("Duplicate record IDs are not allowed.")
        claims = {claim.id for claim in self.claims}
        sources = {source.id: source for source in self.sources}
        evidence = {item.id: item for item in self.evidence}
        for item in self.evidence:
            if item.claim_id not in claims or item.source_id not in sources:
                raise ValueError("Evidence must reference existing claims and sources.")
            if item.excerpt not in sources[item.source_id].content:
                raise ValueError("Evidence excerpt must occur in the source content.")
        for finding in self.findings:
            if finding.claim_id not in claims:
                raise ValueError("Finding references an unknown claim.")
            if finding.assessment != Assessment.UNRESOLVED and not finding.evidence_ids:
                raise ValueError("A resolved finding requires evidence.")
            if len(set(finding.evidence_ids)) != len(finding.evidence_ids):
                raise ValueError("Duplicate evidence references are not allowed.")
            for evidence_id in finding.evidence_ids:
                item = evidence.get(evidence_id)
                if item is None or item.claim_id != finding.claim_id:
                    raise ValueError("Finding references invalid or unrelated evidence.")
            for component in finding.components:
                if len(component.evidence_ids) != len(set(component.evidence_ids)):
                    raise ValueError("Duplicate component evidence references are not allowed.")
                undirected = component.status in {"insufficient", "not_assessed"}
                if not undirected and not component.evidence_ids:
                    raise ValueError("A directional component requires evidence.")
                if component.status == "not_assessed" and (
                    component.evidence_ids or component.context_evidence_ids
                ):
                    raise ValueError("An unassessed component cannot reference evidence.")
                if any(eid not in finding.evidence_ids for eid in component.evidence_ids):
                    raise ValueError("Component references evidence outside its finding.")
                if len(component.context_evidence_ids) != len(set(component.context_evidence_ids)):
                    raise ValueError("Duplicate component context references are not allowed.")
                if any(eid not in finding.evidence_ids for eid in component.context_evidence_ids):
                    raise ValueError("Component context references evidence outside its finding.")
                if set(component.evidence_relations) != {
                    str(eid) for eid in component.evidence_ids
                }:
                    raise ValueError("Component evidence relations must match evidence IDs.")
                expected = {
                    "supported": {"supports"},
                    "contradicted": {"contradicts"},
                    "conflicting": {"supports", "contradicts"},
                    "insufficient": set(),
                    "not_assessed": set(),
                }
                if set(component.evidence_relations.values()) != expected[component.status]:
                    raise ValueError("Component status and evidence relations disagree.")
        if {finding.claim_id for finding in self.findings} != claims:
            raise ValueError("Every claim requires a finding.")
        if len(self.findings) != len(claims):
            raise ValueError("Each claim requires exactly one finding.")
        return self


def validate_transition(current: InvestigationStatus, target: InvestigationStatus) -> None:
    allowed = {
        InvestigationStatus.QUEUED: {InvestigationStatus.RUNNING, InvestigationStatus.FAILED},
        InvestigationStatus.RUNNING: {InvestigationStatus.COMPLETED, InvestigationStatus.FAILED},
        InvestigationStatus.COMPLETED: set(),
        InvestigationStatus.FAILED: set(),
    }
    if target not in allowed[current]:
        raise ValueError("Invalid investigation status transition.")
