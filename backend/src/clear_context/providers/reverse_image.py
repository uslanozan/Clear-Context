"""Reverse image search adapters behind one interface.

A provider returns pages where the same or a similar image appears. A match is a lead
for reading those pages, not proof of an image's original source or date.
"""

import html
import io
import re
from datetime import date, datetime
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from PIL import Image, UnidentifiedImageError

from clear_context.domain.investigation import ImageMatch, MediaOrigin
from clear_context.domain.source_types import FACT_CHECK_HOSTS


class ReverseImageFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class ReverseImageSearch(Protocol):
    name: str

    def search(self, data: bytes, mime_type: str) -> MediaOrigin: ...

    def close(self) -> None: ...


def shrink_image(data: bytes, max_bytes: int) -> bytes:
    """Re-encode as JPEG, reducing quality and size until it fits; the stored file is unchanged."""
    if len(data) <= max_bytes:
        return data
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as error:
        raise ReverseImageFailure("image_unreadable") from error
    image = image.convert("RGB")
    for side in (1600, 1200, 900, 640):
        image.thumbnail((side, side))
        for quality in (85, 70, 55):
            buffer = io.BytesIO()
            image.save(buffer, format="JPEG", quality=quality)
            if buffer.tell() <= max_bytes:
                return buffer.getvalue()
    raise ReverseImageFailure("image_too_large")


def parse_display_date(value) -> date | None:
    """Parse dates such as "Feb 12, 2025"; relative or partial dates stay unparsed."""
    if not isinstance(value, str):
        return None
    for pattern in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date()
        except ValueError:
            continue
    return None


def _text(item: dict, key: str) -> str | None:
    value = item.get(key)
    return value if isinstance(value, str) and value.strip() else None


def public_copies(matches: list[ImageMatch], limit: int = 2) -> list[str]:
    """Image URLs of same-image matches; Google-hosted thumbnails are preferred.

    Services that only accept an image URL are queried with these copies, so the user's
    upload is never published.
    """
    urls = [
        m.image_url
        for m in matches
        if m.match != "similar" and m.image_url and m.image_url.startswith("https://")
    ]
    hosted = [u for u in urls if ".gstatic.com/" in u]
    return list(dict.fromkeys(hosted + urls))[:limit]


def parse_bing_pages(items) -> list[ImageMatch]:
    """Bing "pages with this image": direct page links with the date Bing shows."""
    matches, seen = [], set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = _text(item, "source")
        if not url or not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        shown = _text(item, "date")
        published = None
        if shown:
            try:
                published = datetime.fromisoformat(shown.replace("Z", "+00:00")).date()
            except ValueError:
                published = None
        image = _text(item, "original")
        matches.append(
            ImageMatch(
                page_url=url,
                page_title=_text(item, "title"),
                image_url=image if image and image.startswith("https://") else None,
                match="full",
                source=(urlsplit(url).hostname or "").removeprefix("www.") or None,
                date_text=published.strftime("%b %d, %Y") if published else None,
                published_on=published,
                found_by="bing",
            )
        )
    return matches


# Lens shows the page's date for these sites, which for a profile or group page can be when
# the page was created: a 2026 video matched Facebook pages dated 2013. The date is still
# shown, but it is not used as a publication date.
SOCIAL_SITES = {"facebook", "instagram", "x", "twitter", "tiktok", "pinterest", "threads"}


def social_site(source: str | None, url: str) -> bool:
    # m.facebook.com and facebook.com both name the site facebook.
    site = ((urlsplit(url).hostname or "").lower().split(".")[-2:] or [""])[0]
    return (source or "").strip().lower() in SOCIAL_SITES or site in SOCIAL_SITES


def parse_lens_matches(items, match: str) -> list[ImageMatch]:
    matches, seen = [], set()
    for item in items or []:
        if not isinstance(item, dict):
            continue
        url = _text(item, "link")
        if not url or not url.startswith(("http://", "https://")) or url in seen:
            continue
        seen.add(url)
        image = _text(item, "image") or _text(item, "thumbnail")
        date_text = _text(item, "date")
        source = _text(item, "source")
        matches.append(
            ImageMatch(
                page_url=url,
                page_title=_text(item, "title"),
                image_url=image if image and image.startswith("https://") else None,
                match=match,
                source=source,
                date_text=date_text,
                published_on=None if social_site(source, url) else parse_display_date(date_text),
                found_by="google_lens",
            )
        )
    return matches


