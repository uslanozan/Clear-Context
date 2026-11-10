from fastapi.testclient import TestClient

from clear_context.core.settings import Settings
from clear_context.main import create_app


def built_web_app(root):
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>Clear Context</title>", "utf-8")
    (root / "assets" / "index-abc123.js").write_text("console.log(1)", "utf-8")
    (root / "favicon.ico").write_bytes(b"\x00\x00\x01\x00")
    return root


def test_serves_the_web_app_beside_the_api(settings, tmp_path):
    dist = built_web_app(tmp_path / "dist")
    app = create_app(settings.model_copy(update={"web_dist_dir": dist}))
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        home = client.get("/")
        assert home.status_code == 200
        assert "Clear Context" in home.text
        assert home.headers["cache-control"] == "no-cache"
        # Client-side routes load the app shell.
        route = client.get("/investigations/abc")
        assert route.status_code == 200 and "Clear Context" in route.text
        asset = client.get("/assets/index-abc123.js")
        assert asset.headers["cache-control"].endswith("immutable")
        assert client.get("/favicon.ico").status_code == 200
        # Missing assets and unknown API paths are errors, not the app shell.
        assert client.get("/assets/missing.js").status_code == 404
        assert client.get("/api/unknown").status_code == 404
        assert client.get("/api/unknown").headers["content-type"] == "application/json"
        # Paths outside the build folder are never served.
        (tmp_path / "secret.txt").write_text("private", "utf-8")
        outside = client.get("/..%2Fsecret.txt")
        assert "private" not in outside.text
        assert home.headers["x-content-type-options"] == "nosniff"
        assert home.headers["referrer-policy"] == "no-referrer"


def test_without_a_web_build_only_the_api_answers(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/").status_code == 404


def test_auto_migrate_creates_a_new_database(tmp_path):
    database = tmp_path / "data" / "clear-context.db"
    settings = Settings(
        _env_file=None,
        database_path=database,
        media_dir=tmp_path / "data" / "media",
        auto_migrate=True,
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/investigations").json() == []
    assert database.is_file()
    # A second start finds the schema current and keeps the data.
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200


def test_desktop_opens_a_running_instance_instead_of_starting_another(monkeypatch):
    from clear_context import desktop

    opened = []
    monkeypatch.setattr(desktop, "clear_context_health", lambda port: {"status": "ok"})
    monkeypatch.setattr(desktop.webbrowser, "open", opened.append)
    monkeypatch.setattr(desktop.uvicorn, "run", lambda *a, **k: opened.append("started"))
    desktop.main()
    assert opened == [f"http://127.0.0.1:{desktop.DEFAULT_PORT}/"]


def test_desktop_skips_ports_taken_by_other_programs(monkeypatch, tmp_path):
    from clear_context import desktop

    started = {}
    monkeypatch.setattr(desktop, "clear_context_health", lambda port: None)
    monkeypatch.setattr(desktop, "port_is_free", lambda port: port == desktop.DEFAULT_PORT + 2)
    monkeypatch.setattr(
        desktop.threading, "Thread", lambda **kwargs: type("T", (), {"start": lambda self: None})()
    )
    monkeypatch.setattr(desktop, "create_app", lambda settings: settings)
    monkeypatch.setattr(desktop.uvicorn, "run", lambda app, **kw: started.update(kw, settings=app))
    monkeypatch.setattr(desktop, "PROJECT_ROOT", tmp_path)
    desktop.main()
    assert started["port"] == desktop.DEFAULT_PORT + 2
    assert started["settings"].auto_migrate is True
