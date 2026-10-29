"""Bounded Meta structured-output transport without retries or credential logging."""

import json
from hashlib import sha256

import httpx

from clear_context.core.settings import Settings


class ModelResponseFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class MetaStructuredProvider:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if (
            settings.app_mode != "meta"
            or not settings.allow_paid_api_calls
            or not settings.meta_api_key.get_secret_value()
        ):
            raise ValueError("Live inference requires Meta mode, paid-call opt-in and an API key.")
        self.settings = settings
        self.transport = transport
        self.response_metadata: list[dict] = []
        self.response_records: list[dict] = []

    async def complete(self, payload: dict, timeout: float) -> dict:
        try:
            async with httpx.AsyncClient(
                transport=self.transport or httpx.AsyncHTTPTransport(retries=0),
                timeout=timeout,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    "https://api.meta.ai/v1/chat/completions",
                    json=payload,
                    headers={
                        "Authorization": "Bearer " + self.settings.meta_api_key.get_secret_value()
                    },
                )
        except httpx.HTTPError as error:
            raise ModelResponseFailure("transport_error") from error
        fingerprint = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        self.response_records.append(
            {
                "request_sha256": fingerprint,
                "status_code": response.status_code,
                "raw_response": response.text,
            }
        )
        self.response_metadata.append(
            {
                "request_sha256": fingerprint,
                "status_code": response.status_code,
                "rate_limit_headers": {
                    name: response.headers[name]
                    for name in (
                        "x-ratelimit-limit-tokens",
                        "x-ratelimit-remaining-tokens",
                        "x-ratelimit-limit-requests",
                        "x-ratelimit-remaining-requests",
                        "retry-after",
                    )
                    if name in response.headers
                },
            }
        )
        if response.status_code != 200:
            code = "rate_limited" if response.status_code == 429 else "model_request_failed"
            raise ModelResponseFailure(code, response.status_code)
        try:
            body = response.json()
            choice = body["choices"][0]
            message = choice["message"]
            if (
                choice["finish_reason"] != "stop"
                or message.get("refusal")
                or message.get("tool_calls")
            ):
                raise ValueError("Incomplete response.")
            if not isinstance(message.get("content"), str):
                raise ValueError("Missing structured content.")
            return body
        except (ValueError, KeyError, TypeError, IndexError) as error:
            raise ModelResponseFailure("invalid_model_response") from error
