from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clear_context.domain.investigation import InvestigationStatus, ModelUsage, ResearchMode


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=20000)
    # None uses the default research mode from settings.
    research_mode: ResearchMode | None = None


class InvestigationFollowUp(BaseModel):
    """Run a report again, or continue the claims its budget did not reach."""

    model_config = ConfigDict(extra="forbid")
    research_mode: ResearchMode = "deep"


class InvestigationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    text: str
    status: InvestigationStatus
    mode: Literal["mock", "meta"]
    research_mode: ResearchMode
    revision: int
    created_at: datetime
    updated_at: datetime
    error_code: str | None
    model_usage: list[ModelUsage]
    parent_id: UUID | None = None
    relation: Literal["rerun", "continue"] | None = None
    group_id: UUID | None = None
    title: str | None = None
    # Queued investigations accepted earlier than this one; set only while it is queued.
    queue_position: int | None = None


class PlannedSearch(BaseModel):
    # Text searches carry query and language; reverse image lookups carry neither.
    kind: str = "text"
    query: str | None = None
    language: str | None = None
    # initial searches come from the plan; followup ones from the second round.
    origin: str


class PlannedNeed(BaseModel):
    claim_id: str
    description: str
    status: str


class ResearchOverview(BaseModel):
    """Recorded research work for one investigation; counts, never quality scores."""

    queries: list[PlannedSearch]
    needs: list[PlannedNeed]
    results: int
    sources_found: int
    selections: int


class StepView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: InvestigationStatus
    created_at: datetime
