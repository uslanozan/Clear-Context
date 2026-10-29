"""Reject label drift before inference without weakening typed output validation."""

from pathlib import Path

import pytest
import yaml

from clear_context.core.judgment_labels import load_judgment_labels
from clear_context.core.settings import PROJECT_ROOT


def test_catalog_separates_evidence_results_and_execution_failures():
    catalog = load_judgment_labels(PROJECT_ROOT / "config/judgment_labels.yaml")
    assert "invalid_judgment" not in catalog.groups["need_status"]
    assert "insufficient" not in catalog.groups["execution_status"]
    assert "mixed" in catalog.groups["need_status"]


@pytest.mark.parametrize("mutation", ["rename", "missing", "extra_group"])
def test_catalog_rejects_contract_drift(tmp_path: Path, mutation):
    data = yaml.safe_load(
        (PROJECT_ROOT / "config/judgment_labels.yaml").read_text(encoding="utf-8")
    )
    if mutation == "rename":
        data["groups"]["need_status"]["true"] = data["groups"]["need_status"].pop("supported")
    elif mutation == "missing":
        data["groups"]["evidence_relation"].pop("insufficient")
    else:
        data["groups"]["confidence"] = {}
    path = tmp_path / "labels.yaml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="contract"):
        load_judgment_labels(path)
