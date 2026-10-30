"""Bounded follow-up queries for research needs left unsettled by the first round."""

import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "followup_queries_v1"
GapKind = Literal["no_results", "irrelevant_results", "missing_context"]


class ResearchGap(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    need_id: str = Field(min_length=1)
    claim_statement: str
    need_description: str
    gap: GapKind
    previous_queries: list[str]
    missing: list[str] = Field(description="Explanations of the unsettled details")


class FollowupQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    need_id: str = Field(min_length=1)
    text: str = Field(min_length=1, max_length=200)
    language: Literal["tr", "en"]
    reason: str = Field(min_length=1, max_length=300)


class FollowupPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    queries: list[FollowupQuery]


def classify_gap(hit_count: int, passage_count: int) -> GapKind:
    if hit_count == 0:
        return "no_results"
    if passage_count == 0:
        return "irrelevant_results"
    return "missing_context"


def build_followup_request(
    gaps: list[ResearchGap], *, prompts_path: Path, maximum_queries: int, model: str
) -> dict:
    if not gaps or maximum_queries < 1:
        raise ValueError("Follow-up planning requires gaps and a positive query budget.")
    catalog = yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
    context = {
        "maximum_queries": maximum_queries,
        "allowed_search_languages": ["tr", "en"],
        "gaps": [gap.model_dump() for gap in gaps],
    }
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": catalog["experiments"][PROMPT_VERSION]["system"]},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "followup_queries",
                "strict": True,
                "schema": FollowupPlan.model_json_schema(),
            },
        },
        "reasoning_effort": "low",
        "max_completion_tokens": 2048,
        "store": False,
        "stream": False,
    }


def normalize_query(text: str) -> str:
    return " ".join(text.casefold().split())


def parse_followup_response(
    content: str, gaps: list[ResearchGap], maximum_queries: int
) -> list[FollowupQuery]:
    plan = FollowupPlan.model_validate_json(content)
    by_need = {gap.need_id: gap for gap in gaps}
    accepted, seen_needs = [], set()
    for query in plan.queries:
        gap = by_need.get(query.need_id)
        if gap is None:
            raise ValueError("Follow-up query references a need without a gap.")
        if query.need_id in seen_needs:
            raise ValueError("At most one follow-up query per need.")
        previous = {normalize_query(text) for text in gap.previous_queries}
        # A repeated query cannot find new evidence; drop it rather than spend a search.
        if normalize_query(query.text) in previous:
            continue
        seen_needs.add(query.need_id)
        accepted.append(query)
    if len(accepted) > maximum_queries:
        raise ValueError("Follow-up queries exceed the budget.")
    return accepted
