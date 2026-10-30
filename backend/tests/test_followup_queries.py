import json

import pytest

from clear_context.core.settings import PROJECT_ROOT
from clear_context.services.followup_queries import (
    ResearchGap,
    build_followup_request,
    classify_gap,
    parse_followup_response,
)

GAP = ResearchGap(
    need_id="n1",
    claim_statement="The mayor opened the bridge in 2019.",
    need_description="Who opened the bridge",
    gap="missing_context",
    previous_queries=["bridge opening year"],
    missing=["The record does not say who opened it."],
)


def query(need_id="n1", text="mayor bridge opening ceremony"):
    return {"need_id": need_id, "text": text, "language": "en", "reason": "Targets the opener."}


def test_gap_kind_comes_from_recorded_hits_and_passages():
    assert classify_gap(0, 0) == "no_results"
    assert classify_gap(3, 0) == "irrelevant_results"
    assert classify_gap(3, 2) == "missing_context"


def test_request_reads_the_catalog_prompt_and_sends_gaps_as_data():
    request = build_followup_request(
        [GAP], prompts_path=PROJECT_ROOT / "config/prompts.yaml", maximum_queries=2, model="m"
    )
    assert "follow-up web search queries" in request["messages"][0]["content"]
    context = json.loads(request["messages"][1]["content"])
    assert context["maximum_queries"] == 2
    assert context["gaps"][0]["gap"] == "missing_context"


def test_repeated_queries_are_dropped_and_unknown_needs_rejected():
    repeated = json.dumps({"queries": [query(text="Bridge  Opening year")]})
    assert parse_followup_response(repeated, [GAP], 2) == []
    with pytest.raises(ValueError, match="without a gap"):
        parse_followup_response(json.dumps({"queries": [query(need_id="n9")]}), [GAP], 2)


def test_one_query_per_need_and_total_budget():
    twice = json.dumps({"queries": [query(), query(text="bridge ribbon cutting mayor")]})
    with pytest.raises(ValueError, match="one follow-up query per need"):
        parse_followup_response(twice, [GAP], 2)
    other = GAP.model_copy(update={"need_id": "n2"})
    both = json.dumps({"queries": [query(), query(need_id="n2")]})
    with pytest.raises(ValueError, match="exceed the budget"):
        parse_followup_response(both, [GAP, other], 1)
