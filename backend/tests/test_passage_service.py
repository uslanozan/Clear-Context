"""Concurrent paragraph selection, source binding and bounded live-call checks."""

import asyncio
import json

import httpx
import pytest

from clear_context.core.passage_selectors import load_selector
from clear_context.core.settings import PROJECT_ROOT, ModelSelection, Settings
from clear_context.providers.meta_passages import MetaPassageProvider
from clear_context.repositories.retrieval import RetrievalRepository, identity
from clear_context.schemas.retrieval import SavedResearchPlan
from clear_context.services.passage_selection import PassageSelectionService, SelectionJob


@pytest.fixture
def workspace(tmp_path):
    repo = RetrievalRepository(tmp_path / "pages.sqlite")
    repo.register_plan(
        SavedResearchPlan.model_validate(
            {
                "case_id": "case",
                "claims": [{"id": "C1", "statement": "A university claim", "quote": "University"}],
                "needs": [
                    {"id": n, "claim_id": "C1", "description": n, "status": "planned"}
                    for n in ["n1", "n2"]
                ]
                + [
                    {
                        "id": "n3",
                        "claim_id": "C1",
                        "description": "Unknown date",
                        "status": "needs_context",
                    }
                ],
                "queries": [
                    {
                        "id": "Q1",
                        "request": {"query": "University history", "language": "en"},
                        "need_ids": ["n1", "n2"],
                    }
                ],
            }
        )
    )
    repo.ingest_search(
        "case",
        "Q1",
        {
            "query": "University history",
            "results": [
                {"title": "A", "url": "https://example.org/a"},
                {"title": "B", "url": "https://example.org/b"},
            ],
        },
        1000,
    )
    pages = [
        repo.save_page(
            identity("s_", "https://example.org/" + x), x.upper() + " source paragraph", 1000
        )
        for x in ["a", "b"]
    ]
    yield repo, pages
    repo.close()


def make_service(repo, handler, **changes):
    method, profile, limits, system = load_selector(
        PROJECT_ROOT / "config/passage_selectors.yaml", PROJECT_ROOT / "config/prompts.yaml"
    )
    limits = limits.model_copy(update=changes)
    settings = Settings(
        _env_file=None,
        app_mode="meta",
        allow_paid_api_calls=True,
        meta_api_key="fake-secret",
        model_default="spark_1_3",
    )
    provider = MetaPassageProvider(settings, httpx.MockTransport(handler))
    return PassageSelectionService(
        repo,
        provider,
        method,
        profile,
        limits,
        system,
        ModelSelection(alias="spark_1_3", api_model_id="muse-spark-1.3", training_use=False),
        clock=lambda: 1000,
    )


def completion(request, paragraph="P001"):
    context = json.loads(json.loads(request.content)["messages"][1]["content"])
    selections = [
        {
            "need_id": n["id"],
            "status": "relevant",
            "paragraph_ids": [paragraph],
            "reason": "Candidate",
        }
        for n in context["needs"]
    ]
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps({"selections": selections})},
                }
            ],
            "usage": {"prompt_tokens": 20, "completion_tokens": 5},
        },
    )


def test_two_inflight_requests_finish_out_of_order_but_keep_page_identity(workspace):
    repo, pages = workspace
    active = maximum = 0
    finished = []

    async def handler(request):
        nonlocal active, maximum
        context = json.loads(json.loads(request.content)["messages"][1]["content"])
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.04 if context["source_url"].endswith("/a") else 0.01)
        active -= 1
        finished.append(context["source_url"])
        return completion(request)

    service = make_service(repo, handler)
    rows = asyncio.run(
        service.select_pages([SelectionJob("case", page, ("n1",)) for page in pages])
    )
    assert maximum == service.max_active == 2
    assert finished[0].endswith("/b")
    assert [r["page_id"] for r in rows] == pages
    data = repo.export()
    assert len(data["research_selection_passages"]) == 2
    by_page = {p["page_id"]: p["quote"] for p in data["research_passages"]}
    assert by_page[pages[0]] == "A source paragraph"
    assert by_page[pages[1]] == "B source paragraph"
    assert "fake-secret" not in json.dumps(data)


def test_same_page_needs_merge_and_cached_replay_uses_no_model_call(workspace):
    repo, pages = workspace
    sent = []

    def handler(request):
        sent.append(request)
        return completion(request)

    service = make_service(repo, handler)
    jobs = [SelectionJob("case", pages[0], (n,)) for n in ["n1", "n2"]]
    rows = asyncio.run(service.select_pages(jobs))
    assert len(rows) == len(sent) == 1
    assert rows[0]["need_ids"] == ["n1", "n2"]
    assert len(repo.export()["research_selection_passages"]) == 2
    replay = make_service(repo, lambda _: pytest.fail("No network"), max_model_calls=0)
    cached = asyncio.run(replay.select_pages(jobs))
    assert cached[0]["cached"] and replay.calls == 0
    assert cached[0]["selection_id"] == rows[0]["selection_id"]
    assert len(repo.export()["research_selections"]) == 1


