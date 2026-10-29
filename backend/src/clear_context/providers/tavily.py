"""Explicit keyless transport; no retries, redirects or credential discovery."""

import json

import httpx

from clear_context.schemas.retrieval import (
    ENDPOINT,
    SearchRequest,
    canonical_source_url,
    parse_response,
)

EXTRACT_ENDPOINT = "https://api.tavily.com/extract"


class RetrievalFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class TavilyKeyless:
    def __init__(self, timeout: float = 45, transport: httpx.BaseTransport | None = None):
        self.client = httpx.Client(
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
        )

    def close(self):
        self.client.close()

    def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            response = self.client.post(
                endpoint, json=payload, headers={"X-Tavily-Access-Mode": "keyless"}
            )
        except httpx.HTTPError as error:
            raise RetrievalFailure("transport_error") from error
        if response.status_code != 200:
            code = "rate_limited" if response.status_code in {429, 432, 433, 434} else "http_error"
            raise RetrievalFailure(code, response.status_code)
        try:
            value = response.json()
            if not isinstance(value, dict):
                raise ValueError("Expected an object.")
            return value
        except (ValueError, TypeError) as error:
            raise RetrievalFailure("invalid_response") from error

    def search(self, request: SearchRequest) -> dict:
        value = self._post(ENDPOINT, request.payload())
        try:
            parse_response(json.dumps(value), request)
        except ValueError as error:
            raise RetrievalFailure("invalid_response") from error
        return value

    @staticmethod
    def extract_payload(url: str) -> dict:
        canonical_source_url(url)
        return {
            "urls": [url],
            "extract_depth": "basic",
            "format": "text",
            "include_images": False,
            "include_usage": True,
        }

    def extract(self, url: str) -> dict:
        value = self._post(EXTRACT_ENDPOINT, self.extract_payload(url))
        results = value.get("results", [])
        failures = value.get("failed_results", [])
        if not isinstance(results, list) or not isinstance(failures, list):
            raise RetrievalFailure("invalid_response")
        if len(results) != 1 or failures:
            raise RetrievalFailure("extract_failed")
        item = results[0]
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("url"), str)
            or item.get("url") != url
            or not isinstance(item.get("raw_content"), str)
            or not item["raw_content"].strip()
        ):
            raise RetrievalFailure("invalid_response")
        return value
