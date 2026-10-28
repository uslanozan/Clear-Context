"""Offline search request, provenance and response-contract checks."""

import json

import pytest
from search_retrieval import (
    SearchRequest,
    bind_plan_queries,
    canonical_source_url,
    deduplicate_jobs,
    parse_response,
)


def plan():
    return {
        "needs": [
            {"id": "n1", "claim_id": "c1", "status": "planned"},
            {"id": "n2", "claim_id": "c2", "status": "planned"},
        ],
        "questions": [
            {
                "question": "What happened?",
                "queries": [
                    {
                        "text": "Example founding date",
                        "language": "en",
                        "need_ids": ["n1", "n2"],
                    }
                ],
            }
        ],
    }


def response(query="Example founding date", results=None):
    return json.dumps(
        {
            "query": query,
            "results": results
            if results is not None
            else [
                {
                    "title": "Example",
                    "url": "https://example.org/page",
                    "content": "A candidate excerpt.",
                    "score": 0.8,
                }
            ],
            "usage": {"credits": 1},
            "request_id": "recorded-id",
            "answer": None,
        }
    )


def test_keyless_request_disables_unrequested_work_and_has_no_credentials():
    request = SearchRequest(query="Example founding date", language="en")
    payload = request.payload()
    assert payload["query"] == request.query
    assert payload["search_depth"] == "basic"
    assert not payload["auto_parameters"] and not payload["include_answer"]
    assert not payload["include_raw_content"] and not payload["include_images"]
    assert not {"api_key", "authorization", "token"} & payload.keys()
    assert "start_date" not in payload and "end_date" not in payload


@pytest.mark.parametrize(
    "field,value", [("language", "es"), ("max_results", 0), ("query", "   ")]
)
def test_invalid_requests_fail_before_network(field, value):
    data = {"query": "Example founding date", "language": "en", field: value}
    with pytest.raises(ValueError):
        SearchRequest.model_validate(data)


def test_cache_identity_includes_language_and_result_limit():
    request = SearchRequest(query="Example founding date", language="en")
    assert request.cache_key != request.model_copy(update={"language": "tr"}).cache_key
    assert request.cache_key != request.model_copy(update={"max_results": 3}).cache_key
    assert (
        request.cache_key
        != request.model_copy(update={"query": "Example  founding date"}).cache_key
    )


def test_identical_queries_share_request_but_preserve_all_case_bindings():
    jobs = bind_plan_queries("first", plan()) + bind_plan_queries("second", plan())
    unique = deduplicate_jobs(jobs + jobs)
    assert len(unique) == 1
    assert len(unique[0]["bindings"]) == 2
    assert {b["plan_case_id"] for b in unique[0]["bindings"]} == {"first", "second"}
    assert unique[0]["bindings"][0]["claim_ids"] == ["c1", "c2"]


@pytest.mark.parametrize(
    "need_ids,status",
    [(["unknown"], "planned"), (["n1", "n1"], "planned"), (["n1"], "needs_context")],
)
def test_unknown_duplicate_or_deferred_query_bindings_are_rejected(need_ids, status):
    value = plan()
    value["needs"][0]["status"] = status
    value["questions"][0]["queries"][0]["need_ids"] = need_ids
    with pytest.raises(ValueError):
        bind_plan_queries("first", value)


def test_url_identity_removes_tracking_but_retains_meaningful_parameters():
    assert (
        canonical_source_url("https://EXAMPLE.org/item?id=12&utm_source=test#part")
        == "https://example.org/item?id=12"
    )
    assert canonical_source_url(
        "https://example.org/item?id=12"
    ) != canonical_source_url("https://example.org/item?id=13")


@pytest.mark.parametrize(
    "url",
    ["javascript:alert(1)", "file:///private", "https://user:pass@example.org/item"],
)
def test_unsafe_report_links_are_rejected(url):
    with pytest.raises(ValueError):
        canonical_source_url(url)


def test_response_does_not_invent_publication_date_or_truth_labels():
    result = parse_response(
        response(), SearchRequest(query="Example founding date", language="en")
    )
    assert result.results[0].published_date is None
    assert (
        "verdict" not in result.model_dump()
        and "confidence" not in result.results[0].model_dump()
    )
    assert result.usage == {"credits": 1}


def test_empty_search_is_valid_but_not_a_false_claim_verdict():
    result = parse_response(
        response(results=[]),
        SearchRequest(query="Example founding date", language="en"),
    )
    assert result.results == []


def test_mismatched_query_and_oversized_result_list_are_rejected():
    request = SearchRequest(query="Example founding date", language="en", max_results=1)
    with pytest.raises(ValueError, match="differs"):
        parse_response(response(query="Different query"), request)
    item = {"title": "Example", "url": "https://example.org/"}
    with pytest.raises(ValueError, match="more results"):
        parse_response(response(results=[item, item]), request)
