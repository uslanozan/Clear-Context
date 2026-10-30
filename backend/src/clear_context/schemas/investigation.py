from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clear_context.domain.investigation import InvestigationStatus, ModelUsage, ResearchMode


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=20000)
    research_mode: ResearchMode = "balanced"


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


class StepView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: InvestigationStatus
    created_at: datetime
