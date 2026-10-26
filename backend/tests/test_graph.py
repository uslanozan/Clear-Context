from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langsmith import tracing_context

from clear_context.graph.investigation import build_investigation_graph
from clear_context.graph.state import InvestigationContext
from clear_context.main import create_app
from clear_context.providers.mock import MockInvestigationProvider


def test_graph_runs_are_isolated():
    graph = build_investigation_graph()
    provider = MockInvestigationProvider()
    ids = [uuid4(), uuid4()]
    results = []
    with tracing_context(enabled=False):
        for index, investigation_id in enumerate(ids):
            results.append(
                graph.invoke(
                    {"investigation_id": investigation_id, "text": f"Input {index}"},
                    context=InvestigationContext(provider=provider),
                    config={"recursion_limit": 12},
                )
            )
    assert [result["report"].investigation_id for result in results] == ids
    assert results[0]["report"].claims[0].text == "Input 0"
    assert results[1]["report"].claims[0].text == "Input 1"
    assert results[0]["report"].claims[0].id != results[1]["report"].claims[0].id


@pytest.mark.parametrize(
    "failure", ["empty_claims", "wrong_investigation", "changed_claim", "mutated_claim"]
)
def test_invalid_graph_output_is_not_persisted(settings, failure):
    class InvalidProvider(MockInvestigationProvider):
        def extract_claims(self, text):
            return [] if failure == "empty_claims" else super().extract_claims(text)

        def evaluate_evidence(self, investigation_id, claims):
            if failure == "mutated_claim":
                claims[0].text = "Changed in place"
                return super().evaluate_evidence(investigation_id, claims)
            report = super().evaluate_evidence(investigation_id, claims)
            if failure == "wrong_investigation":
                return report.model_copy(update={"investigation_id": uuid4()})
            return report.model_copy(
                update={
                    "claims": [
                        claim.model_copy(update={"text": "Changed scope"}) for claim in claims
                    ]
                }
            )

    app = create_app(settings)
    with TestClient(app) as client:
        app.state.service.provider = InvalidProvider()
        created = client.post("/api/investigations", json={"text": "Original claim"})
        location = created.headers["location"]
        assert client.get(location).json()["status"] == "failed"
        assert client.get(location + "/report").status_code == 409
        steps = client.get(location + "/steps").json()
        assert steps[-1]["name"] == "investigation_failed"
        assert "report_saved" not in [step["name"] for step in steps]


def test_local_graph_does_not_enable_remote_tracing(settings, monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    with TestClient(create_app(settings)) as client:
        created = client.post("/api/investigations", json={"text": "Local-only mock input"})
        assert client.get(created.headers["location"]).json()["status"] == "completed"
