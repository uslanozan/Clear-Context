"""Meta structured paragraph selection with explicit live-call authorization."""

import json
from hashlib import sha256

import httpx

from clear_context.core.settings import Settings
from clear_context.schemas.passage_selection import response_schema
from clear_context.services.paragraphs import Paragraph


def build_selection_request(
    system: str,
    page: dict,
    needs: list[dict],
    claims: list[dict],
    items: list[Paragraph],
    allowed: dict[str, list[str]],
    *,
    model: str = "muse-spark-1.3",
    effort: str = "low",
    max_completion_tokens: int = 4096,
    response_contract: str = "legacy_v1",
) -> dict:
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source_url": page["url"],
                        "needs": needs,
                        "claims": claims,
                        "allowed_paragraph_ids_by_need": allowed,
                        "paragraphs": [{"id": p.id, "text": p.text} for p in items],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "passage_selection",
                "strict": True,
                "schema": response_schema(response_contract),
            },
        },
        "reasoning_effort": effort,
        "max_completion_tokens": max_completion_tokens,
        "store": False,
        "stream": False,
    }


class SelectionFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class MetaPassageProvider:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        if (
            settings.app_mode != "meta"
            or not settings.allow_paid_api_calls
            or not settings.meta_api_key.get_secret_value()
        ):
            raise ValueError("Live selection requires Meta mode, paid-call opt-in and an API key.")
        self.settings = settings
        self.transport = transport
        self.response_metadata: list[dict] = []
        self.response_records: list[dict] = []

    async def select(self, payload: dict, timeout: float) -> dict:
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
            raise SelectionFailure("transport_error") from error
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
            raise SelectionFailure(code, response.status_code)
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
            raise SelectionFailure("invalid_model_response") from error
