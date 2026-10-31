from fastapi.testclient import TestClient
from pydantic import SecretStr

from clear_context.main import create_app
from clear_context.services.runtime import Runtime

PANEL_KEY = "tvly-panel-key-0123456789-abcd"


def test_keys_are_reported_without_their_values(settings):
    with TestClient(create_app(settings)) as client:
        view = client.get("/api/settings")
        saved = client.put("/api/settings", json={"tavily_api_key": f"  {PANEL_KEY}  "})
    assert view.status_code == saved.status_code == 200
    for response in (view, saved):
        assert "test-secret-never-expose" not in response.text
        assert PANEL_KEY not in response.text
    assert view.json()["keys"]["meta_api_key"] == {
        "configured": True,
        "preview": "test-sec...pose",
        "source": "env",
    }
    assert view.json()["keys"]["serp_api_key"]["configured"] is False
    assert saved.json()["keys"]["tavily_api_key"] == {
        "configured": True,
        "preview": "tvly-pan...abcd",
        "source": "panel",
    }
    assert saved.json()["changed"] == ["tavily_api_key"]


def test_short_keys_show_no_ending_and_bad_keys_are_rejected(settings):
    with TestClient(create_app(settings)) as client:
        short = client.put("/api/settings", json={"serp_api_key": "abcdefgh12"}).json()
        assert short["keys"]["serp_api_key"]["preview"] is None
        for bad in ("short", "has space inside", "line\nbreak-0123"):
            assert client.put("/api/settings", json={"serp_api_key": bad}).status_code == 422
        assert client.put("/api/settings", json={"unknown": 1}).status_code == 422


def test_saved_values_apply_without_restart_and_persist(settings):
    with TestClient(create_app(settings)) as client:
        before = client.app.state.service.runtime
        response = client.put(
            "/api/settings",
            json={
                "default_research_mode": "deep",
                "link_reading": False,
                "search_min_score": 0.4,
                "model_judge": "wonder",
            },
        )
        assert response.status_code == 200
        runtime = client.app.state.service.runtime
        assert runtime is not before and before.retired
        assert runtime.models["judge"].api_model_id == "muse-wonder-1.0"
        assert runtime.settings.search_min_score == 0.4
        assert client.get("/api/health").json()["default_research_mode"] == "deep"
        created = client.post("/api/investigations", json={"text": "A claim."}).json()
        assert created["research_mode"] == "deep"
        chosen = client.post(
            "/api/investigations", json={"text": "A claim.", "research_mode": "fast"}
        ).json()
        assert chosen["research_mode"] == "fast"
    with TestClient(create_app(settings)) as client:
        view = client.get("/api/settings").json()
        assert (view["default_research_mode"], view["link_reading"]) == ("deep", False)
        assert view["models"]["judge"] == "wonder"
        assert view["models"]["research"] == "spark_1_3"
        # null returns a value to its .env setting.
        reset = client.put("/api/settings", json={"link_reading": None}).json()
        assert reset["link_reading"] is True
        assert "link_reading" not in reset["changed"]


def test_models_are_limited_to_allowed_text_models(settings):
    with TestClient(create_app(settings)) as client:
        options = {item["alias"] for item in client.get("/api/settings").json()["model_options"]}
        assert {"spark_1_3", "wonder"} <= options
        # Contributor models allow training use, which is off; image models are not text models.
        assert "spark_1_3_contributor" not in options and "image_1_0" not in options
        for alias in ("spark_1_3_contributor", "image_1_0", "missing"):
            response = client.put("/api/settings", json={"model_research": alias})
            assert response.status_code == 422
        assert client.get("/api/settings").json()["changed"] == []


def test_paid_calls_need_a_meta_key_and_switch_the_mode(settings):
    no_key = settings.model_copy(update={"meta_api_key": settings.meta_api_key.__class__("")})
    with TestClient(create_app(no_key)) as client:
        refused = client.put("/api/settings", json={"paid_calls": True})
        assert refused.status_code == 422
        assert "Meta API key" in refused.json()["detail"]
        assert client.get("/api/health").json()["mode"] == "mock"
    with TestClient(create_app(settings)) as client:
        assert client.put("/api/settings", json={"paid_calls": True}).json()["paid_calls"]
        health = client.get("/api/health").json()
        assert (health["mode"], health["research_enabled"]) == ("meta", True)
        runtime = client.app.state.service.runtime
        assert runtime.link_reader is not None and runtime.research is not None
        off = client.put(
            "/api/settings", json={"link_reading": False, "reverse_image_search": False}
        )
        assert off.status_code == 200
        assert client.app.state.service.runtime.link_reader is None
        assert client.app.state.service.runtime.reverse_image is None
        client.put("/api/settings", json={"paid_calls": False})
        assert client.get("/api/health").json()["mode"] == "mock"


def test_requests_for_other_host_names_are_refused(settings):
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/health").status_code == 200
        rebound = client.get("/api/health", headers={"host": "attacker.example"})
        assert rebound.status_code == 400


class Client:
    closed = 0

    def close(self):
        Client.closed += 1


def test_replaced_runtime_closes_after_its_last_investigation():
    runtime = Runtime(
        settings=None, models={}, provider=None, media_analyzer=None, link_reader=Client()
    )
    Client.closed = 0
    runtime.acquire()
    runtime.retire()
    assert Client.closed == 0
    runtime.release()
    assert Client.closed == 1


def test_env_seeds_the_database_once_and_later_edits_are_marked(settings):
    from clear_context.repositories.settings import SettingsRepository

    with TestClient(create_app(settings)) as client:
        stored = SettingsRepository(client.app.state.repository.sessions).load()
        assert stored["meta_api_key"] == "test-secret-never-expose"
        assert (stored["link_reading"], stored["model_judge"]) == (True, "spark_1_3")
        # Empty keys are not stored, so a key added to .env later can still be seeded.
        assert "tavily_api_key" not in stored
        assert client.get("/api/settings").json()["changed"] == []

    edited = settings.model_copy(
        update={"link_reading": False, "tavily_api_key": SecretStr("tvly-from-env-0123456789")}
    )
    with TestClient(create_app(edited)) as client:
        view = client.get("/api/settings").json()
        # The saved value stays and is marked; the new .env key fills the empty field.
        assert (view["link_reading"], view["changed"]) == (True, ["link_reading"])
        assert client.app.state.service.runtime.settings.link_reading is True
        assert view["keys"]["tavily_api_key"] == {
            "configured": True,
            "preview": "tvly-fro...6789",
            "source": "env",
        }
        reset = client.put("/api/settings", json={"link_reading": None}).json()
        assert (reset["link_reading"], reset["changed"]) == (False, [])


def test_reset_all_takes_every_value_from_env(settings):
    from clear_context.services.app_settings import PANEL_FIELDS

    with TestClient(create_app(settings)) as client:
        client.put(
            "/api/settings",
            json={"serp_api_key": "serp-panel-key-000000", "model_judge": "wonder"},
        )
        client.put("/api/settings", json={"search_min_score": 0.5, "link_reading": False})
        assert len(client.get("/api/settings").json()["changed"]) == 4
        reset = client.put("/api/settings", json=dict.fromkeys(PANEL_FIELDS)).json()
        assert reset["changed"] == []
        assert reset["keys"]["serp_api_key"]["configured"] is False
        assert (reset["models"]["judge"], reset["search_min_score"]) == ("spark_1_3", 0.3)

