from typing import Protocol
from uuid import UUID

from clear_context.domain.investigation import Claim, ClaimExtraction, InvestigationReport


class InvestigationProvider(Protocol):
    def extract_claims(self, text: str) -> ClaimExtraction: ...

    def evaluate_evidence(
        self, investigation_id: UUID, claims: list[Claim]
    ) -> InvestigationReport: ...
