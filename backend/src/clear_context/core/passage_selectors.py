"""Allowlisted passage-selection profiles and bounded execution settings."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from clear_context.core.prompts import PromptCatalog


class SelectorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    implementation: Literal["full_page"]
    prompt: str = Field(min_length=1)
    status: Literal["provisional"]
    response_contract: Literal["legacy_v1", "coverage_v2"] = "legacy_v1"


class SelectionLimits(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_concurrency: int | None = Field(
        default=10,
        ge=1,
        le=100,
        description="Null starts all finite batch jobs within the total live-call budget.",
    )
    max_model_calls: int = Field(default=10, ge=0, le=100)
    max_page_chars: int = Field(default=40000, ge=100, le=200000)
    paragraph_max_chars: int = Field(default=1000, ge=50, le=4000)
    max_completion_tokens: int = Field(default=4096, ge=256, le=8192)
    effort: Literal["minimal", "low", "medium", "high"] = "low"
    timeout_seconds: float = Field(default=100, gt=0, le=120)
    cache_ttl_seconds: int = Field(default=86400, gt=0)


class SelectorCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1]
    selected: str
    selectors: dict[str, SelectorProfile]
    limits: SelectionLimits

    @model_validator(mode="after")
    def check_selected(self):
        if self.selected not in self.selectors:
            raise ValueError("Unknown selected passage profile.")
        return self


def load_selector(catalog_path: Path, prompts_path: Path, method: str | None = None):
    catalog = SelectorCatalog.model_validate(
        yaml.safe_load(catalog_path.read_text(encoding="utf-8-sig"))
    )
    selected = method or catalog.selected
    if selected not in catalog.selectors:
        raise ValueError("Unknown passage selector.")
    profile = catalog.selectors[selected]
    prompts = PromptCatalog.model_validate(
        yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
    )
    if profile.prompt not in prompts.experiments:
        raise ValueError("Selector references an unavailable central prompt.")
    system = prompts.experiments[profile.prompt].system
    if not system.strip():
        raise ValueError("Empty selection prompt.")
    return selected, profile, catalog.limits, system
