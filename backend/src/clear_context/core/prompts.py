from dataclasses import dataclass
from hashlib import sha256
from string import Template
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from clear_context.core.settings import Settings, resolve_path


class PromptTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    system: str = Field(min_length=1)

    @field_validator("system")
    @classmethod
    def validate_template(cls, value: str) -> str:
        template = Template(value)
        if not value.strip() or not template.is_valid():
            raise ValueError("Prompt must contain a valid, non-empty template.")
        if set(template.get_identifiers()) != {"max_claims"}:
            raise ValueError("Claim extraction requires only the max_claims placeholder.")
        return value


class PromptVersions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    versions: dict[str, PromptTemplate] = Field(min_length=1)


class ExperimentalPrompt(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    system: str = Field(min_length=1)
    few_shot_examples: list[dict[str, object]] = Field(default_factory=list)
    missing_check: str | None = None


class PromptCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    prompts: dict[Literal["claim_extraction"], PromptVersions]
    experiments: dict[str, ExperimentalPrompt] = Field(default_factory=dict)


@dataclass(frozen=True)
class RenderedPrompt:
    version: str
    system: str

    @property
    def sha256(self) -> str:
        return sha256(self.system.encode("utf-8")).hexdigest()


def load_claim_extraction_prompt(settings: Settings) -> RenderedPrompt:
    with resolve_path(settings.prompt_catalog_path).open(encoding="utf-8-sig") as stream:
        catalog = PromptCatalog.model_validate(yaml.safe_load(stream))
    if settings.prompt_claim_extraction == "d_v1":
        import json

        entry = catalog.experiments["claim_extraction_tail_v1"]
        return RenderedPrompt(
            version="d_v1",
            system=entry.system
            + "\nSynthetic demonstrations:\n"
            + json.dumps(entry.few_shot_examples, ensure_ascii=False),
        )
    prompt = catalog.prompts.get("claim_extraction")
    version = settings.prompt_claim_extraction
    if prompt is None or version not in prompt.versions:
        raise ValueError("Unknown claim extraction prompt version.")
    capacity = (
        settings.meta_max_claims if version == "v1" else settings.extraction_response_capacity
    )
    system = Template(prompt.versions[version].system).substitute(max_claims=capacity)
    return RenderedPrompt(version=version, system=system)