def test_unknown_paragraph_is_rejected_without_passage_or_success_cache(workspace):
    repo, pages = workspace
    service = make_service(repo, lambda request: completion(request, "P999"))
    row = asyncio.run(service.select_pages([SelectionJob("case", pages[0], ("n1",))]))[0]
    assert row["status"] == "invalid_selection"
    data = repo.export()
    assert not data["research_selections"] and not data["research_passages"]
    assert repo.cached("selection", row["request_key"], 1000) is None


def test_all_jobs_are_preflighted_before_any_live_call(workspace):
    repo, pages = workspace
    service = make_service(repo, lambda _: pytest.fail("No network"))
    with pytest.raises(ValueError):
        asyncio.run(
            service.select_pages(
                [SelectionJob("case", pages[0], ("n1",)), SelectionJob("case", pages[1], ("n3",))]
            )
        )
    assert service.calls == 0


def test_call_cap_and_oversized_page_do_not_silently_truncate(workspace):
    repo, pages = workspace
    service = make_service(repo, completion, max_model_calls=1)
    rows = asyncio.run(
        service.select_pages([SelectionJob("case", page, ("n1",)) for page in pages])
    )
    assert service.calls == 1
    assert sum(r["status"] == "call_budget_exhausted" for r in rows) == 1
    long_page = repo.save_page(identity("s_", "https://example.org/a"), "Content " * 100, 1001)
    service = make_service(repo, lambda _: pytest.fail("No network"), max_page_chars=100)
    row = asyncio.run(service.select_pages([SelectionJob("case", long_page, ("n1",))]))[0]
    assert row["status"] == "page_too_large" and service.calls == 0


def test_rate_limit_stops_queued_work_after_bounded_retries(workspace):
    repo, pages = workspace
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(429, json={"error": "limited"})

    service = make_service(repo, handler, max_concurrency=1)
    rows = asyncio.run(
        service.select_pages([SelectionJob("case", page, ("n1",)) for page in pages])
    )
    # One call and two bounded retries; queued pages are not attempted.
    assert len(sent) == 3
    assert [r["status"] for r in rows] == ["rate_limited", "not_run_after_failure"]


def test_selector_catalog_rejects_unknown_profile_or_implementation(tmp_path):
    import yaml

    path = tmp_path / "selectors.yaml"
    original = yaml.safe_load((PROJECT_ROOT / "config/passage_selectors.yaml").read_text())
    original["selected"] = "missing"
    path.write_text(yaml.safe_dump(original))
    with pytest.raises(ValueError):
        load_selector(path, PROJECT_ROOT / "config/prompts.yaml")
    original["selected"] = "full_page_v1"
    original["selectors"]["full_page_v1"]["implementation"] = "unimplemented_hybrid"
    path.write_text(yaml.safe_dump(original))
    with pytest.raises(ValueError):
        load_selector(path, PROJECT_ROOT / "config/prompts.yaml")


@pytest.mark.parametrize(
    "coverage,status,ids,gaps,valid",
    [
        ("direct", "relevant", ["P001"], [], True),
        ("partial", "relevant", ["P001"], ["Distance"], True),
        ("none", "not_found", [], ["No article body"], True),
        ("partial", "relevant", ["P001"], [], False),
        ("direct", "relevant", ["P001"], ["Distance"], False),
        ("none", "relevant", ["P001"], [], False),
        ("direct", "not_found", [], [], False),
        ("partial", "relevant", ["P999"], ["Distance"], False),
    ],
)
def test_coverage_contract(coverage, status, ids, gaps, valid):
    from clear_context.schemas.passage_selection import validate

    content = json.dumps(
        {
            "selections": [
                {
                    "need_id": "n1",
                    "status": status,
                    "paragraph_ids": ids,
                    "reason": "Explanation",
                    "coverage": coverage,
                    "missing_components": gaps,
                }
            ]
        }
    )
    if valid:
        result = validate(content, {"n1": ["P001"]}, "coverage_v2")
        assert result.selections[0].coverage == coverage
    else:
        with pytest.raises(ValueError):
            validate(content, {"n1": ["P001"]}, "coverage_v2")


def test_provider_metadata_only_keeps_allowlisted_quota_headers(workspace):
    repo, pages = workspace

    def handler(request):
        response = completion(request)
        response.headers.update(
            {
                "x-ratelimit-limit-requests": "3000",
                "set-cookie": "private-cookie",
                "authorization": "private-token",
            }
        )
        return response

    service = make_service(repo, handler)
    asyncio.run(service.select_pages([SelectionJob("case", pages[0], ("n1",))]))
    metadata = service.provider.response_metadata
    assert metadata[0]["rate_limit_headers"] == {"x-ratelimit-limit-requests": "3000"}
    assert "private" not in json.dumps(metadata)


