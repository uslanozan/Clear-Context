"""Google Fact Check Tools image search: published fact checks of the same image.

The API needs a publicly reachable image URL. The uploaded file is never published; the
query uses copies of the same image that reverse image search already found online.
A review's rating is the publisher's conclusion, reported as found, not ours.
"""

from datetime import datetime

import httpx

from clear_context.domain.investigation import MediaOrigin, PriorChecks, PriorFactCheck


class FactCheckFailure(RuntimeError):
    def __init__(self, code: str, status_code: int | None = None):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def parse_review_date(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _text(value) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def parse_image_search(body: dict) -> list[PriorFactCheck]:
    reviews, seen = [], set()
    for result in body.get("results") or []:
        claim = (result or {}).get("claim") or {}
        for review in claim.get("claimReview") or []:
            url = _text(review.get("url"))
            if not url or not url.startswith(("http://", "https://")) or url in seen:
                continue
            seen.add(url)
            published = parse_review_date(review.get("reviewDate"))
            publisher = review.get("publisher") or {}
            reviews.append(
                PriorFactCheck(
                    url=url,
                    title=_text(review.get("title")),
                    publisher=_text(publisher.get("name")),
                    site=_text(publisher.get("site")),
                    rating=_text(review.get("textualRating")),
                    review_date=published.date() if published else None,
                    claim_text=_text(claim.get("text")),
                    language=_text(review.get("languageCode")),
                )
            )
    return reviews


def public_copies(origin: MediaOrigin, limit: int = 2) -> list[str]:
    """Image URLs of same-image matches; Google-hosted thumbnails are preferred."""
    urls = [
        m.image_url
        for m in origin.matches
        if m.match != "similar" and m.image_url and m.image_url.startswith("https://")
    ]
    hosted = [u for u in urls if ".gstatic.com/" in u]
    return list(dict.fromkeys(hosted + urls))[:limit]


class GoogleFactCheckSearch:
    name = "google_fact_check"
    endpoint = "https://factchecktools.googleapis.com/v1alpha1/claims:imageSearch"

    def __init__(
        self,
        api_key: str,
        timeout: float = 20,
        transport: httpx.BaseTransport | None = None,
    ):
        if not api_key:
            raise ValueError("Fact Check image search requires a Google API key.")
        # The key travels in a header, not the URL.
        self.client = httpx.Client(
            timeout=timeout,
            transport=transport or httpx.HTTPTransport(retries=0),
            trust_env=False,
            follow_redirects=False,
            headers={"X-goog-api-key": api_key},
        )

    def close(self):
        self.client.close()

    def search_image_url(self, image_url: str) -> list[PriorFactCheck]:
        try:
            response = self.client.get(self.endpoint, params={"imageUri": image_url})
        except httpx.HTTPError as error:
            raise FactCheckFailure("transport_error") from error
        if response.status_code != 200:
            code = "rate_limited" if response.status_code == 429 else "http_error"
            raise FactCheckFailure(code, response.status_code)
        try:
            body = response.json()
        except ValueError as error:
            raise FactCheckFailure("invalid_response") from error
        if not isinstance(body, dict):
            raise FactCheckFailure("invalid_response")
        return parse_image_search(body)

    def lookup(self, origin: MediaOrigin) -> PriorChecks:
        copies = public_copies(origin)
        if not copies:
            return PriorChecks(
                status="not_checked",
                reason="No public copy of the image was found to query fact checks with.",
            )
        reviews, failure = [], None
        for url in copies:
            try:
                reviews = self.search_image_url(url)
            except FactCheckFailure as error:
                failure = error
                continue
            if reviews:
                break
        if not reviews and failure:
            return PriorChecks(
                status="failed",
                reason=f"Fact check search did not complete ({failure.code}).",
            )
        return PriorChecks(
            status="found" if reviews else "none",
            provider=self.name,
            reviews=sorted(reviews, key=lambda r: (r.review_date is None, r.review_date)),
        )


def build_fact_check_search(settings) -> GoogleFactCheckSearch | None:
    key = settings.google_fact_check_api_key.get_secret_value()
    if not settings.fact_check_image_search or not key:
        return None
    return GoogleFactCheckSearch(key)
