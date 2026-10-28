import json
from pathlib import Path

import pytest
from query_planning import PlanningClaim, build_request, validate_plan


def claims():
    return [
        PlanningClaim(id="c1", statement="A claim.", quote="A claim.", group="Example"),
        PlanningClaim(
            id="c2", statement="Another claim.", quote="Another claim.", group="Example"
        ),
    ]


def question(ids, text="Example founding date"):
    return {
        "claim_ids": ids,
        "question": "When was Example founded?",
        "reason": "Check the founding date.",
        "queries": [{"text": text, "language": "en"}],
    }


def test_shared_question_preserves_every_claim():
    plan = validate_plan(
        json.dumps({"questions": [question(["c1", "c2"])], "deferred_claims": []}),
        claims(),
        2,
    )
    assert len(plan.questions) == 1
    assert plan.questions[0].claim_ids == ["c1", "c2"]


def test_explicit_deferral_is_not_silent_loss():
    plan = validate_plan(
        json.dumps(
            {
                "questions": [question(["c1"])],
                "deferred_claims": [
                    {"claim_id": "c2", "reason": "Missing subject identity."}
                ],
            }
        ),
        claims(),
        2,
    )
    assert plan.deferred_claims[0].claim_id == "c2"


@pytest.mark.parametrize(
    ("questions", "deferred", "budget", "message"),
    [
        ([question(["c1"])], [], 2, "omitted"),
        ([question(["c1", "missing"])], [], 2, "unknown"),
        ([question(["c1", "c1", "c2"])], [], 2, "duplicate"),
        ([question(["c1", "c2"])], [{"claim_id": "c1", "reason": "Budget"}], 2, "both"),
        ([question(["c1"]), question(["c2"])], [], 2, "Duplicate query"),
        ([question(["c1"]), question(["c2"], "Other query")], [], 1, "budget"),
        ([question(["c1", "c2"], "   ")], [], 2, "blank"),
    ],
)
def test_invalid_plans_are_rejected(questions, deferred, budget, message):
    with pytest.raises(ValueError, match=message):
        validate_plan(
            json.dumps({"questions": questions, "deferred_claims": deferred}),
            claims(),
            budget,
        )


def test_request_has_no_runtime_date_or_input_in_system():
    payload, digest = build_request(
        claims(),
        catalog_path=Path(__file__).resolve().parents[1] / "config/prompts.yaml",
        source_language="en",
    )
    context = json.loads(payload["messages"][1]["content"])
    assert context["source_published_at"] is None
    assert context["claims"][0]["quote"] == "A claim."
    assert "A claim." not in payload["messages"][0]["content"]
    assert payload["reasoning_effort"] == "low"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert len(digest) == 64


def test_prompt_comparison_preserves_payload_conditions():
    arguments = {
        "catalog_path": Path(__file__).resolve().parents[1] / "config/prompts.yaml",
        "source_language": "en",
    }
    baseline, baseline_hash = build_request(claims(), **arguments)
    candidate, candidate_hash = build_request(
        claims(), prompt_version="query_planning_v2", **arguments
    )
    assert baseline_hash != candidate_hash
    assert baseline["messages"][1] == candidate["messages"][1]
    assert {k: v for k, v in baseline.items() if k != "messages"} == {
        k: v for k, v in candidate.items() if k != "messages"
    }


def component_plan():
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
                "description": "Network size at source time",
                "status": "needs_context",
                "reason": "Source publication period is unknown.",
            },
            {
                "id": "n3",
                "claim_id": "c2",
                "description": "Related opening event",
                "status": "planned",
                "reason": None,
            },
        ],
        "questions": [
            {
                "need_ids": ["n1", "n3"],
                "question": "When did the museum open?",
                "queries": [{"text": "Example museum opening date", "language": "en"}],
            }
        ],
    }


def test_partial_claim_keeps_researchable_needs_and_explicit_gap():
    plan = validate_plan(
        json.dumps(component_plan()), claims(), 2, prompt_version="query_planning_v3"
    )
    first_claim = [need for need in plan.needs if need.claim_id == "c1"]
    assert {need.status for need in first_claim} == {"planned", "needs_context"}
    assert plan.questions[0].need_ids == ["n1", "n3"]


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda p: p["needs"][1].update(id="n1"), "duplicate IDs"),
        (lambda p: p["needs"][2].update(claim_id="missing"), "unknown or omitted"),
        (lambda p: p["needs"].pop(), "unknown or omitted"),
        (lambda p: p["needs"][1].update(reason=None), "explicit reason"),
        (lambda p: p["questions"][0].update(need_ids=["n1", "n2", "n3"]), "deferred"),
        (lambda p: p["questions"][0].update(need_ids=["n1"]), "missing its research"),
        (lambda p: p["questions"][0].update(need_ids=["n1", "n1", "n3"]), "duplicate"),
        (lambda p: p["questions"][0].update(need_ids=["unknown"]), "unknown"),
        (
            lambda p: p["needs"][1].update(description="opening DATE"),
            "Duplicate information",
        ),
    ],
)
def test_invalid_component_plans_are_rejected(mutation, message):
    plan = component_plan()
    mutation(plan)
    with pytest.raises(ValueError, match=message):
        validate_plan(json.dumps(plan), claims(), 2, prompt_version="query_planning_v3")


def test_v3_request_selects_component_schema_without_changing_input():
    arguments = {
        "catalog_path": Path(__file__).resolve().parents[1] / "config/prompts.yaml",
        "source_language": "en",
    }
    old, _ = build_request(claims(), prompt_version="query_planning_v2", **arguments)
    new, _ = build_request(claims(), prompt_version="query_planning_v3", **arguments)
    assert old["messages"][1] == new["messages"][1]
    schema = new["response_format"]["json_schema"]["schema"]
    assert set(schema["properties"]) == {"needs", "questions"}
    assert new["max_completion_tokens"] == old["max_completion_tokens"]


@pytest.mark.parametrize("budget,duplicate", [(1, False), (3, True)])
def test_component_plan_rejects_budget_overflow_and_duplicate_queries(
    budget, duplicate
):
    plan = component_plan()
    query = "Example   museum opening date" if duplicate else "Museum network history"
    plan["questions"].append(
        {
            "need_ids": ["n1"],
            "question": "What else is known about the museum?",
            "queries": [{"text": query, "language": "en"}],
        }
    )
    with pytest.raises(ValueError, match="Duplicate query" if duplicate else "budget"):
        validate_plan(
            json.dumps(plan), claims(), budget, prompt_version="query_planning_v3"
        )


def test_all_deferred_needs_remain_explicit_without_search_questions():
    plan = component_plan()
    for need in plan["needs"]:
        need.update(status="budget_deferred", reason="No query budget remains.")
    plan["questions"] = []
    result = validate_plan(
        json.dumps(plan), claims(), 1, prompt_version="query_planning_v3"
    )
    assert not result.questions
    assert {need.claim_id for need in result.needs} == {"c1", "c2"}
