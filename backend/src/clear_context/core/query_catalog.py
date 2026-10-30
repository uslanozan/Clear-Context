"""Select allowlisted query planners for offline or explicitly authorized evaluations."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from clear_context.services.query_planning import (
    PlanningClaim,
    build_request,
    validate_component_plan,
    validate_mapped_plan,
    validate_plan,
)


class PlannerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    implementation: Literal["structured_llm"]
    prompt: str = Field(min_length=1)
    response_schema: Literal["claim", "component", "mapped_component"]
    status: Literal["historical", "candidate"]


class PlannerCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    selected: str = Field(min_length=1)
    planners: dict[str, PlannerProfile] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_selection(self):
        if self.selected not in self.planners:
            raise ValueError("Selected query planner is absent from the catalog.")
        return self


def load_planner_profile(path: Path, method: str | None = None) -> PlannerProfile:
    catalog = PlannerCatalog.model_validate(yaml.safe_load(path.read_text(encoding="utf-8-sig")))
    selected = method if method is not None else catalog.selected
    if selected not in catalog.planners:
        raise ValueError("Unknown query planner method.")
    return catalog.planners[selected]


def build_planner_request(
    claims: list[PlanningClaim],
    *,
    planners_path: Path,
    prompts_path: Path,
    source_language: Literal["tr", "en", "auto"],
    source_published_at: str | None = None,
    maximum_queries: int = 16,
    model: str = "muse-spark-1.3",
    method: str | None = None,
    image_context: list[dict] | None = None,
) -> tuple[dict, PlannerProfile]:
    profile = load_planner_profile(planners_path, method)
    payload, _ = build_request(
        claims,
        catalog_path=prompts_path,
        source_language=source_language,
        source_published_at=source_published_at,
        maximum_queries=maximum_queries,
        model=model,
        prompt_version=profile.prompt,
        response_schema=profile.response_schema,
        image_context=image_context,
    )
    return payload, profile


def parse_planner_response(
    content: str,
    claims: list[PlanningClaim],
    maximum_queries: int,
    profile: PlannerProfile,
) -> dict:
    if profile.response_schema == "mapped_component":
        return validate_mapped_plan(content, claims, maximum_queries).model_dump()
    if profile.response_schema == "component":
        return validate_component_plan(content, claims, maximum_queries).model_dump()
    if profile.response_schema == "claim":
        return validate_plan(content, claims, maximum_queries).model_dump()
    raise ValueError("Unsupported query response schema.")
