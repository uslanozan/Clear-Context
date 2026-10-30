"""Research provenance, cache freshness and bounded keyless execution."""

import json

import httpx
import pytest
from pydantic import ValidationError
from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from clear_context.providers.tavily import RetrievalFailure, TavilyClient
from clear_context.repositories.retrieval import RetrievalRepository, identity, query_needs
from clear_context.schemas.retrieval import RetrievalPolicy, SavedResearchPlan, SearchRequest
from clear_context.services.retrieval import RetrievalSession


def plan(case_id="case-a"):
    return SavedResearchPlan.model_validate(
        {
            "case_id": case_id,
            "claims": [
                {"id": "C1", "statement": "The university opened in 2002.", "quote": "in 2002"}
            ],
            "needs": [
                {"id": "n1", "claim_id": "C1", "description": "Founding date", "status": "planned"},
                {
                    "id": "n2",
                    "claim_id": "C1",
                    "description": "Faculty affiliation",
                    "status": "planned",
                },
                {
                    "id": "n3",
                    "claim_id": "C1",
                    "description": "Undated count",
                    "status": "needs_context",
                },
            ],
            "queries": [
                {
                    "id": "Q1",
                    "request": {"query": "Example University founding", "language": "en"},
                    "need_ids": ["n1"],
                },
                {
                    "id": "Q2",
                    "request": {"query": "Example University faculty", "language": "en"},
                    "need_ids": ["n2"],
                },
            ],
        }
    )


def search_response(query, url="https://example.org/history"):
    return {
        "query": query,
        "results": [{"title": "History", "url": url, "content": "Founded in 2007.", "score": 0.9}],
    }


@pytest.fixture
def repository(tmp_path):
    repo = RetrievalRepository(tmp_path / "research.sqlite")
    repo.register_plan(plan())
    yield repo
    repo.close()


def session(repository, handler, policy=None, now=None):
    provider = TavilyClient(transport=httpx.MockTransport(handler))
    service = RetrievalSession(
        repository, provider, policy or RetrievalPolicy(), clock=lambda: (now or [1000])[0]
    )
    return service


def ingest(repository, case="case-a", q="Q1"):
    request = repository.query(case, q)
    repository.ingest_search(case, q, search_response(request.query), 1000)
    return identity("s_", "https://example.org/history")


def test_repeated_url_keeps_both_queries_and_namespaced_need_links(repository):
    ingest(repository)
    ingest(repository, q="Q2")
    repository.register_plan(plan("case-b"))
    ingest(repository, case="case-b")
    data = repository.export()
    assert len(data["research_sources"]) == 1
    assert len(data["research_hits"]) == 3
    assert len(data["research_query_needs"]) == 4
    assert len(data["research_needs"]) == 6
    assert repository.plan("case-a").claims[0].quote == "in 2002"


def test_plan_and_database_reject_orphan_or_deferred_bindings(repository):
    data = plan().model_dump()
    data["queries"][0]["need_ids"] = ["n3"]
    with pytest.raises(ValidationError):
        SavedResearchPlan.model_validate(data)
    with pytest.raises(IntegrityError), repository.engine.begin() as conn:
        conn.execute(insert(query_needs).values(case_id="case-a", query_id="Q1", need_id="missing"))
    data = plan().model_dump()
    data["claims"][0]["statement"] = "Changed"
    with pytest.raises(ValueError, match="immutable"):
        repository.register_plan(SavedResearchPlan.model_validate(data))


def test_exact_search_cache_survives_restart_and_expires(repository):
    now = [1000]
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json=search_response(json.loads(request.content)["query"]))

    service = session(repository, handler, now=now)
    service.search("case-a", "Q1")
    service.provider.close()
    next_session = session(repository, handler, now=now)
    next_session.search("case-a", "Q1")
    assert len(sent) == 1 and next_session.calls["search"] == 0
    now[0] += 21601
    next_session.search("case-a", "Q1")
    assert len(sent) == 2
    assert repository.export()["research_hits"][0]["retrieved_at"] == now[0]
    next_session.provider.close()


def test_shared_page_read_once_and_exact_passage_keeps_both_need_edges(repository):
    source = ingest(repository)
    ingest(repository, q="Q2")
    sent = []
    content = "The faculty opened in 2002. The university opened in 2007."

    def handler(request):
        sent.append(request)
        assert "Authorization" not in request.headers
        assert request.headers["X-Tavily-Access-Mode"] == "keyless"
        assert "query" not in json.loads(request.content)
        return httpx.Response(
            200, json={"results": [{"url": "https://example.org/history", "raw_content": content}]}
        )

    service = session(repository, handler)
    page = service.read_source(source)
    assert service.read_source(source) == page
    quote = "The university opened in 2007."
    start = content.index(quote)
    repository.add_passage(page, start, len(content), quote, "case-a", ["n1", "n2"])
    assert len(sent) == 1
    assert len(repository.export()["research_passage_needs"]) == 2
    with pytest.raises(ValueError, match="offsets"):
        repository.add_passage(
            page, start, len(content), "The university opened in 2002.", "case-a", ["n1"]
        )
    with pytest.raises(ValueError, match="reference"):
        repository.add_passage(page, start, len(content), quote, "case-a", ["n3"])
    service.provider.close()


def test_passage_cannot_attach_to_unrelated_case(repository):
    source = ingest(repository)
    page = repository.save_page(source, "A literal passage", 1000)
    repository.register_plan(plan("case-b"))
    with pytest.raises(ValueError, match="not discovered"):
        repository.add_passage(page, 0, 17, "A literal passage", "case-b", ["n1"])


