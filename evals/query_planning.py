"""Build and validate an experimental claim-to-query plan; no search execution."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

PROMPT_VERSION = "query_planning_v1"


class StrictRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    @field_validator("*", mode="after")
    @classmethod
    def reject_blank_strings(cls, value):
        if isinstance(value, str) and not value.strip():
            raise ValueError("Text must not be blank.")
        return value


class PlanningClaim(StrictRecord):
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    group: str | None


class SearchQuery(StrictRecord):
    text: str = Field(min_length=1, max_length=240)
    language: Literal["tr", "en"]


class ResearchQuestion(StrictRecord):
    claim_ids: list[str] = Field(min_length=1)
    question: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    queries: list[SearchQuery] = Field(min_length=1, max_length=2)


class DeferredClaim(StrictRecord):
    claim_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class QueryPlan(StrictRecord):
    questions: list[ResearchQuestion]
    deferred_claims: list[DeferredClaim]


class InformationNeed(StrictRecord):
    id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: Literal["planned", "needs_context", "budget_deferred"]
    reason: str | None


class ComponentQuestion(StrictRecord):
    need_ids: list[str] = Field(min_length=1)
    question: str = Field(min_length=1)
    queries: list[SearchQuery] = Field(min_length=1, max_length=2)


class ComponentQueryPlan(StrictRecord):
    needs: list[InformationNeed] = Field(min_length=1)
    questions: list[ComponentQuestion]


class MappedSearchQuery(SearchQuery):
    need_ids: list[str] = Field(min_length=1)


class MappedQuestion(StrictRecord):
    need_ids: list[str] = Field(min_length=1)
    question: str = Field(min_length=1)
    queries: list[MappedSearchQuery] = Field(min_length=1, max_length=2)


class MappedComponentPlan(StrictRecord):
    needs: list[InformationNeed] = Field(min_length=1)
    questions: list[MappedQuestion]


def build_request(
    claims: list[PlanningClaim],
    *,
    catalog_path: Path,
    source_language: Literal["tr", "en"],
    source_published_at: str | None = None,
    maximum_queries: int = 16,
    model: str = "muse-spark-1.3",
    prompt_version: str = PROMPT_VERSION,
    response_schema: Literal["claim", "component", "mapped_component"] | None = None,
) -> tuple[dict, str]:
    if not claims or len({claim.id for claim in claims}) != len(claims):
        raise ValueError("Input claims must have unique IDs and must not be empty.")
    if not 1 <= maximum_queries <= 40:
        raise ValueError("Query budget must be between 1 and 40.")
    catalog = yaml.safe_load(catalog_path.read_text(encoding="utf-8-sig"))
    entry = catalog["experiments"][prompt_version]
    system = entry["system"]
    if entry.get("few_shot_examples"):
        system += "\nSynthetic examples:\n" + json.dumps(
            entry["few_shot_examples"], ensure_ascii=False
        )
    context = {
        "source_language": source_language,
        "source_published_at": source_published_at,
        "allowed_search_languages": ["tr", "en"],
        "maximum_queries": maximum_queries,
        "claims": [claim.model_dump() for claim in claims],
    }
    contract = response_schema or (
        "component" if prompt_version == "query_planning_v3" else "claim"
    )
    schemas = {
        "claim": QueryPlan,
        "component": ComponentQueryPlan,
        "mapped_component": MappedComponentPlan,
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "query_plan",
                "strict": True,
                "schema": schemas[contract].model_json_schema(),
            },
        },
        "reasoning_effort": "low",
        "max_completion_tokens": 8192,
        "store": False,
        "stream": False,
    }, sha256(system.encode("utf-8")).hexdigest()


def validate_plan(
    content: str,
    claims: list[PlanningClaim],
    maximum_queries: int,
    *,
    prompt_version: str = PROMPT_VERSION,
) -> QueryPlan | ComponentQueryPlan:
    if prompt_version == "query_planning_v3":
        return validate_component_plan(content, claims, maximum_queries)
    plan = QueryPlan.model_validate_json(content)
    expected = {claim.id for claim in claims}
    planned = set()
    unique_queries = set()
    count = 0
    for question in plan.questions:
        ids = question.claim_ids
        if len(set(ids)) != len(ids) or not set(ids) <= expected:
            raise ValueError("Research question has duplicate or unknown claim IDs.")
        planned.update(ids)
        for query in question.queries:
            # Preserve case: it can affect operators and provider behavior.
            key = (" ".join(query.text.split()), query.language)
            if key in unique_queries:
                raise ValueError(
                    "Duplicate query; share one research question instead."
                )
            unique_queries.add(key)
            count += 1
    deferred = [claim.claim_id for claim in plan.deferred_claims]
    if len(set(deferred)) != len(deferred) or not set(deferred) <= expected:
        raise ValueError("Deferred claims contain duplicate or unknown IDs.")
    if planned & set(deferred):
        raise ValueError("A claim cannot be both planned and deferred.")
    if planned | set(deferred) != expected:
        raise ValueError("The plan silently omitted input claims.")
    if count > maximum_queries:
        raise ValueError("Query budget exceeded.")
    return plan


def validate_component_plan(
    content: str, claims: list[PlanningClaim], maximum_queries: int
) -> ComponentQueryPlan:
    plan = ComponentQueryPlan.model_validate_json(content)
    expected = {claim.id for claim in claims}
    needs = {need.id: need for need in plan.needs}
    if len(needs) != len(plan.needs):
        raise ValueError("Information needs contain duplicate IDs.")
    if {need.claim_id for need in plan.needs} != expected:
        raise ValueError("Information needs contain unknown or omitted claim IDs.")
    descriptions = set()
    for need in plan.needs:
        key = (need.claim_id, " ".join(need.description.casefold().split()))
        if key in descriptions:
            raise ValueError("Duplicate information need for one claim.")
        descriptions.add(key)
        if need.status != "planned" and not need.reason:
            raise ValueError("Deferred information needs require an explicit reason.")
    referenced = set()
    queries = set()
    count = 0
    for question in plan.questions:
        ids = question.need_ids
        if len(set(ids)) != len(ids) or not set(ids) <= needs.keys():
            raise ValueError("Question has duplicate or unknown information need IDs.")
        if any(needs[need_id].status != "planned" for need_id in ids):
            raise ValueError(
                "A deferred information need cannot have a search question."
            )
        referenced.update(ids)
        for query in question.queries:
            key = (" ".join(query.text.split()), query.language)
            if key in queries:
                raise ValueError(
                    "Duplicate query; share one research question instead."
                )
            queries.add(key)
            count += 1
    planned = {need.id for need in plan.needs if need.status == "planned"}
    if referenced != planned:
        raise ValueError("A planned information need is missing its research question.")
    if count > maximum_queries:
        raise ValueError("Query budget exceeded.")
    return plan


def validate_mapped_plan(
    content: str, claims: list[PlanningClaim], maximum_queries: int
) -> MappedComponentPlan:
    plan = MappedComponentPlan.model_validate_json(content)
    compatible = plan.model_dump()
    for question in compatible["questions"]:
        for query in question["queries"]:
            query.pop("need_ids")
    validate_component_plan(json.dumps(compatible), claims, maximum_queries)
    for question in plan.questions:
        covered = set()
        for query in question.queries:
            ids = query.need_ids
            if len(ids) != len(set(ids)) or not set(ids) <= set(question.need_ids):
                raise ValueError("Query has duplicate or foreign information need IDs.")
            covered.update(ids)
        if covered != set(question.need_ids):
            raise ValueError("Question needs are not covered by its search queries.")
    return plan