def order_matches(matches: list[ImageMatch]) -> list[ImageMatch]:
    """Same-image matches first, earliest displayed date first; others keep provider rank."""
    rank = {"full": 0, "partial": 0, "similar": 1}
    return sorted(
        matches,
        key=lambda m: (rank[m.match], m.published_on is None, m.published_on or date.max),
    )


# Hints that a page is a fact check. They only set reading priority; they are not a judgment
# of a source's reliability.
FACT_CHECK_WORDS = (
    "fact check",
    "fact-check",
    "doğruluk kontrolü",
    "doğruluk payı",
    "teyit",
    "doğrula",
    "snopes",
    "hoax",
    "debunk",
)


def looks_like_fact_check(match: ImageMatch) -> bool:
    host = (urlsplit(match.page_url).hostname or "").lower()
    if any(host == name or host.endswith("." + name) for name in FACT_CHECK_HOSTS):
        return True
    text = " ".join(filter(None, (match.source, match.page_title))).casefold()
    return any(word in text for word in FACT_CHECK_WORDS)


def select_matches(matches: list[ImageMatch], limit: int) -> list[ImageMatch]:
    """Keep the earliest matches plus every likely fact check, in display order."""
    ordered = order_matches(matches)
    checks = [m for m in ordered if looks_like_fact_check(m)]
    others = [m for m in ordered if not looks_like_fact_check(m)]
    kept = {id(m) for m in checks + others[: max(limit - len(checks), 0)]}
    return [m for m in ordered if id(m) in kept]


