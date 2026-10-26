from fastapi.testclient import TestClient

from clear_context import __main__ as launcher
from clear_context.main import create_app


def test_launcher_uses_configured_settings(settings, monkeypatch):
    settings.api_host = "127.0.0.1"
    settings.api_port = 8123
    settings.log_level = "warning"
    monkeypatch.setattr(launcher, "Settings", lambda: settings)
    calls = []
    monkeypatch.setattr(launcher.uvicorn, "run", lambda app, **kwargs: calls.append(kwargs))
    launcher.main()
    assert calls == [{"host": "127.0.0.1", "port": 8123, "log_level": "warning", "workers": 1}]


def test_docs_can_be_disabled(settings):
    settings.api_docs_enabled = False
    with TestClient(create_app(settings)) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404
        assert client.get("/api/health").status_code == 200


def test_cors_allows_only_configured_origins(settings):
    settings.cors_allowed_origins = ["http://localhost:5173"]
    with TestClient(create_app(settings)) as client:
        headers = {
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        }
        response = client.options("/api/investigations", headers=headers)
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        response = client.post(
            "/api/investigations",
            json={"text": "Mock input"},
            headers={"Origin": "http://localhost:5173"},
        )
        assert "Location" in response.headers["access-control-expose-headers"]
        headers["Origin"] = "https://untrusted.example"
        response = client.options("/api/investigations", headers=headers)
        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
