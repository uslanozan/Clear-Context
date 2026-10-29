"""Versioned, bounded evidence-assessment configuration."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from clear_context.core.prompts import PromptCatalog


class JudgeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    implementation: Literal["need_evidence_v1"]
    prompt: str


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


def load_judge(path: Path, prompts_path: Path):
    catalog = JudgeCatalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8-sig")))
    if catalog.selected not in catalog.judges:
        raise ValueError("Unknown selected judge.")
    profile = catalog.judges[catalog.selected]
    prompts = PromptCatalog.model_validate(
        yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
    )
    if profile.prompt not in prompts.experiments:
        raise ValueError("Unknown central judge prompt.")
    return catalog.selected, catalog.limits, prompts.experiments[profile.prompt].system
