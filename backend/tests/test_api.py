from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from clear_context.core.settings import Settings
from clear_context.domain.investigation import InvestigationStatus
from clear_context.main import create_app


def test_complete_mock_flow_and_persistence(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.post("/api/investigations", json={"text": "  A claim to investigate.  "})
        assert response.status_code == 202
        assert response.json()["status"] == "queued"
        investigation_id = response.json()["id"]
        assert response.headers["location"] == f"/api/investigations/{investigation_id}"
        status = client.get(response.headers["location"]).json()
        assert status["status"] == "completed"
        report = client.get(f"/api/investigations/{investigation_id}/report").json()
        assert report["mode"] == "mock"
        assert report["claims"][0]["text"] == "A claim to investigate."
        assert report["sources"] == report["evidence"] == []
        assert report["findings"][0]["assessment"] == "unresolved"
        assert "Mock output" in report["limitations"][0]
        steps = client.get(f"/api/investigations/{investigation_id}/steps").json()
        assert [step["name"] for step in steps] == [
            "graph_started",
            "extract_claims",
            "evaluate_evidence",
            "validate_report",
            "report_saved",
        ]
        assert [step["status"] for step in steps] == ["running"] * 4 + ["completed"]
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/api/investigations/{investigation_id}/report").json() == report
        assert client.get("/api/investigations").json()[0]["id"] == investigation_id


@pytest.mark.parametrize(
    "payload",
    [{"text": " "}, {"text": "x" * 20001}, {}, {"text": "test", "api_key": "not-allowed"}],
)
def test_invalid_input_is_rejected(settings, payload):
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/investigations", json=payload).status_code == 422
        assert client.get("/api/investigations").json() == []


def test_missing_pending_and_invalid_identifiers(settings):
    app = create_app(settings)
    with TestClient(app) as client:
        for suffix in ("", "/report", "/steps"):
            assert client.get(f"/api/investigations/{uuid4()}{suffix}").status_code == 404
        assert client.get("/api/investigations/not-a-uuid").status_code == 422
        row = app.state.repository.create("Pending input")
        assert client.get(f"/api/investigations/{row.id}/report").status_code == 409
        assert client.get("/api/investigations?limit=101").status_code == 422
        assert client.get("/api/investigations?offset=-1").status_code == 422


def test_health_models_and_openapi_do_not_expose_secrets(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").json()["paid_api_calls_enabled"] is False
        models = client.get("/api/models")
        assert models.json()["configured_models"]["judge"]["api_model_id"] == "muse-spark-1.3"
        for path in ("/api/models", "/api/health", "/openapi.json"):
            response = client.get(path)
            assert response.status_code == 200
            assert "test-secret-never-expose" not in response.text
            assert "meta_api_key" not in response.text.lower()


def test_provider_failure_is_sanitized_and_persisted(settings):
    class FailingProvider:
        def extract_claims(self, *args):
            raise RuntimeError("private-provider-secret")

    app = create_app(settings)
    with TestClient(app) as client:
        app.state.service.provider = FailingProvider()
        response = client.post("/api/investigations", json={"text": "A claim"})
        location = response.headers["location"]
        status = client.get(location)
        assert status.json()["status"] == "failed"
        assert status.json()["error_code"] == "processing_failed"
        assert "private-provider-secret" not in status.text
        assert client.get(location + "/report").status_code == 409
        assert "private-provider-secret" not in client.get(location + "/steps").text


def test_startup_marks_interrupted_jobs_failed(settings):
    app = create_app(settings)
    with TestClient(app):
        queued = app.state.repository.create("Queued input")
        running = app.state.repository.create("Running input")
        app.state.repository.transition(UUID(running.id), InvestigationStatus.RUNNING, "start")
    with TestClient(create_app(settings)) as client:
        for investigation_id in (queued.id, running.id):
            result = client.get(f"/api/investigations/{investigation_id}").json()
            assert result["status"] == "failed"
            assert result["error_code"] == "interrupted"


def test_startup_requires_migration(tmp_path):
    settings = Settings(_env_file=None, database_path=tmp_path / "empty.db")
    with pytest.raises(RuntimeError, match="Database not initialized"):
        with TestClient(create_app(settings)):
            pass
