from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from clear_context.domain.investigation import (
    Assessment,
    Claim,
    Evidence,
    Finding,
    FindingComponent,
    InvestigationReport,
    InvestigationStatus,
    ResearchSummary,
    Source,
    TextSpan,
)
from clear_context.main import create_app
from clear_context.services.continuation import NothingToContinue, continuation_state

TEXT = "The bridge opened in 2019. The mayor opened it."


def parent_report(investigation_id) -> InvestigationReport:
    settled, limited = uuid4(), uuid4()
    source, evidence = uuid4(), uuid4()
    return InvestigationReport(
        investigation_id=investigation_id,
        mode="mock",
        claims=[
            Claim(
                id=settled,
                text="The bridge opened in 2019.",
                source_span=TextSpan(start=0, end=26, text="The bridge opened in 2019."),
            ),
            Claim(
                id=limited,
                text="The mayor opened it.",
                source_span=TextSpan(start=27, end=47, text="The mayor opened it."),
            ),
        ],
        sources=[Source(id=source, url="https://example.org/b", title="B", content="Opened 2019.")],
        evidence=[
            Evidence(id=evidence, claim_id=settled, source_id=source, excerpt="Opened 2019.")
        ],
        findings=[
            Finding(
                id=uuid4(),
                claim_id=settled,
                assessment=Assessment.UNRESOLVED,
                explanation="Review each detail.",
                evidence_ids=[evidence],
                components=[
                    FindingComponent(
                        description="Opening year",
                        status="supported",
                        explanation="The record says 2019.",
                        evidence_ids=[evidence],
                        evidence_relations={str(evidence): "supports"},
                    )
                ],
            ),
            Finding(
                id=uuid4(),
                claim_id=limited,
                assessment=Assessment.UNRESOLVED,
                explanation="Not researched within the budget.",
            ),
        ],
        limitations=[],
        research_summary=ResearchSummary(
            planned=1, assessed=1, budget_limited=1, budget_limited_claim_ids=[limited]
        ),
    )


def test_continuation_copies_settled_claims_under_new_ids_and_researches_the_rest():
    parent = parent_report(uuid4())
    state = continuation_state(parent, TEXT)
    assert [c.text for c in state["claims"]] == ["The mayor opened it."]
    assert [c.text for c in state["all_claims"]] == [c.text for c in parent.claims]
    # IDs are unique across investigations, so nothing copied keeps its old ID.
    old = (
        {c.id for c in parent.claims}
        | {e.id for e in parent.evidence}
        | {s.id for s in parent.sources}
    )
    kept = state["kept"]
    new = (
        {c.id for c in state["all_claims"]}
        | {e.id for e in kept["evidence"]}
        | {s.id for s in kept["sources"]}
    )
    assert not old & new
    [finding] = kept["findings"]
    [component] = finding.components
    assert component.evidence_ids == [kept["evidence"][0].id]
    assert component.evidence_relations == {str(kept["evidence"][0].id): "supports"}
    assert kept["evidence"][0].source_id == kept["sources"][0].id
    assert state["analyzed_text"] == TEXT


def test_nothing_to_continue_without_budget_limited_claims():
    parent = parent_report(uuid4()).model_copy(update={"research_summary": ResearchSummary()})
    with pytest.raises(NothingToContinue):
        continuation_state(parent, TEXT)


def test_rerun_and_continue_create_linked_investigations(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        repository = app.state.repository
        row = repository.create(TEXT, mode="mock")
        repository.transition(UUID(row.id), InvestigationStatus.RUNNING, "graph_started")
        repository.complete(parent_report(UUID(row.id)))

        rerun = client.post(f"/api/investigations/{row.id}/rerun", json={"research_mode": "deep"})
        assert rerun.status_code == 202
        assert (rerun.json()["parent_id"], rerun.json()["relation"]) == (row.id, "rerun")
        assert rerun.json()["research_mode"] == "deep"

        continued = client.post(f"/api/investigations/{row.id}/continue", json={})
        assert continued.status_code == 202 and continued.json()["relation"] == "continue"
        report = client.get(f"/api/investigations/{continued.json()['id']}/report").json()
        steps = client.get(f"/api/investigations/{continued.json()['id']}/steps").json()
        # The continuation skips extraction and merges the copied finding back in.
        assert [s["name"] for s in steps][:3] == [
            "graph_started",
            "evaluate_evidence",
            "merge_continuation",
        ]
        assert [c["text"] for c in report["claims"]] == [
            "The bridge opened in 2019.",
            "The mayor opened it.",
        ]
        assert report["findings"][0]["components"][0]["status"] == "supported"
        assert report["limitations"][0].startswith("Continued from an earlier report: 1 claim")

        # A mock report has no budget-limited claims, so it cannot be continued.
        assert (
            client.post(f"/api/investigations/{rerun.json()['id']}/continue", json={}).status_code
            == 409
        )


def test_rerun_reuses_uploaded_files(settings):
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
    app = create_app(settings)
    with TestClient(app) as client:
        created = client.post(
            "/api/investigations/upload",
            data={"text": "Caption"},
            files=[("files", ("photo.png", png, "image/png"))],
        ).json()
        rerun = client.post(f"/api/investigations/{created['id']}/rerun", json={}).json()
        media = app.state.repository.media_for(UUID(rerun["id"]))
    assert [(m.filename, m.mime_type) for m in media] == [("photo.png", "image/png")]
