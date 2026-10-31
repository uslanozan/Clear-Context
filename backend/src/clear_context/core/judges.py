"""Versioned, bounded evidence-assessment configuration."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from clear_context.core.judgment_labels import load_judgment_labels
from clear_context.core.prompts import PromptCatalog, experiment_system
from clear_context.core.settings import PROJECT_ROOT


class JudgeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    implementation: Literal["need_evidence_v1"]
    prompt: str
    response_contract: Literal[
        "legacy_v1",
        "reconciled_v1_1",
        "compact_v1_2",
        "relevance_v1",
        "components_v2",
        "components_v3",
    ] = "legacy_v1"
    max_completion_tokens: int | None = Field(default=None, ge=256, le=8192)


class JudgeLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_concurrency: int = Field(default=3, ge=1, le=10)
    max_model_calls: int = Field(default=3, ge=0, le=30)
    max_input_chars: int = Field(default=40000, ge=100, le=200000)
    max_completion_tokens: int = Field(default=4096, ge=256, le=8192)
    effort: Literal["minimal", "low", "medium", "high"] = "low"
    timeout_seconds: float = Field(default=100, gt=0, le=120)
    cache_ttl_seconds: int = Field(default=86400, gt=0)


class JudgeCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    selected: str
    judges: dict[str, JudgeProfile]
    limits: JudgeLimits


def load_judge(
    path: Path, prompts_path: Path, method: str | None = None, labels_path: Path | None = None
):
    load_judgment_labels(labels_path or PROJECT_ROOT / "config/judgment_labels.yaml")
    catalog = JudgeCatalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8-sig")))
    selected = method or catalog.selected
    if selected not in catalog.judges:
        raise ValueError("Unknown selected judge.")
    profile = catalog.judges[selected]
    prompts = PromptCatalog.model_validate(
        yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
    )
    if profile.prompt not in prompts.experiments:
        raise ValueError("Unknown central judge prompt.")
    limits = catalog.limits
    if profile.max_completion_tokens is not None:
        limits = limits.model_copy(update={"max_completion_tokens": profile.max_completion_tokens})
    system = experiment_system(
        {name: entry.model_dump() for name, entry in prompts.experiments.items()}, profile.prompt
    )
    return (selected, limits, system, profile.response_contract)
