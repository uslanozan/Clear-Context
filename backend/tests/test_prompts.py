from hashlib import sha256

import pytest
import yaml

from clear_context.core.prompts import load_claim_extraction_prompt
from clear_context.core.settings import Settings
from clear_context.domain.investigation import ModelUsage
from clear_context.main import create_app


def write_catalog(tmp_path, system="Return at most ${max_claims} claims.", version="v1"):
    path = tmp_path / "prompts.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "prompts": {"claim_extraction": {"versions": {version: {"system": system}}}},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_default_prompt_preserves_extraction_instructions():
    prompt = load_claim_extraction_prompt(Settings(_env_file=None, meta_max_claims=3))
    assert prompt.version == "v1"
    assert "Return at most 3 unique claims." in prompt.system
    assert "exact, contiguous substrings" in prompt.system
    assert "Do not verify claims or add facts or sources." in prompt.system
    assert "${" not in prompt.system
    assert prompt.sha256 == sha256(prompt.system.encode("utf-8")).hexdigest()


def test_selected_version_and_rendered_limit_affect_receipt(tmp_path):
    path = write_catalog(tmp_path, version="v2")
    settings = Settings(
        _env_file=None, prompt_catalog_path=path, prompt_claim_extraction="v2", meta_max_claims=2
    )
    first = load_claim_extraction_prompt(settings)
    settings.meta_max_claims = 4
    second = load_claim_extraction_prompt(settings)
    assert first.version == second.version == "v2"
    assert first.system == "Return at most 2 claims."
    assert first.sha256 != second.sha256


@pytest.mark.parametrize("system", ["", "  ", "No placeholder.", "${input}", "${max_claims"])
def test_invalid_templates_fail_before_an_investigation(tmp_path, system):
    path = write_catalog(tmp_path, system=system)
    with pytest.raises(ValueError):
        create_app(Settings(_env_file=None, prompt_catalog_path=path))


def test_unknown_prompt_version_fails_at_startup(tmp_path):
    path = write_catalog(tmp_path)
    with pytest.raises(ValueError, match="Unknown claim extraction prompt version"):
        create_app(
            Settings(_env_file=None, prompt_catalog_path=path, prompt_claim_extraction="v99")
        )


def test_missing_catalog_fails_at_startup(tmp_path):
    with pytest.raises(FileNotFoundError):
        create_app(Settings(_env_file=None, prompt_catalog_path=tmp_path / "missing.yaml"))


def test_historical_usage_without_prompt_metadata_still_loads():
    usage = ModelUsage(task="claim_extraction", model_id="historical-model")
    assert usage.prompt_version is None
    assert usage.prompt_sha256 is None
