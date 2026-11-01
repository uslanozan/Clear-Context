"""Offline catalog and per-query coverage checks; no model calls."""

import json
from pathlib import Path

import pytest
import yaml
from query_catalog import (
    PlannerCatalog,
    build_planner_request,
    load_planner_profile,
    parse_planner_response,
)
from query_planning import PlanningClaim, validate_mapped_plan

ROOT = Path(__file__).resolve().parents[1]


def claim():
    return PlanningClaim(
        id="c1",
        statement="Example museum opened in 2009.",
        quote="Example museum opened in 2009.",
        group=None,
    )


def arguments():
    return {
        "planners_path": ROOT / "config/query_planners.yaml",
        "prompts_path": ROOT / "config/prompts.yaml",
        "source_language": "en",
    }


def test_default_selection_and_contract_are_catalog_driven():
    payload, profile = build_planner_request([claim()], **arguments())
    # The selection lives in the catalog; the test follows it instead of repeating a version,
    # which went stale once already (v5 to v8).
    catalog = yaml.safe_load(
        (ROOT / "config/query_planners.yaml").read_text(encoding="utf-8")
    )
    assert profile.prompt == catalog["planners"][catalog["selected"]]["prompt"]
    definitions = payload["response_format"]["json_schema"]["schema"]["$defs"]
    assert "need_ids" in definitions["MappedSearchQuery"]["properties"]
    assert json.loads(payload["messages"][1]["content"])["source_published_at"] is None


@pytest.mark.parametrize(
    "method,contract",
    [
        ("v1", "claim"),
        ("v3", "component"),
        ("v2", "claim"),
        ("v4", "mapped_component"),
    ],
)
def test_explicit_method_selection(method, contract):
    _, profile = build_planner_request([claim()], method=method, **arguments())
    assert profile.response_schema == contract


def test_unknown_and_unimplemented_methods_fail_before_inference():
    with pytest.raises(ValueError, match="Unknown query planner"):
        load_planner_profile(ROOT / "config/query_planners.yaml", "spacy")
    data = yaml.safe_load(
        (ROOT / "config/query_planners.yaml").read_text(encoding="utf-8")
    )
    data["selected"] = "missing"
    with pytest.raises(ValueError, match="absent"):
        PlannerCatalog.model_validate(data)
    data["selected"] = "v4"
    data["planners"]["v4"]["implementation"] = "unsupported"
    with pytest.raises(ValueError, match="implementation"):
        PlannerCatalog.model_validate(data)


def mapped_plan():
    return {
        "needs": [
            {
                "id": "n1",
                "claim_id": "c1",
                "description": "Opening date",
                "status": "planned",
                "reason": None,
            },
            {
                "id": "n2",
                "claim_id": "c1",
                "description": "Other detail",
                "status": "planned",
                "reason": None,
            },
        ],
        "questions": [
            {
                "need_ids": ["n1", "n2"],
                "question": "What is known?",
                "queries": [
                    {
                        "text": "Example opening date",
                        "language": "en",
                        "need_ids": ["n1"],
                    },
                    {
                        "text": "Example other detail",
                        "language": "en",
                        "need_ids": ["n2"],
                    },
                ],
            }
        ],
    }


def test_every_query_can_map_to_its_own_distinct_need():
    result = validate_mapped_plan(json.dumps(mapped_plan()), [claim()], 2)
    assert result.questions[0].queries[1].need_ids == ["n2"]


@pytest.mark.parametrize(
    "ids,message",
    [(["n1"], "not covered"), (["missing"], "foreign"), (["n1", "n1"], "duplicate")],
)
def test_query_mapping_cannot_claim_unsearched_question_coverage(ids, message):
    plan = mapped_plan()
    plan["questions"][0]["queries"][1]["need_ids"] = ids
    with pytest.raises(ValueError, match=message):
        validate_mapped_plan(json.dumps(plan), [claim()], 2)


def test_catalog_parser_validates_selected_schema():
    profile = load_planner_profile(ROOT / "config/query_planners.yaml")
    result = parse_planner_response(json.dumps(mapped_plan()), [claim()], 2, profile)
    assert result["questions"][0]["queries"][1]["need_ids"] == ["n2"]
    with pytest.raises(ValueError, match="budget"):
        parse_planner_response(json.dumps(mapped_plan()), [claim()], 1, profile)


def test_scope_prompt_comparison_preserves_input_schema_and_budgets():
    old, _ = build_planner_request([claim()], method="v4", **arguments())
    new, profile = build_planner_request([claim()], method="v5", **arguments())
    assert profile.prompt == "query_planning_v5"
    assert old["messages"][0] != new["messages"][0]
    assert old["messages"][1] == new["messages"][1]
    assert {k: v for k, v in old.items() if k != "messages"} == {
        k: v for k, v in new.items() if k != "messages"
    }
