from uuid import UUID, uuid4

from clear_context.domain.investigation import Assessment, Claim, Finding, InvestigationReport


class MockInvestigationProvider:
    def extract_claims(self, text: str) -> list[Claim]:
        return [Claim(id=uuid4(), text=text)]

    def evaluate_evidence(self, investigation_id: UUID, claims: list[Claim]) -> InvestigationReport:
        return InvestigationReport(
            investigation_id=investigation_id,
            claims=claims,
            sources=[],
            evidence=[],
            findings=[
                Finding(
                    id=uuid4(),
                    claim_id=claim.id,
                    assessment=Assessment.UNRESOLVED,
                    explanation="Mock mode: no sources were retrieved and no claim was verified.",
                )
                for claim in claims
            ],
            limitations=[
                "Mock output for API development; no model or search service was called.",
                "The complete input is preserved as one claim; decomposition is not implemented.",
            ],
        )