def is_google_redirect(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return (host == "google.com" or host.endswith(".google.com")) and parts.path == "/goto"


class SerpApiLensSearch:
    """Google Lens through SerpApi: upload once, read exact matches and, if few, visual matches.

    Lens shows a date for many exact matches. It is the date displayed for that page: a lead
    for the earliest known appearance, not proof of where or when the image was first published.
    """

    name = "serpapi_lens"
    upload_endpoint = "https://serpapi.com/image"
    search_endpoint = "https://serpapi.com/search"
    # SerpApi's upload limit; uploaded image IDs expire after ten minutes.
    max_upload_bytes = 500_000

    def __init__(
        self,
        api_key: str,
        timeout: float = 45,
        min_exact_matches: int = 3,
        max_similar_matches: int = 10,
        max_matches: int = 25,
        bing: bool = True,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("SerpApi Lens requires SERP_API_KEY.")
        # Bing returns direct page links and dates; it needs a public copy found by Lens.
        self.bing = bing
        self.api_key = api_key
        self.min_exact_matches = min_exact_matches
        self.max_similar_matches = max_similar_matches
        # Popular images match hundreds of pages; keep a reviewable set.
        self.max_matches = max_matches
        self.client = httpx.Client(
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
        )

    def close(self):
        self.client.close()

    @staticmethod
    def _json(response: httpx.Response) -> dict:
        if response.status_code != 200:
            code = "rate_limited" if response.status_code == 429 else "http_error"
            raise ReverseImageFailure(code, response.status_code)
        try:
            body = response.json()
        except ValueError as error:
            raise ReverseImageFailure("invalid_response") from error
        if not isinstance(body, dict):
            raise ReverseImageFailure("invalid_response")
        error = body.get("error")
        if isinstance(error, str) and "hasn't returned any results" in error:
            # SerpApi reports an empty result set as an error.
            return {}
        if error:
            raise ReverseImageFailure("provider_error")
        return body

    def _bing(self, image_url: str) -> list[ImageMatch]:
        params = {"engine": "bing_reverse_image", "image_url": image_url, "api_key": self.api_key}
        try:
            response = self.client.get(self.search_endpoint, params=params)
        except httpx.HTTPError as error:
            raise ReverseImageFailure("transport_error") from error
        return parse_bing_pages(self._json(response).get("pages_with_this_image"))

    def _lens(self, image_id: str, kind: str) -> dict:
        # SerpApi takes the key as a parameter; failures keep only a code, never the URL.
        params = {
            "engine": "google_lens",
            "image_id": image_id,
            "type": kind,
            "api_key": self.api_key,
        }
        try:
            response = self.client.get(self.search_endpoint, params=params)
        except httpx.HTTPError as error:
            raise ReverseImageFailure("transport_error") from error
        return self._json(response)

    def _resolve(self, match: ImageMatch) -> ImageMatch:
        """Replace a Google redirect link with its target; keep the link if that fails.

        Google often answers freshly issued links with a request-verification page. That page
        is never automated; the link stays a Google link and is not read as a source.
        """
        if not is_google_redirect(match.page_url):
            return match
        try:
            response = self.client.get(match.page_url, timeout=8)
        except httpx.HTTPError:
            return match
        target = ""
        if response.status_code in {301, 302, 303, 307, 308}:
            target = response.headers.get("location", "")
        elif response.status_code == 200 and len(response.content) < 4000:
            # Google sometimes answers 200 with a small "302 Moved" page holding the link.
            found = re.search(r'<A HREF="(https?://[^"]+)"', response.text, re.IGNORECASE)
            target = html.unescape(found.group(1)) if found else ""
        if target.startswith(("http://", "https://")) and not is_google_redirect(target):
            return match.model_copy(update={"page_url": target})
        return match

    def search(self, data: bytes, mime_type: str) -> MediaOrigin:
        upload = shrink_image(data, self.max_upload_bytes)
        try:
            response = self.client.post(
                self.upload_endpoint,
                data={"api_key": self.api_key},
                files={"image": ("image.jpg", upload, "image/jpeg")},
            )
        except httpx.HTTPError as error:
            raise ReverseImageFailure("transport_error") from error
        image_id = self._json(response).get("image_id")
        if not isinstance(image_id, str) or not image_id:
            raise ReverseImageFailure("invalid_response")
        exact = self._lens(image_id, "exact_matches").get("exact_matches")
        matches = parse_lens_matches(exact, "full")
        # Visual matches cost a second search; use them only when exact matches are scarce.
        if len(matches) < self.min_exact_matches:
            known = {m.page_url for m in matches}
            visual = self._lens(image_id, "visual_matches").get("visual_matches")
            similar = [m for m in parse_lens_matches(visual, "similar") if m.page_url not in known]
            matches += similar[: self.max_similar_matches]
        kept = [self._resolve(m) for m in select_matches(matches, self.max_matches)]
        reason = None
        # Thumbnails are small; a second copy sometimes finds pages the first did not.
        for copy in public_copies(kept, limit=2) if self.bing else []:
            try:
                found = self._bing(copy)
            except ReverseImageFailure as error:
                reason = f"Bing reverse image search did not complete ({error.code})."
                break
            if found:
                kept += found
                break
        unique = {m.page_url: m for m in reversed(kept)}
        kept = order_matches([m for m in kept if unique[m.page_url] is m])
        return MediaOrigin(
            status="matches_found" if kept else "no_matches",
            provider=self.name,
            reason=reason,
            matches=kept,
        )


# Redirect links and social feeds rarely yield readable page text.
UNREADABLE_HOSTS = (
    "google.com",
    "instagram.com",
    "facebook.com",
    "pinterest.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
)


def readable_matches(origin: MediaOrigin, limit: int) -> list[ImageMatch]:
    """Matches to read as research sources: likely fact checks first, then the adapter's order."""
    picked = []
    ordered = [m for m in origin.matches if looks_like_fact_check(m)]
    ordered += [m for m in origin.matches if not looks_like_fact_check(m)]
    for match in ordered:
        host = (urlsplit(match.page_url).hostname or "").lower()
        if any(host == name or host.endswith("." + name) for name in UNREADABLE_HOSTS):
            continue
        picked.append(match)
        if len(picked) >= limit:
            break
    return picked


def build_reverse_image_search(settings) -> ReverseImageSearch | None:
    """Return the configured adapter, or None when no provider is selected."""
    if settings.reverse_image_provider == "serpapi_lens":
        return SerpApiLensSearch(settings.serp_api_key.get_secret_value())
    return None
