"""Tavily Search/Extract transport; no retries, redirects or credential discovery.

Uses an API key when one is configured, otherwise the rate-limited keyless mode.
"""

import json
import re

import httpx

from clear_context.schemas.retrieval import (
    ENDPOINT,
    SearchRequest,
    canonical_source_url,
    parse_response,
)

EXTRACT_ENDPOINT = "https://api.tavily.com/extract"

# Plain text extraction dropped whole article bodies on some sites (for example list-styled
# fact-check summaries), so pages are requested as Markdown and reduced to readable text.
# A link target is a URL without spaces (balanced parentheses allowed, as in Wikipedia
# addresses), optionally followed by a quoted title.
TARGET = r'\(\s*<?(?:[^\s()<>]|\([^\s()]*\))*>?(?:\s+"[^"]*")?\s*\)'
IMAGE = re.compile(r"!\[[^\]]*\]" + TARGET)
LINK = re.compile(r"\[([^\]]*)\]" + TARGET)
HEADING = re.compile(r"^#{1,6}\s+", re.MULTILINE)
EMPHASIS = re.compile(r"(\*\*|__)(.+?)\1")
BLANK_LINES = re.compile(r"\n{3,}")
BULLET = re.compile(r"^\s*[*+-]\s+(.*)$")
# Menus and language pickers are runs of short list items. Short lists inside an article
# can be evidence (for example member cities), so after the first body paragraph only long
# runs are removed.
MENU_ITEM_WORDS = 3
HEADER_MENU_RUN = 3
BODY_MENU_RUN = 7
BODY_PARAGRAPH_WORDS = 20


def drop_menus(lines: list[str]) -> list[str]:
    """Remove menu-like runs of short list items and repeated adjacent lines."""
    kept, run = [], []
    in_body = False

    def flush():
        if len(run) < (BODY_MENU_RUN if in_body else HEADER_MENU_RUN):
            kept.extend(run)
        run.clear()

    for line in lines:
        item = BULLET.match(line)
        if item and len(item.group(1).split()) <= MENU_ITEM_WORDS:
            run.append(line)
            continue
        flush()
        if not item and len(line.split()) >= BODY_PARAGRAPH_WORDS:
            in_body = True
        # Pages often repeat a caption or author name on the next line.
        if line.strip() and kept and line.strip() == kept[-1].strip():
            continue
        kept.append(line)
    flush()
    return kept


def markdown_to_text(markdown: str) -> str:
    """Drop images, link targets, heading and bold marks and menus; keep the wording."""
    text = IMAGE.sub("", markdown)
    # Links can nest images; repeat until no link syntax is left.
    previous = None
    while previous != text:
        previous, text = text, LINK.sub(r"\1", text)
    text = HEADING.sub("", text)
    text = EMPHASIS.sub(r"\2", text)
    lines = drop_menus([line.rstrip() for line in text.split("\n")])
    return BLANK_LINES.sub("\n\n", "\n".join(lines)).strip()


class RetrievalFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class TavilyClient:
    def __init__(
        self,
        timeout: float = 45,
        transport: httpx.BaseTransport | None = None,
        api_key: str = "",
    ):
        # The key is only ever sent as a request header; never logged or cached.
        self.headers = (
            {"Authorization": f"Bearer {api_key}"}
            if api_key
            else {"X-Tavily-Access-Mode": "keyless"}
        )
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
            response = self.client.post(endpoint, json=payload, headers=self.headers)
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
            "format": "markdown",
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
        item["raw_content"] = markdown_to_text(item["raw_content"])
        if not item["raw_content"]:
            raise RetrievalFailure("extract_failed")
        return value
