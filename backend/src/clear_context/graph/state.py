from dataclasses import dataclass, field
from typing import NotRequired, TypedDict
from uuid import UUID

from clear_context.domain.investigation import Claim, InvestigationReport
from clear_context.providers.base import InvestigationProvider


class InvestigationState(TypedDict):
    investigation_id: UUID
    text: str
    claims: NotRequired[list[Claim]]
    report: NotRequired[InvestigationReport]


@dataclass(frozen=True)
class InvestigationContext:
    provider: InvestigationProvider = field(repr=False)