def test_rate_limit_halts_without_retry_or_paid_fallback(repository):
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(429, json={"error": "limited"})

    service = session(repository, handler)
    with pytest.raises(RetrievalFailure, match="rate_limited"):
        service.search("case-a", "Q1")
    with pytest.raises(RetrievalFailure, match="session_halted"):
        service.search("case-a", "Q2")
    assert len(sent) == 1
    assert repository.export()["research_events"][-1]["kind"] == "request_failed"
    service.provider.close()


def test_budget_and_followups_reject_new_claims_or_unbounded_search(repository):
    service = session(
        repository,
        lambda request: pytest.fail("Network not allowed"),
        RetrievalPolicy(max_search_calls=0, max_followup_queries=1),
    )
    with pytest.raises(RetrievalFailure, match="call_budget"):
        service.search("case-a", "Q1")
    request = SearchRequest(query="Example University independent founding date", language="en")
    with pytest.raises(ValueError):
        service.add_followup("case-a", "F1", request, ["n3"], "missing_context", "Undated")
    service.add_followup(
        "case-a",
        "F1",
        request,
        ["n1"],
        "irrelevant_results",
        "Returned pages concern another entity",
    )
    with pytest.raises(RetrievalFailure, match="followup_budget"):
        service.add_followup("case-a", "F2", request, ["n1"], "no_results", "Still missing")
    service.provider.close()


@pytest.mark.parametrize(
    "payload",
    [
        {
            "results": [],
            "failed_results": [{"url": "https://example.org/history", "error": "Unavailable"}],
        },
        {"results": [{"url": "https://other.example/", "raw_content": "Wrong source"}]},
        {"results": [{"url": "https://example.org/history", "raw_content": ""}]},
    ],
)
def test_failed_misattributed_or_empty_extract_never_becomes_page(repository, payload):
    source = ingest(repository)
    service = session(repository, lambda request: httpx.Response(200, json=payload))
    with pytest.raises(RetrievalFailure):
        service.read_source(source)
    assert repository.export()["research_pages"] == []
    service.provider.close()


def test_failed_page_cache_avoids_repeated_download_until_expiry(repository):
    source = ingest(repository)
    now, sent = [1000], []

    def handler(request):
        sent.append(request)
        return httpx.Response(
            200, json={"results": [], "failed_results": [{"url": "https://example.org/history"}]}
        )

    service = session(repository, handler, now=now)
    for _ in range(2):
        with pytest.raises(RetrievalFailure, match="extract_failed"):
            service.read_source(source)
    assert len(sent) == 1
    now[0] += 301
    with pytest.raises(RetrievalFailure, match="extract_failed"):
        service.read_source(source)
    assert len(sent) == 2
    service.provider.close()


def test_page_refresh_preserves_old_passage_snapshot(repository):
    source = ingest(repository)
    old = repository.save_page(source, "Old literal content", 1000)
    repository.add_passage(old, 0, 19, "Old literal content", "case-a", ["n1"])
    new = repository.save_page(source, "New literal content", 2000)
    assert old != new
    assert repository.page(old)["content"] == "Old literal content"
    assert repository.export()["research_passages"][0]["page_id"] == old


def test_recorded_query_reuses_cache_across_cases(repository):
    repository.register_plan(plan("case-b"))
    sent = []

    def handler(request):
        sent.append(request)
        return httpx.Response(200, json=search_response(json.loads(request.content)["query"]))

    service = session(repository, handler)
    service.search("case-a", "Q1")
    service.search("case-b", "Q1")
    assert len(sent) == 1
    assert len(repository.export()["research_hits"]) == 2
    service.provider.close()


@pytest.mark.parametrize(
    ("api_key", "expected"),
    [
        ("", {"x-tavily-access-mode": "keyless"}),
        ("tvly-test", {"authorization": "Bearer tvly-test"}),
    ],
)
def test_client_uses_api_key_when_configured_and_keyless_otherwise(api_key, expected):
    seen = []

    def handler(request):
        seen.append(request.headers)
        return httpx.Response(200, json=search_response("q"))

    client = TavilyClient(transport=httpx.MockTransport(handler), api_key=api_key)
    client.search(SearchRequest(query="q", language="en"))
    client.close()
    for name, value in expected.items():
        assert seen[0][name] == value
    other = "authorization" if not api_key else "x-tavily-access-mode"
    assert other not in seen[0]


def test_markdown_pages_are_reduced_to_their_wording(repository):
    from clear_context.providers.tavily import markdown_to_text

    # Plain-text extraction lost this kind of list-styled fact-check summary entirely.
    markdown = (
        "![](data:image/svg+xml,x)\n\n# Başlık\n\n"
        "[![](data:x)\n\nYazar](/ekibimiz/a)\n\n"
        "**İddia YANLIŞ**\n\n\n\nFotoğraflar Çin’de [videoda](https://v.example/1) görülüyor."
    )
    assert markdown_to_text(markdown) == (
        "Başlık\n\nYazar\n\nİddia YANLIŞ\n\nFotoğraflar Çin’de videoda görülüyor."
    )
    source = ingest(repository)
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={"results": [{"url": "https://example.org/history", "raw_content": markdown}]},
        )

    service = session(repository, handler)
    page = service.read_source(source)
    assert sent[0]["format"] == "markdown"
    assert repository.page(page)["content"].endswith("Fotoğraflar Çin’de videoda görülüyor.")
    service.provider.close()
