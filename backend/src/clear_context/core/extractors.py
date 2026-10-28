from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from clear_context.core.settings import Settings, resolve_path

ExtractorImplementation = Literal["legacy", "chunked", "direct", "langextract"]


class ExtractorProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    implementation: ExtractorImplementation
    prompt_source: Literal["versions", "experiments"]
    prompt: str = Field(min_length=1)
    status: Literal["legacy", "provisional", "evaluation_only"]


class ExtractorCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    extractors: dict[str, ExtractorProfile] = Field(min_length=1)


def load_extractor_profile(settings: Settings) -> ExtractorProfile:
    with resolve_path(settings.extractor_catalog_path).open(encoding="utf-8-sig") as stream:
        catalog = ExtractorCatalog.model_validate(yaml.safe_load(stream))
    profile = catalog.extractors.get(settings.prompt_claim_extraction)
    if profile is None:
        raise ValueError("Unknown claim extraction prompt version or extractor profile.")
    if profile.status == "evaluation_only" or profile.implementation == "langextract":
        raise ValueError(
            "Selected extractor is evaluation-only and unavailable in the application."
        )
    if (profile.implementation == "direct") != (profile.prompt_source == "experiments"):
        raise ValueError("Extractor implementation and prompt contract are incompatible.")
    return profile
