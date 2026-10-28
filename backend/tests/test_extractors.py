import pytest
import yaml

from clear_context.core.prompts import load_claim_extraction_prompt
from clear_context.core.settings import Settings, load_model_selections
from clear_context.providers.meta import MetaInvestigationProvider


def write_catalog(tmp_path, profile):
    path = tmp_path / "extractors.yaml"
    path.write_text(
        yaml.safe_dump({"schema_version": 1, "extractors": {"custom": profile}}),
        encoding="utf-8",
    )
    return path


def direct_profile(**overrides):
    return {
        "implementation": "direct",
        "prompt_source": "experiments",
        "prompt": "claim_extraction_tail_v1",
        "status": "provisional",
        **overrides,
    }


def test_alias_selects_same_prompt_and_direct_handler(tmp_path, monkeypatch):
    settings = Settings(
        _env_file=None,
        app_mode="meta",
        allow_paid_api_calls=True,
        meta_api_key="synthetic-test-key",
        prompt_claim_extraction="custom",
        extractor_catalog_path=write_catalog(tmp_path, direct_profile()),
    )
    selected = load_claim_extraction_prompt(settings)
    baseline = load_claim_extraction_prompt(
        Settings(_env_file=None, prompt_claim_extraction="d_v1")
    )
    assert selected.version == "custom"
    assert selected.system == baseline.system
    assert selected.sha256 == baseline.sha256
    monkeypatch.setattr(MetaInvestigationProvider, "_extract_direct", lambda self, text: text)
    provider = MetaInvestigationProvider(
        settings, load_model_selections(settings)["claim_extraction"]
    )
    assert provider.extract_claims("Synthetic source") == "Synthetic source"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"implementation": "arbitrary_module"}, "implementation"),
        ({"prompt": "missing_prompt"}, "prompt reference"),
        ({"prompt_source": "versions"}, "incompatible"),
        ({"status": "evaluation_only"}, "evaluation-only"),
    ],
)
def test_invalid_profiles_fail_before_model_calls(tmp_path, overrides, message):
    settings = Settings(
        _env_file=None,
        prompt_claim_extraction="custom",
        extractor_catalog_path=write_catalog(tmp_path, direct_profile(**overrides)),
    )
    with pytest.raises(ValueError, match=message):
        load_claim_extraction_prompt(settings)


def test_b_system_is_documented_but_not_runnable():
    with pytest.raises(ValueError, match="evaluation-only"):
        load_claim_extraction_prompt(Settings(_env_file=None, prompt_claim_extraction="b_system"))