def test_v2_service_preserves_coverage_in_receipt_and_cache(workspace):
    repo, pages = workspace

    def handler(request):
        payload = json.loads(request.content)
        assert "coverage" in json.dumps(payload["response_format"])
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {
                                    "selections": [
                                        {
                                            "need_id": "n1",
                                            "status": "relevant",
                                            "paragraph_ids": ["P001"],
                                            "reason": "Partial location",
                                            "coverage": "partial",
                                            "missing_components": ["Distance"],
                                        }
                                    ]
                                }
                            )
                        },
                    }
                ]
            },
        )

    service = make_service(repo, handler)
    service.profile = service.profile.model_copy(update={"response_contract": "coverage_v2"})
    service.method = "full_page_v2"
    job = SelectionJob("case", pages[0], ("n1",))
    first = asyncio.run(service.select_pages([job]))[0]
    second = asyncio.run(service.select_pages([job]))[0]
    assert first["output"]["selections"][0]["coverage"] == "partial"
    assert second["cached"] and service.calls == 1
    assert "missing_components" in repo.export()["research_selections"][0]["result"]


def test_null_concurrency_launches_finite_batch_together(workspace):
    repo, _ = workspace
    pages = [
        repo.save_page(identity("s_", "https://example.org/a"), f"Snapshot {i}", 1000 + i)
        for i in range(7)
    ]
    active = maximum = 0
    all_started = asyncio.Event()

    async def handler(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        if active == 7:
            all_started.set()
        await asyncio.wait_for(all_started.wait(), timeout=2)
        active -= 1
        return completion(request)

    service = make_service(repo, handler, max_concurrency=None, max_model_calls=7)
    rows = asyncio.run(service.select_pages([SelectionJob("case", p, ("n1",)) for p in pages]))
    assert maximum == service.max_active == service.calls == 7
    assert all(r["status"] == "selected" for r in rows)
    assert [r["page_id"] for r in rows] == pages


def test_null_concurrency_still_obeys_total_call_budget(workspace):
    repo, _ = workspace
    pages = [
        repo.save_page(identity("s_", "https://example.org/a"), f"Snapshot {i}", 1000 + i)
        for i in range(7)
    ]
    service = make_service(repo, completion, max_concurrency=None, max_model_calls=3)
    rows = asyncio.run(service.select_pages([SelectionJob("case", p, ("n1",)) for p in pages]))
    assert service.calls == 3
    assert sum(r["status"] == "call_budget_exhausted" for r in rows) == 4


def test_context_keeps_raw_selection_and_new_policy_reuses_model_cache(workspace):
    repo, _ = workspace
    page = repo.save_page(
        identity("s_", "https://example.org/a"),
        "The report says " + "a detail " * 10 + "but this is uncertain. Another fact.",
        1001,
    )
    service = make_service(repo, completion, paragraph_max_chars=50)
    job = SelectionJob("case", page, ("n1",))
    first = asyncio.run(service.select_pages([job]))[0]
    assert first["output"]["selections"][0]["paragraph_ids"] == ["P001"]
    original_quote = repo.export()["research_passages"][0]["quote"]
    assert len(first["context_windows"][0]["quote"]) > len(original_quote)
    assert "uncertain" in first["context_windows"][0]["quote"]
    receipt = json.loads(repo.export()["research_selections"][0]["result"])
    assert receipt["context_windows"] == first["context_windows"]
    replay = make_service(
        repo,
        lambda _: pytest.fail("Model cache must be reused"),
        paragraph_max_chars=50,
        context_after_chars=0,
    )
    second = asyncio.run(replay.select_pages([job]))[0]
    assert replay.calls == 0 and second["cached"]
    assert second["context_windows"][0]["after_truncated"]
    assert first["selection_id"] != second["selection_id"]


def test_repository_rejects_context_with_modified_source_text(workspace):
    from dataclasses import replace

    from clear_context.schemas.passage_selection import NeedSelection, Selections
    from clear_context.services.paragraphs import paragraphs
    from clear_context.services.passage_context import source_context

    repo, pages = workspace
    page = repo.page(pages[0])
    units = paragraphs(page["content"])
    context = source_context(page["content"], units[0], "n1", 500, 500)
    output = Selections(
        selections=[
            NeedSelection(
                need_id="n1",
                status="relevant",
                paragraph_ids=["P001"],
                reason="Source text",
            )
        ]
    )
    with pytest.raises(ValueError, match="Context differs"):
        repo.save_selection(
            "case",
            pages[0],
            "full_page_v1",
            "model",
            "prompt",
            "key",
            output,
            {u.id: u for u in units},
            1000,
            context_windows=[replace(context, quote="Altered source quote")],
        )
    assert not repo.export()["research_selections"]
