"""Search contracts and immutable claim/need/query identities."""

import json
from hashlib import sha256
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ENDPOINT = "https://api.tavily.com/search"


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    query: str = Field(min_length=1, max_length=400)
    language: Literal["tr", "en"]
    max_results: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Query must not be blank.")
        return value

    def payload(self) -> dict:
        return {
            "query": self.query,
            "search_depth": "basic",
            "auto_parameters": False,
            "max_results": self.max_results,
            "topic": "general",
            "language": self.language,
            "filter_by_language": False,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "include_usage": True,
            "include_published_date": True,
        }

    @property
    def cache_key(self) -> str:
        identity = {
            "endpoint": ENDPOINT,
            "access_mode": "keyless",
            "payload": self.payload(),
        }
        return sha256(json.dumps(identity, sort_keys=True).encode("utf-8")).hexdigest()


def canonical_source_url(value: str) -> str:
    parts = urlsplit(value)
    if (
        parts.scheme.lower() not in {"https", "http"}
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise ValueError("Source URL must be an HTTP(S) URL without credentials.")
    # Remove tracking and fragments, never meaningful query parameters.
    parameters = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path or "/",
            urlencode(parameters),
            "",
        )
    )


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    title: str
    url: str
    content: str | None = None
    score: float | None = None
    published_date: str | None = None

    @field_validator("url")
    @classmethod
    def validate_source_url(cls, value: str) -> str:
        canonical_source_url(value)
        return value


class SearchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    query: str
    results: list[SearchResult]
    response_time: float | None = None
    request_id: str | None = None
    usage: dict | None = None


def parse_response(content: str, request: SearchRequest) -> SearchResponse:
    result = SearchResponse.model_validate_json(content)
    if result.query != request.query:
        raise ValueError("Provider response query differs from the recorded request.")
    if len(result.results) > request.max_results:
        raise ValueError("Provider returned more results than requested.")
    return result


class ClaimReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    quote: str


class ResearchNeed(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    claim_id: str
    description: str
    status: Literal["planned", "needs_context", "budget_deferred", "not_checkable"]
    # Only pages showing the same picture settle it; plans saved before v9 lack the flag.
    about_attached_media: bool = False


class ResearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1)
    request: SearchRequest
    need_ids: list[str] = Field(min_length=1)


class SavedResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    case_id: str = Field(min_length=1)
    claims: list[ClaimReference]
    needs: list[ResearchNeed]
    queries: list[ResearchQuery]

    @model_validator(mode="after")
    def validate_references(self):
        for items in (self.claims, self.needs, self.queries):
            if len({item.id for item in items}) != len(items):
                raise ValueError("Duplicate identifier within the plan.")
        claims = {item.id for item in self.claims}
        needs = {item.id: item for item in self.needs}
        if any(need.claim_id not in claims for need in self.needs):
            raise ValueError("Need references an unknown claim.")
        for query in self.queries:
            if len(query.need_ids) != len(set(query.need_ids)):
                raise ValueError("Repeated query/need binding.")
            if any(n not in needs or needs[n].status != "planned" for n in query.need_ids):
                raise ValueError("Query references an unknown or deferred need.")
        return self


class RetrievalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    search_ttl_seconds: int = Field(default=21600, gt=0)
    page_ttl_seconds: int = Field(default=86400, gt=0)
    failure_ttl_seconds: int = Field(default=300, gt=0)
    max_search_calls: int = Field(default=30, ge=0, le=100)
    max_extract_calls: int = Field(default=6, ge=0, le=20)
    max_followup_queries: int = Field(default=2, ge=0, le=10)
    timeout_seconds: float = Field(default=45, gt=0, le=120)
