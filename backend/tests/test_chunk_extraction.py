import json

import httpx
import pytest
from fastapi.testclient import TestClient

from clear_context.core.settings import Settings, load_model_selections
from clear_context.main import create_app
from clear_context.providers.meta import MetaInvestigationProvider
from clear_context.services.text_chunks import (
    TextChunk,
    context_ranges,
    locate_quote,
    partition,
    visible_ranges,
)


def configured(**overrides):
    return Settings(
        _env_file=None,
        **(
            {
                "app_mode": "meta",
                "allow_paid_api_calls": True,
                "meta_api_key": "synthetic-key",
                "prompt_claim_extraction": "v2",
                "extraction_chunk_characters": 400,
                "extraction_min_chunk_characters": 80,
            }
            | overrides
        ),
    )


def model_claim(quote, statement=None, context_quotes=None, context_status="standalone"):
    return {
        "quote": quote,
        "statement": statement or quote,
        "context_quotes": context_quotes or [],
        "context_status": context_status,
    }


def completion(claims, has_more=False, finish="stop", output_tokens=20):
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": finish,
                    "message": {"content": json.dumps({"claims": claims, "has_more": has_more})},
                }
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": output_tokens},
        },
    )


def provider(handler, **overrides):
    settings = configured(**overrides)
    return MetaInvestigationProvider(
        settings, load_model_selections(settings)["claim_extraction"], httpx.MockTransport(handler)
    )


@pytest.mark.parametrize(
    "text",
    [
        "Short text.",
        "First paragraph.\n\n" * 100,
        "A. " * 1000,
        "x" * 1600,
        "😀 a numerical claim 123. A second sentence. " * 60,
    ],
)
def test_partition_preserves_every_character_without_gaps(text):
    chunks = partition(text, 400)
    assert chunks[0].start == 0 and chunks[-1].end == len(text)
    assert all(0 < chunk.end - chunk.start <= 400 for chunk in chunks)
    assert all(left.end == right.start for left, right in zip(chunks, chunks[1:], strict=False))
    assert "".join(text[chunk.start : chunk.end] for chunk in chunks) == text


def test_quote_locations_use_original_unicode_coordinates():
    text = "😀 Marie Curie. She won in 1911."
    span = locate_quote(text, "She won in 1911.", [TextChunk(0, len(text))])
    assert span.start == 15
    assert text[span.start : span.end] == span.text
    assert context_ranges(text, TextChunk(15, len(text)), 0) == []
    with pytest.raises(ValueError):
        locate_quote(text, "She won in 1921.", [TextChunk(0, len(text))])


def test_boundary_quote_must_be_visible_and_overlap_the_target():
    text = "A first sentence. A second sentence."
    chunk = TextChunk(25, len(text))
    visible = visible_ranges([TextChunk(18, 25), chunk])
    assert locate_quote(text, "A second sentence.", visible, overlaps=chunk).start == 18
    with pytest.raises(ValueError):
        locate_quote(text, "A first sentence.", visible, overlaps=chunk)
    with pytest.raises(ValueError):
        locate_quote(text, "A first sentence.", [TextChunk(0, 18), chunk], overlaps=chunk)


def test_context_is_separate_and_normalized_statement_keeps_original_quote():
    text = "Marie Curie was a scientist. She won in 1911."

    def handler(request):
        payload = json.loads(request.content)
        data = json.loads(payload["messages"][1]["content"])
        assert data["target"] == text
        assert "context" in data
        return completion(
            [
                model_claim(
                    "She won in 1911.",
                    "Marie Curie won in 1911.",
                    ["Marie Curie was a scientist."],
                    "context_linked",
                )
            ]
        )

    result = provider(handler).extract_claims(text)
    claim = result.claims[0]
    assert claim.statement == "Marie Curie won in 1911."
    assert claim.text == "She won in 1911."
    assert claim.context_spans[0].start == 0
    assert claim.source_span.start == text.index("She")
    assert result.coverage.status == "processed"


