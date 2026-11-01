"""The selected planner flags needs that only the attached media's own matches can settle."""

import json
from pathlib import Path

import pytest

from clear_context.core.query_catalog import (
    build_planner_request,
    load_planner_profile,
    parse_planner_response,
)
from clear_context.services.query_planning import PlanningClaim

ROOT = Path(__file__).resolve().parents[2]
CLAIM = PlanningClaim(
    id="c1",
    statement="The attached video shows a storm in Izmir.",
    quote="storm in Izmir",
    group=None,
)


def plan(flag=True):
    need = {
        "id": "n1",
        "claim_id": "c1",
        "description": "The attached video shows a storm in Izmir",
        "status": "planned",
        "reason": None,
    }
    if flag is not None:
        need["about_attached_media"] = flag
    return {
        "needs": [need],
        "questions": [
            {
                "need_ids": ["n1"],
                "question": "Where is it from?",
                "queries": [{"text": "Izmir storm video", "language": "en", "need_ids": ["n1"]}],
            }
        ],
    }


def test_selected_planner_asks_for_the_media_flag():
    payload, profile = build_planner_request(
        [CLAIM],
        planners_path=ROOT / "config/query_planners.yaml",
        prompts_path=ROOT / "config/prompts.yaml",
        source_language="en",
    )
    assert profile.response_schema == "media_mapped_component"
    need = payload["response_format"]["json_schema"]["schema"]["$defs"]["MediaInformationNeed"]
    assert "about_attached_media" in need["required"]
    assert "about_attached_media" in payload["messages"][0]["content"]


def test_flag_is_kept_and_required():
    profile = load_planner_profile(ROOT / "config/query_planners.yaml")
    parsed = parse_planner_response(json.dumps(plan()), [CLAIM], 4, profile)
    assert parsed["needs"][0]["about_attached_media"] is True
    with pytest.raises(ValueError):
        parse_planner_response(json.dumps(plan(flag=None)), [CLAIM], 4, profile)
