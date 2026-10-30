"""Bounded search and page reading with explicit provenance and no hidden retries."""

import json
import time
from pathlib import Path
from typing import Literal

import yaml

from clear_context.providers.tavily import EXTRACT_ENDPOINT, RetrievalFailure, TavilyClient
from clear_context.repositories.retrieval import RetrievalRepository, encode, identity
from clear_context.schemas.retrieval import RetrievalPolicy, SearchRequest


def load_retrieval_policy(path: Path) -> RetrievalPolicy:
    return RetrievalPolicy.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class RetrievalSession:
    def __init__(
        self,
        repository: RetrievalRepository,
        provider: TavilyClient,
        policy: RetrievalPolicy,
        clock=time.time,
    ):
        self.repository = repository
        self.provider = provider
        self.policy = policy
        self.clock = clock
        self.calls = {"search": 0, "extract": 0}
        self.followups = 0
        self.halted = False

    def _reserve(self, kind):
        if self.halted:
            raise RetrievalFailure("session_halted")
        limit = self.policy.max_search_calls if kind == "search" else self.policy.max_extract_calls
        if self.calls[kind] >= limit:
            raise RetrievalFailure("call_budget_exhausted")
        self.calls[kind] += 1

    def _live(self, kind, key, payload, operation):
        self._reserve(kind)
        self.repository.log("request_started", self.clock(), kind=kind, key=key, request=payload)
        try:
            value = operation()
        except RetrievalFailure as error:
            self.halted = error.code != "extract_failed"
            self.repository.log(
                "request_failed",
                self.clock(),
                kind=kind,
                key=key,
                code=error.code,
                status_code=error.status_code,
            )
            raise
        self.repository.log("request_completed", self.clock(), kind=kind, key=key)
        return value

    def search(self, case_id: str, query_id: str):
        request = self.repository.query(case_id, query_id)
        cached = self.repository.cached("search", request.cache_key, self.clock())
        if cached:
            response = json.loads(cached["payload"])
            retrieved_at = cached["fetched_at"]
            self.repository.log("cache_hit", self.clock(), kind="search", key=request.cache_key)
        else:
            response = self._live(
                "search",
                request.cache_key,
                request.payload(),
                lambda: self.provider.search(request),
            )
            retrieved_at = self.clock()
            self.repository.save_cache(
                "search", request.cache_key, response, retrieved_at, self.policy.search_ttl_seconds
            )
        self.repository.ingest_search(case_id, query_id, response, retrieved_at)
        return response

    def read_source(self, source_id: str):
        url = self.repository.source_url(source_id)
        payload = self.provider.extract_payload(url)
        key = identity(
            "extract_",
            encode({"endpoint": EXTRACT_ENDPOINT, "access_mode": "keyless", "payload": payload}),
        )
        cached = self.repository.cached("page", key, self.clock())
        if cached:
            response = json.loads(cached["payload"])
            retrieved_at = cached["fetched_at"]
            self.repository.log("cache_hit", self.clock(), kind="extract", key=key)
        else:
            failed = self.repository.cached("page_failure", key, self.clock())
            if failed:
                raise RetrievalFailure(json.loads(failed["payload"])["code"])
            try:
                response = self._live("extract", key, payload, lambda: self.provider.extract(url))
            except RetrievalFailure as error:
                if error.code == "extract_failed":
                    self.repository.save_cache(
                        "page_failure",
                        key,
                        {"code": error.code},
                        self.clock(),
                        self.policy.failure_ttl_seconds,
                    )
                raise
            retrieved_at = self.clock()
            self.repository.save_cache(
                "page", key, response, retrieved_at, self.policy.page_ttl_seconds
            )
        content = response["results"][0]["raw_content"]
        return self.repository.save_page(source_id, content, retrieved_at)

    def add_followup(
        self,
        case_id: str,
        query_id: str,
        request: SearchRequest,
        need_ids: list[str],
        gap: Literal["no_results", "irrelevant_results", "missing_context"],
        reason: str,
    ):
        if gap not in {"no_results", "irrelevant_results", "missing_context"} or not reason.strip():
            raise ValueError("Follow-up requires an explicit evidence gap and reason.")
        if self.followups >= self.policy.max_followup_queries:
            raise RetrievalFailure("followup_budget_exhausted")
        self.repository.add_followup(case_id, query_id, request, need_ids)
        self.followups += 1
        self.repository.log(
            "followup_registered",
            self.clock(),
            case_id=case_id,
            query_id=query_id,
            need_ids=need_ids,
            gap=gap,
            reason=reason,
        )
