import json

import httpx

from clear_context.core.settings import Settings, load_model_selections
from clear_context.providers.meta import MetaInvestigationProvider


def run(items):
    settings = Settings(
        _env_file=None,
        app_mode="meta",
        allow_paid_api_calls=True,
        meta_api_key="synthetic-test-key",
        model_default="spark_1_3",
        prompt_claim_extraction="d_v1",
    )

    def handler(request):
        payload = json.loads(request.content)
        assert payload["reasoning_effort"] == "low"
        assert payload["messages"][0]["role"] == "system"
        assert json.loads(payload["messages"][1]["content"])["source"] == "A source claim."
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": json.dumps({"extractions": items})},
                    }
                ],
                "usage": {},
            },
        )

    provider = MetaInvestigationProvider(
        settings,
        load_model_selections(settings)["claim_extraction"],
        transport=httpx.MockTransport(handler),
    )
    return provider.extract_claims("A source claim.")


def item(quote):
    return {
        "claim": quote,
        "claim_attributes": {"statement": "A self-contained statement.", "group": "Source topic"},
    }


def test_direct_preserves_group_and_literal_span():
    result = run([item("A source claim.")])
    assert result.claims[0].group == "Source topic"
    assert result.claims[0].source_span.text == "A source claim."
    assert result.coverage.status == "processed"


def test_direct_empty_requires_review():
    result = run([])
    assert not result.claims
    assert result.coverage.status == "partial"
    assert "Empty extraction" in " ".join(result.coverage.notes)


def test_direct_bad_quote_retains_valid_claim_and_marks_partial():
    result = run([item("A source claim."), item("Invented source.")])
    assert len(result.claims) == 1
    assert result.coverage.status == "partial"
