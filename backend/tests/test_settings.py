import pytest

from clear_context.core.settings import Settings, load_model_selections


def test_model_override_and_blank_inheritance():
    settings = Settings(
        _env_file=None, model_default="spark_1_2", model_judge="wonder", model_screenshot=" "
    )
    selected = load_model_selections(settings)
    assert selected["judge"].api_model_id == "muse-wonder-1.0"
    assert selected["screenshot"].api_model_id == "muse-spark-1.2"


def test_yaml_default_when_environment_is_empty():
    selected = load_model_selections(Settings(_env_file=None, model_default=""))
    assert selected["research"].alias == "spark_1_3"


@pytest.mark.parametrize(
    "alias",
    [
        "missing",
        "wonder_full",
        "spark_open",
        "glimmer",
        "sam_3_1",
        "image_1_0",
        "voice_transcribe",
        "spark_1_3_contributor",
    ],
)
def test_unusable_or_unapproved_models_fail_closed(alias):
    with pytest.raises(ValueError):
        load_model_selections(Settings(_env_file=None, model_default=alias))


def test_contributor_requires_explicit_opt_in():
    selected = load_model_selections(
        Settings(
            _env_file=None, model_default="spark_1_3_contributor", model_allow_training_use=True
        )
    )
    assert selected["judge"].training_use is True


def test_key_is_excluded_from_serialization():
    settings = Settings(_env_file=None, meta_api_key="test-secret")
    assert "test-secret" not in repr(settings)
    assert "meta_api_key" not in settings.model_dump()


def test_live_mode_cannot_be_enabled_accidentally():
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_mode="live")


@pytest.mark.parametrize("port", [0, 65536, "not-a-port"])
def test_invalid_ports_are_rejected(port):
    with pytest.raises(ValueError):
        Settings(_env_file=None, api_port=port)


def test_environment_overrides_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text('API_PORT=8123\nCORS_ALLOWED_ORIGINS=["http://localhost:5173"]\n')
    monkeypatch.setenv("API_PORT", "8124")
    settings = Settings(_env_file=env_file)
    assert settings.api_port == 8124
    assert settings.cors_allowed_origins == ["http://localhost:5173"]


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "http://*",
        "file:///test",
        "https://host/path",
        "https://user:password@host",
        "https://host?token=test",
    ],
)
def test_invalid_cors_origins_are_rejected(origin):
    with pytest.raises(ValueError):
        Settings(_env_file=None, cors_allowed_origins=[origin])
