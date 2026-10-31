import asyncio
import json
from uuid import uuid4

import pytest

from clear_context.core.settings import PROJECT_ROOT, Settings
from clear_context.domain.investigation import (
    Assessment,
    Claim,
    Finding,
    InvestigationReport,
    ResearchSummary,
    Source,
)
from clear_context.services import investigation_research as research_module
from clear_context.services.claim_groups import Grouping, group_claims, parse_groups
from clear_context.services.investigation_research import (
    COMPLETE_BATCH_CLAIMS,
    COMPLETE_MAX_CLAIMS,
    InvestigationResearch,
    add_unresearched,
    batch_budget,
    merge_reports,
)
from clear_context.services.language import LanguageDecision

PROMPTS = PROJECT_ROOT / "config/prompts.yaml"


def test_groups_keep_the_first_claim_in_text_order_and_reject_invalid_answers():
    order = ["c1", "c2", "c3", "c4"]
    answer = json.dumps({"groups": [{"claim_ids": ["c4", "c2"]}]})
    assert parse_groups(answer, order) == {"c4": "c2"}
    for groups in (
        [{"claim_ids": ["c1"]}],
        [{"claim_ids": ["c1", "c9"]}],
        [{"claim_ids": ["c1", "c2"]}, {"claim_ids": ["c2", "c3"]}],
    ):
        with pytest.raises(ValueError):
            parse_groups(json.dumps({"groups": groups}), order)


class Provider:
    def __init__(self, content=None, error=None):
        self.content, self.error, self.requests = content, error, []

    async def complete(self, request, timeout):
        self.requests.append(request)
        if self.error:
            raise self.error
        return {"choices": [{"message": {"content": self.content}}], "usage": {}}


def test_grouping_is_skipped_for_few_claims_and_never_drops_claims_on_failure():
    claims = [("a", "One."), ("b", "Two.")]
    provider = Provider(json.dumps({"groups": []}))
    assert asyncio.run(group_claims(claims, provider, "m", PROMPTS)).duplicates == {}
    assert provider.requests == []
    three = [*claims, ("c", "Two again.")]
    found = asyncio.run(
        group_claims(
            three, Provider(json.dumps({"groups": [{"claim_ids": ["c", "b"]}]})), "m", PROMPTS
        )
    )
    assert found.duplicates == {"c": "b"} and found.usage.task == "claim_grouping"
    broken = asyncio.run(group_claims(three, Provider("not json"), "m", PROMPTS))
    assert (broken.duplicates, broken.failed) == ({}, True)
    request = Provider(json.dumps({"groups": []}))
    asyncio.run(group_claims(three, request, "m", PROMPTS))
    schema = request.requests[0]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["groups"]["items"]["properties"]["claim_ids"]["items"]["enum"] == [
        "a",
        "b",
        "c",
    ]


def claim(text):
    return Claim(id=uuid4(), text=text, statement=text)


def report_for(claims, sources=(), summary=None):
    return InvestigationReport(
        investigation_id=uuid4(),
        mode="meta",
        claims=list(claims),
        sources=list(sources),
        evidence=[],
        findings=[
            Finding(id=uuid4(), claim_id=c.id, assessment=Assessment.UNRESOLVED, explanation="x")
            for c in claims
        ],
        limitations=["shared"],
        research_summary=summary,
    )


def test_duplicates_and_held_claims_return_in_text_order():
    a, b, c, d = (claim(t) for t in ["We got no kits.", "No aid came.", "Kits never came.", "X"])
    researched = report_for([a, b], summary=ResearchSummary(planned=2, assessed=2))
    report = add_unresearched(researched, [a, b, c, d], {str(c.id): str(a.id)}, [d])
    assert [f.claim_id for f in report.findings] == [a.id, b.id, c.id, d.id]
    duplicate = report.findings[2]
    assert '"We got no kits."' in duplicate.explanation
    assert duplicate.components[0].status == "not_assessed"
    assert report.research_summary.budget_limited == 1
    assert report.research_summary.budget_limited_claim_ids == [d.id]


def test_batch_reports_merge_into_one_without_repeating_sources():
    shared = Source(id=uuid4(), url="https://a.example", title="a", content="text")
    first = report_for([claim("1")], [shared], ResearchSummary(planned=2, budget_limited=1))
    second = report_for([claim("2")], [shared], ResearchSummary(planned=3, assessed=3))
    merged = merge_reports(uuid4(), [first, second])
    assert len(merged.claims) == 2 and len(merged.sources) == 1
    assert (merged.research_summary.planned, merged.research_summary.budget_limited) == (5, 1)
    assert merged.limitations == ["shared"]


def test_complete_mode_researches_batches_and_leaves_the_rest_for_a_continuation(
    monkeypatch, tmp_path
):
    claims = [claim(f"Claim {i}.") for i in range(COMPLETE_MAX_CLAIMS + 5)]
    calls = []

    async def research(
        self, investigation_id, batch, progress, budget, media, subject, case_suffix=""
    ):
        calls.append((len(batch), budget, case_suffix))
        return report_for(batch, summary=ResearchSummary(planned=len(batch)))

    async def no_language(*args, **kwargs):
        return LanguageDecision("en", 1.0, "langdetect")

    async def no_groups(*args, **kwargs):
        return Grouping({})

    monkeypatch.setattr(InvestigationResearch, "_research", research)
    monkeypatch.setattr(research_module, "detect_language", no_language)
    monkeypatch.setattr(research_module, "group_claims", no_groups)
    settings = Settings(
        _env_file=None, app_mode="meta", allow_paid_api_calls=True, meta_api_key="k"
    )
    service = InvestigationResearch(settings, {"research": None}, tmp_path)
    service.models = {"research": type("M", (), {"api_model_id": "m"})()}
    report = service.run(uuid4(), claims, mode="complete")
    # Each batch is its own research case; the plan of one cannot collide with another.
    assert len({suffix for _, _, suffix in calls}) == len(calls)
    assert [n for n, _, _ in calls] == [COMPLETE_BATCH_CLAIMS] * (
        COMPLETE_MAX_CLAIMS // COMPLETE_BATCH_CLAIMS
    )
    assert calls[0][1] == batch_budget(COMPLETE_BATCH_CLAIMS)
    assert len(report.findings) == len(claims)
    assert report.research_summary.budget_limited_claim_ids == [c.id for c in claims[-5:]]


def test_batch_budget_reaches_every_claim_within_planner_limits():
    budget = batch_budget(COMPLETE_BATCH_CLAIMS)
    assert budget.max_queries <= 40 and budget.max_judgment_calls >= 2 * COMPLETE_BATCH_CLAIMS


def test_follow_up_runs_accept_complete_mode_but_settings_do_not(settings):
    from fastapi.testclient import TestClient

    from clear_context.main import create_app

    with TestClient(create_app(settings)) as client:
        created = client.post("/api/investigations", json={"text": "One claim."}).json()
        rerun = client.post(
            f"/api/investigations/{created['id']}/rerun", json={"research_mode": "complete"}
        )
        assert rerun.status_code == 202 and rerun.json()["research_mode"] == "complete"
        # An expensive mode is never a default.
        refused = client.put("/api/settings", json={"default_research_mode": "complete"})
        assert refused.status_code == 422
