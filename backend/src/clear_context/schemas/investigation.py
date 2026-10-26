from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from clear_context.domain.investigation import InvestigationStatus


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    text: str = Field(min_length=1, max_length=20000)


class InvestigationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    text: str
    status: InvestigationStatus
    mode: Literal["mock"]
    revision: int
    created_at: datetime
    updated_at: datetime
    error_code: str | None


class StepView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    status: InvestigationStatus
    created_at: datetime
