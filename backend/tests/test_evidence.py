from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from clear_context.db.session import create_database, create_session_factory
from clear_context.domain.investigation import (
    InvestigationReport,
    InvestigationStatus,
    validate_transition,
)
from clear_context.repositories.investigation import InvestigationRepository


def report_payload(investigation_id=None):
    claim_id, source_id, evidence_id = [str(uuid4()) for _ in range(3)]
    return {
        "investigation_id": str(investigation_id or uuid4()),
        "claims": [{"id": claim_id, "text": "Synthetic fixture claim."}],
        "sources": [
            {
                "id": source_id,
                "url": "https://example.invalid/fixture",
                "title": "Synthetic fixture",
                "content": "Fixture text supports a claim.",
            }
        ],
        "evidence": [
            {
                "id": evidence_id,
                "claim_id": claim_id,
                "source_id": source_id,
                "excerpt": "Fixture text",
            }
        ],
        "findings": [
            {
                "id": str(uuid4()),
                "claim_id": claim_id,
                "assessment": "supported",
                "explanation": "Synthetic fixture only.",
                "evidence_ids": [evidence_id],
            }
        ],
        "limitations": ["Synthetic fixture, not real-world evidence."],
    }


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_id",
        "wrong_excerpt",
        "wrong_claim",
        "no_evidence",
        "missing_finding",
        "duplicate_id",
    ],
)
def test_invalid_evidence_is_rejected(mutation):
    payload = report_payload()
    if mutation == "missing_id":
        payload["findings"][0]["evidence_ids"] = [str(uuid4())]
    elif mutation == "wrong_excerpt":
        payload["evidence"][0]["excerpt"] = "Invented quotation"
    elif mutation == "wrong_claim":
        payload["findings"][0]["claim_id"] = str(uuid4())
    elif mutation == "no_evidence":
        payload["findings"][0]["evidence_ids"] = []
    elif mutation == "missing_finding":
        payload["findings"] = []
    else:
        payload["evidence"].append(payload["evidence"][0].copy())
    with pytest.raises(ValidationError):
        InvestigationReport.model_validate(payload)


def test_evidence_round_trip_and_terminal_state(settings):
    engine = create_database(settings.database_path)
    try:
        repository = InvestigationRepository(create_session_factory(engine))
        row = repository.create("Synthetic fixture claim.")
        investigation_id = UUID(row.id)
        repository.transition(investigation_id, InvestigationStatus.RUNNING, "fixture")
        report = InvestigationReport.model_validate(report_payload(investigation_id))
        repository.complete(report)
        assert repository.get_report(investigation_id) == report
        with pytest.raises(ValueError):
            repository.complete(report)
        assert repository.get_report(investigation_id) == report
    finally:
        engine.dispose()


def test_completed_job_cannot_restart():
    with pytest.raises(ValueError):
        validate_transition(InvestigationStatus.COMPLETED, InvestigationStatus.RUNNING)
