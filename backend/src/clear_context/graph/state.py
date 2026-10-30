import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated, NotRequired, TypedDict
from uuid import UUID

from clear_context.domain.investigation import (
    Claim,
    ExtractionCoverage,
    InvestigationReport,
    MediaFinding,
    ModelUsage,
)
from clear_context.providers.base import InvestigationProvider


class InvestigationState(TypedDict):
    investigation_id: UUID
    text: str
    # Uploaded files: id, kind, mime_type, filename and a local path.
    media: NotRequired[list[dict]]
    media_findings: NotRequired[list[MediaFinding]]
    analyzed_text: NotRequired[str]
    claims: NotRequired[list[Claim]]
    report: NotRequired[InvestigationReport]
    # Several nodes report usage; keep all of it.
    model_usage: NotRequired[Annotated[list[ModelUsage], operator.add]]
    extraction_coverage: NotRequired[ExtractionCoverage | None]


@dataclass(frozen=True)
class InvestigationContext:
    provider: InvestigationProvider = field(repr=False)
    research: object | None = field(default=None, repr=False)
    progress: Callable[[str], None] | None = field(default=None, repr=False)
    research_mode: str = "balanced"
    media_analyzer: object | None = field(default=None, repr=False)
    reverse_image: object | None = field(default=None, repr=False)