def test_capacity_splits_a_range_instead_of_capping_the_document():
    text = "First fact. Second fact. Third fact. Fourth fact. " * 17

    def handler(request):
        data = json.loads(json.loads(request.content)["messages"][1]["content"])
        target = data["target"]
        quotes = [model_claim(target.strip())]
        if len(target) > 180:
            quotes.append(model_claim(target.strip(), "A second distinct statement."))
        return completion(quotes)

    result = provider(handler, extraction_response_capacity=2).extract_claims(text)
    assert len(result.claims) > 2
    assert result.coverage.status == "processed"
    assert any(chunk.status == "split" for chunk in result.coverage.chunks)
    assert any(usage.outcome == "capacity_reached" for usage in result.model_usage)
    leaves = [chunk for chunk in result.coverage.chunks if chunk.status != "split"]
    assert sum(chunk.end - chunk.start for chunk in leaves) == len(text)


def test_truncated_parent_usage_survives_successful_smaller_ranges():
    calls = []

    def handler(request):
        target = json.loads(json.loads(request.content)["messages"][1]["content"])["target"]
        calls.append(target)
        return completion(
            [model_claim(target.strip())], finish="length" if len(calls) == 1 else "stop"
        )

    result = provider(handler).extract_claims("A full source sentence. " * 14)
    assert result.coverage.status == "processed"
    assert result.model_usage[0].outcome == "truncated"
    assert len(result.model_usage) == len(calls)
    assert len(calls) == 3


@pytest.mark.parametrize(
    "limit", [{"extraction_max_calls": 1}, {"extraction_max_output_tokens": 128}]
)
def test_budget_returns_partial_coverage_instead_of_silent_success(limit):
    result = provider(lambda request: completion([model_claim("A fact.")]), **limit).extract_claims(
        "A fact. " * 140
    )
    assert result.coverage.status == "partial"
    assert result.coverage.model_calls == 1
    assert any(chunk.reason == "budget_exhausted" for chunk in result.coverage.chunks)


def test_unsplittable_capacity_is_explicitly_partial():
    result = provider(
        lambda request: completion([model_claim("One fact.")], has_more=True)
    ).extract_claims("One fact. Another fact.")
    assert result.coverage.status == "partial"
    assert result.coverage.chunks[0].reason == "response_capacity"
    assert result.claims[0].text == "One fact."


@pytest.mark.parametrize(
    "claim",
    [
        model_claim("Invented source text."),
        model_claim("A fact.", context_quotes=["Invented context."]),
        model_claim("A fact.", context_status="context_linked"),
    ],
)
def test_unanchored_quotes_or_unsupported_context_are_rejected(claim):
    result = provider(lambda request: completion([claim])).extract_claims("A fact.")
    assert result.claims == []
    assert result.coverage.status == "partial"
    assert result.model_usage[0].outcome == "invalid"


def test_repeated_source_quote_is_marked_ambiguous():
    result = provider(lambda request: completion([model_claim("A fact.")])).extract_claims(
        "A fact. A fact."
    )
    assert result.claims[0].source_span.start == 0
    assert result.claims[0].context_status == "ambiguous"


def test_service_error_stops_without_retry_and_marks_remaining_ranges():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(429, text="private body")

    result = provider(handler).extract_claims("A fact. " * 150)
    assert len(calls) == 1
    assert result.coverage.status == "partial"
    assert all(chunk.reason == "meta_rate_limited" for chunk in result.coverage.chunks)
    assert "private body" not in result.model_dump_json()


def test_v2_provenance_and_partial_scope_round_trip(settings):
    settings.app_mode = "meta"
    settings.allow_paid_api_calls = True
    settings.prompt_claim_extraction = "v2"
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.service.provider.transport = httpx.MockTransport(
            lambda request: completion([model_claim("A fact.")], has_more=True)
        )
        created = client.post("/api/investigations", json={"text": "A fact."})
        location = created.headers["location"]
        report = client.get(location + "/report").json()
        assert report["claims"][0]["source_span"] == {"start": 0, "end": 7, "text": "A fact."}
        assert report["extraction_coverage"]["status"] == "partial"
        assert any("partial" in line for line in report["limitations"])
    with TestClient(create_app(settings)) as client:
        assert client.get(location + "/report").json() == report


def test_nonfactual_v2_input_can_finish_without_fabricated_claims(settings):
    settings.app_mode = "meta"
    settings.allow_paid_api_calls = True
    settings.prompt_claim_extraction = "v2"
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.service.provider.transport = httpx.MockTransport(lambda request: completion([]))
        created = client.post("/api/investigations", json={"text": "Please help?"})
        report = client.get(created.headers["location"] + "/report").json()
        assert report["claims"] == report["findings"] == []
        assert report["extraction_coverage"]["status"] == "processed"
