import asyncio

import httpx

from clear_context.core.retry import retry_delay, should_retry_error, should_retry_status
from clear_context.core.settings import Settings
from clear_context.providers.meta_structured import MetaStructuredProvider


def test_retry_rules():
    assert should_retry_status(429, 0) and should_retry_status(503, 1)
    assert not should_retry_status(429, 2)  # at most two retries
    assert not should_retry_status(400, 0) and not should_retry_status(432, 0)
    request = httpx.Request("POST", "https://example.org")
    assert should_retry_error(httpx.ConnectError("x", request=request), 0, paid=True)
    assert not should_retry_error(httpx.ReadTimeout("x", request=request), 0, paid=True)
    assert should_retry_error(httpx.ReadTimeout("x", request=request), 0, paid=False)


def test_retry_after_is_honoured_and_capped(monkeypatch):
    from clear_context.core import retry

    monkeypatch.setattr(retry, "MAX_RETRY_AFTER", 20.0)
    assert retry_delay(0, httpx.Response(429, headers={"retry-after": "5"})) == 5.0
    assert retry_delay(0, httpx.Response(429, headers={"retry-after": "600"})) == 20.0


def test_structured_provider_recovers_after_a_transient_failure():
    answers = [httpx.Response(503), httpx.Response(429)]
    body = {
        "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
        "usage": {},
    }

    def handler(request):
        return answers.pop(0) if answers else httpx.Response(200, json=body)

    settings = Settings(
        _env_file=None, app_mode="meta", allow_paid_api_calls=True, meta_api_key="k"
    )
    provider = MetaStructuredProvider(settings, transport=httpx.MockTransport(handler))
    assert asyncio.run(provider.complete({"model": "m"}, 5)) == body
    assert provider.retries == 2
