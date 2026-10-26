from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_input_tokens: int | None = Field(default=None, ge=0)


class Claim(Record):
    id: UUID
    text: str = Field(min_length=1)


class ClaimExtraction(Record):
    claims: list[Claim]
    model_usage: list[ModelUsage] = Field(default_factory=list)


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
