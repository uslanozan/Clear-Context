"""Typed search-only evaluation helpers. No claim generation or truth judgments."""

import json
from hashlib import sha256
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


def bind_plan_queries(case_id: str, plan: dict) -> list[dict]:
    needs = {item["id"]: item for item in plan["needs"]}
    jobs = []
    for question in plan["questions"]:
        for query in question["queries"]:
            ids = query["need_ids"]
            if (
                not ids
                or len(set(ids)) != len(ids)
                or any(item not in needs for item in ids)
            ):
                raise ValueError("Query has missing, unknown or duplicate need IDs.")
            if any(needs[item]["status"] != "planned" for item in ids):
                raise ValueError("A search query references a deferred need.")
            jobs.append(
                {
                    "request": SearchRequest(
                        query=query["text"], language=query["language"]
                    ),
                    "binding": {
                        "plan_case_id": case_id,
                        "need_ids": ids,
                        "claim_ids": sorted({needs[item]["claim_id"] for item in ids}),
                        "question": question["question"],
                    },
                }
            )
    return jobs


def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    unique = {}
    for job in jobs:
        request = job["request"]
        key = request.cache_key
        if key not in unique:
            unique[key] = {
                "cache_key": key,
                "request": request.model_dump(),
                "bindings": [],
            }
        binding = job["binding"]
        if binding not in unique[key]["bindings"]:
            unique[key]["bindings"].append(binding)
    return list(unique.values())
