from collections.abc import Callable
from dataclasses import dataclass, field
from typing import NotRequired, TypedDict
from uuid import UUID

from clear_context.domain.investigation import (
    Claim,
    ExtractionCoverage,
    InvestigationReport,
    ModelUsage,
)
from clear_context.providers.base import InvestigationProvider


class InvestigationState(TypedDict):
    investigation_id: UUID
    text: str
    claims: NotRequired[list[Claim]]
    report: NotRequired[InvestigationReport]
    model_usage: NotRequired[list[ModelUsage]]
    extraction_coverage: NotRequired[ExtractionCoverage | None]


@dataclass(frozen=True)
class InvestigationContext:
    provider: InvestigationProvider = field(repr=False)
    research: object | None = field(default=None, repr=False)
    progress: Callable[[str], None] | None = field(default=None, repr=False)
    research_mode: str = "balanced"
