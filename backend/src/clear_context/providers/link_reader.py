"""Read links found in the user's text: page text, title, main image and publication date.

Pages are read through Tavily, so this server never fetches a user-supplied page. The only
direct request is the image download, which accepts public HTTPS addresses only.
"""

import ipaddress
import re
import socket
from dataclasses import dataclass, field
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit

import httpx

from clear_context.providers.tavily import EXTRACT_ENDPOINT, markdown_to_text
from clear_context.schemas.retrieval import ENDPOINT as SEARCH_ENDPOINT
from clear_context.schemas.retrieval import canonical_source_url
from clear_context.services.media import IMAGE_LIMIT, sniff

MAX_LINKS = 3
# Only the start of a page is checked: the headline, lead and first paragraphs carry its main
# claims, while a whole article produced more claims than one research budget can assess.
MAX_TEXT_CHARS = 3000
URL = re.compile(r"https?://[^\s<>\"'`]+", re.IGNORECASE)
TRAILING = ".,;:!?)]}»”’'\""


class LinkFailure(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass
class LinkPage:
    url: str
    title: str | None
    text: str
    truncated: bool
    images: list[str] = field(default_factory=list)
    published_on: date | None = None


def find_links(text: str, limit: int = MAX_LINKS) -> list[str]:
    """HTTP(S) addresses in the text, in order, without trailing punctuation or duplicates."""
    found = []
    for match in URL.findall(text or ""):
        url = match.rstrip(TRAILING)
        try:
            canonical_source_url(url)
        except ValueError:
            continue
        if url not in found:
            found.append(url)
        if len(found) >= limit:
            break
    return found


def host_label(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
    return host or None


def same_page(first: str, second: str) -> bool:
    def key(url):
        parts = urlsplit(canonical_source_url(url))
        return (parts.netloc.removeprefix("www."), parts.path.rstrip("/"), parts.query)

    try:
        return key(first) == key(second)
    except ValueError:
        return False


def parse_published(value) -> date | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return parsedate_to_datetime(value).date()
    except (TypeError, ValueError):
        pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def public_address(host: str) -> str | None:
    """One address of the host when every address it resolves to is public, else None."""
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError):
        return None
    addresses = sorted({info[4][0] for info in infos})
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        return None
    return addresses[0]


def pinned_url(parts, address: str) -> str:
    """The URL with its host replaced by the checked address (IPv6 in brackets)."""
    host = f"[{address}]" if ":" in address else address
    port = f":{parts.port}" if parts.port else ""
    query = f"?{parts.query}" if parts.query else ""
    return f"https://{host}{port}{parts.path or '/'}{query}"


class TavilyLinkReader:
    def __init__(
        self,
        api_key: str = "",
        timeout: float = 45,
        transport: httpx.BaseTransport | None = None,
        resolver=public_address,
    ):
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self.client = httpx.Client(
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
            headers=headers,
        )
        self.resolver = resolver

    def close(self):
        self.client.close()

    def _post(self, endpoint: str, payload: dict) -> dict:
        try:
            response = self.client.post(endpoint, json=payload)
        except httpx.HTTPError as error:
            raise LinkFailure("transport_error") from error
        if response.status_code != 200:
            raise LinkFailure("rate_limited" if response.status_code == 429 else "http_error")
        try:
            body = response.json()
        except ValueError as error:
            raise LinkFailure("invalid_response") from error
        if not isinstance(body, dict):
            raise LinkFailure("invalid_response")
        return body

    def read(self, url: str) -> LinkPage:
        """Read with basic extraction, then once with Tavily's advanced extraction if needed.

        Measured: Reddit posts failed basic extraction but read with advanced; Facebook and
        Instagram posts failed both. Advanced costs more credits, so it runs only on failure.
        """
        try:
            return self._read(url, "basic")
        except LinkFailure as error:
            if error.code not in {"unreadable", "invalid_response"}:
                raise
            return self._read(url, "advanced")

    def _read(self, url: str, depth: str) -> LinkPage:
        body = self._post(
            EXTRACT_ENDPOINT,
            {
                "urls": [url],
                "extract_depth": depth,
                "format": "markdown",
                "include_images": True,
            },
        )
        results = body.get("results") or []
        item = results[0] if results and isinstance(results[0], dict) else {}
        raw = item.get("raw_content")
        text = markdown_to_text(raw) if isinstance(raw, str) else ""
        if not text:
            raise LinkFailure("unreadable")
        title = item.get("title") if isinstance(item.get("title"), str) else None
        images = [
            urljoin(url, image)
            for image in item.get("images") or []
            if isinstance(image, str) and urljoin(url, image).startswith("https://")
        ]
        return LinkPage(
            url=url,
            title=title.strip() if title and title.strip() else None,
            text=text[:MAX_TEXT_CHARS],
            truncated=len(text) > MAX_TEXT_CHARS,
            images=list(dict.fromkeys(images)),
        )

    def published_on(self, page: LinkPage) -> date | None:
        """The date a news search index reports for this exact page, if any; never guessed."""
        if not page.title:
            return None
        try:
            body = self._post(
                SEARCH_ENDPOINT,
                {
                    "query": page.title[:400],
                    "topic": "news",
                    "max_results": 5,
                    "include_answer": False,
                    "include_raw_content": False,
                },
            )
        except LinkFailure:
            return None
        for result in body.get("results") or []:
            if isinstance(result, dict) and same_page(result.get("url", ""), page.url):
                return parse_published(result.get("published_date"))
        return None

    def download_image(self, url: str, max_redirects: int = 3) -> tuple[str, bytes]:
        """Fetch one image from a public HTTPS address; returns (mime type, data)."""
        for _ in range(max_redirects + 1):
            parts = urlsplit(url)
            if parts.scheme != "https" or not parts.hostname or parts.username:
                raise LinkFailure("image_address_rejected")
            address = self.resolver(parts.hostname)
            if not address:
                raise LinkFailure("image_address_rejected")
            # Connect to the address that was checked, so a second DNS answer cannot point the
            # request at a private host. TLS still verifies the certificate for the host name.
            try:
                with self.client.stream(
                    "GET",
                    pinned_url(parts, address),
                    headers={"Accept": "image/*", "Host": parts.netloc},
                    extensions={"sni_hostname": parts.hostname},
                ) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        url = urljoin(url, response.headers.get("location", ""))
                        continue
                    if response.status_code != 200:
                        raise LinkFailure("image_http_error")
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if len(data) > IMAGE_LIMIT:
                            raise LinkFailure("image_too_large")
            except httpx.HTTPError as error:
                raise LinkFailure("image_transport_error") from error
            detected = sniff(bytes(data))
            if not detected or detected[0] != "image":
                raise LinkFailure("image_type_rejected")
            return detected[1], bytes(data)
        raise LinkFailure("image_too_many_redirects")


def build_link_reader(settings) -> TavilyLinkReader:
    return TavilyLinkReader(settings.tavily_api_key.get_secret_value())
