import json
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from clear_context.core.settings import Settings, load_model_selections
from clear_context.main import create_app
from clear_context.providers.errors import ProviderError
from clear_context.providers.meta import MetaInvestigationProvider


def meta_settings(**overrides):
    values = {
        "app_mode": "meta",
        "allow_paid_api_calls": True,
        "meta_api_key": "synthetic-test-key",
        "model_default": "spark_1_3",
        "prompt_claim_extraction": "v1",
    }
    return Settings(_env_file=None, **(values | overrides))


def completion(claims=None, **overrides):
    body = {
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "content": json.dumps({"claims": claims or ["A synthetic claim."]}),
                    "refusal": None,
                },
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }
    return body | overrides


def provider_with(handler, **settings_overrides):
    settings = meta_settings(**settings_overrides)
    return MetaInvestigationProvider(
        settings, load_model_selections(settings)["claim_extraction"], httpx.MockTransport(handler)
    )


def test_meta_request_uses_configured_model_schema_and_limits():
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://api.meta.ai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer synthetic-test-key"
        payload = json.loads(request.content)
        assert payload["model"] == "muse-wonder-1.0"
        assert payload["max_completion_tokens"] == 256
        assert payload["store"] is False
        assert "tools" not in payload
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["response_format"]["json_schema"]["schema"]["additionalProperties"] is False
        assert payload["messages"][1]["content"] == "A synthetic claim."
        assert "Return at most 8 unique claims." in payload["messages"][0]["content"]
        return httpx.Response(200, json=completion())

    provider = provider_with(
        handler, model_claim_extraction="wonder", meta_max_completion_tokens=256
    )
    result = provider.extract_claims("A synthetic claim.")
    assert len(calls) == 1
    assert result.claims[0].text == "A synthetic claim."
    assert result.model_usage[0].input_tokens == 100
    assert result.model_usage[0].output_tokens == 20
    assert result.model_usage[0].model_id == "muse-wonder-1.0"
    assert result.model_usage[0].prompt_version == "v1"
    assert result.model_usage[0].prompt_sha256 == provider.prompt.sha256


@pytest.mark.parametrize(
    "overrides",
    [
        {"allow_paid_api_calls": False},
        {"meta_api_key": ""},
        {"app_mode": "mock"},
    ],
)
def test_paid_call_guard(overrides):
    with pytest.raises(ValueError, match="opt-in"):
        provider_with(lambda request: pytest.fail("No request expected"), **overrides)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "meta_authentication_failed"),
        (403, "meta_access_denied"),
        (429, "meta_rate_limited"),
        (500, "meta_request_failed"),
        (302, "meta_request_failed"),
    ],
)
def test_http_errors_are_sanitized_and_retried_only_when_transient(status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="private-error-and-key",
            headers={
                "Location": "https://untrusted.example/collect",
            },
        )

    with pytest.raises(ProviderError) as error:
        provider_with(handler).extract_claims("A synthetic claim.")
    assert str(error.value) == code
    assert "private-error-and-key" not in str(error.value)
    # 429 and 5xx are retried twice; other failures are final.
    assert len(calls) == (3 if status in {429, 500} else 1)


@pytest.mark.parametrize(
    "exception,code",
    [
        (httpx.ReadTimeout, "meta_timeout"),
        (httpx.ConnectError, "meta_connection_failed"),
    ],
)
def test_transport_errors_are_sanitized(exception, code):
    calls = []

    def handler(request):
        calls.append(request)
        raise exception("private transport error", request=request)

    with pytest.raises(ProviderError, match=code):
        provider_with(handler).extract_claims("A synthetic claim.")
    # A failed connection never reached Meta and is retried; a read timeout may have been
    # processed and billed, so it is not.
    assert len(calls) == (3 if exception is httpx.ConnectError else 1)


@pytest.mark.parametrize(
    "body,code",
    [
        ({"choices": []}, "meta_invalid_response"),
        (completion(["Invented text"]), "meta_ungrounded_claim"),
        (completion(["A synthetic claim.", "A synthetic claim."]), "meta_invalid_response"),
        (
            {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]},
            "meta_incomplete_output",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"refusal": "No", "content": None}}]},
            "meta_refused",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": "not-json"}}]},
            "meta_invalid_response",
        ),
    ],
)
def test_bad_model_outputs_fail_closed(body, code):
    with pytest.raises(ProviderError, match=code):
        provider_with(lambda request: httpx.Response(200, json=body)).extract_claims(
            "A synthetic claim."
        )


def test_missing_usage_is_unknown_not_zero():
    body = completion()
    body.pop("usage")
    result = provider_with(lambda request: httpx.Response(200, json=body)).extract_claims(
        "A synthetic claim."
    )
    assert result.model_usage[0].input_tokens is None


def test_meta_evaluation_never_calls_model_without_sources():
    provider = provider_with(lambda request: pytest.fail("No evaluation call expected"))
    from clear_context.domain.investigation import Claim

    report = provider.evaluate_evidence(uuid4(), [Claim(id=uuid4(), text="A claim.")])
    assert report.mode == "meta"
    assert report.sources == report.evidence == []
    assert report.findings[0].assessment == "unresolved"


def test_meta_api_flow_persists_usage_and_mode(settings):
    settings.app_mode = "meta"
    settings.allow_paid_api_calls = True
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.service.runtime.provider.transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=completion())
        )
        created = client.post("/api/investigations", json={"text": "A synthetic claim."})
        assert created.status_code == 202
        assert created.json()["mode"] == "meta"
        location = created.headers["location"]
        report = client.get(location + "/report").json()
        assert report["mode"] == "meta"
        assert report["model_usage"][0]["output_tokens"] == 20
        assert report["model_usage"][0]["prompt_version"] == "v1"
        assert len(report["model_usage"][0]["prompt_sha256"]) == 64
        assert client.get(location).json()["model_usage"] == report["model_usage"]
        assert client.get("/api/health").json()["paid_api_calls_enabled"] is True
    settings.app_mode = "mock"
    with TestClient(create_app(settings)) as client:
        assert client.get(location + "/report").json() == report


def test_meta_error_code_reaches_api_without_body(settings):
    settings.app_mode = "meta"
    settings.allow_paid_api_calls = True
    app = create_app(settings)
    with TestClient(app) as client:
        app.state.service.runtime.provider.transport = httpx.MockTransport(
            lambda request: httpx.Response(429, text="private provider body")
        )
        response = client.post("/api/investigations", json={"text": "A synthetic claim."})
        state = client.get(response.headers["location"])
        assert state.json()["status"] == "failed"
        assert state.json()["error_code"] == "meta_rate_limited"
        assert "private provider body" not in state.text


def test_usage_survives_failure_after_successful_extraction(settings):
    settings.app_mode = "meta"
    settings.allow_paid_api_calls = True
    app = create_app(settings)
    with TestClient(app) as client:
        provider = app.state.service.runtime.provider
        provider.transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json=completion())
        )

        def fail_evaluation(*args):
            raise RuntimeError("private evaluation error")

        provider.evaluate_evidence = fail_evaluation
        response = client.post("/api/investigations", json={"text": "A synthetic claim."})
        state = client.get(response.headers["location"]).json()
        assert state["status"] == "failed"
        assert state["model_usage"][0]["input_tokens"] == 100
        assert client.get(response.headers["location"] + "/report").status_code == 409
