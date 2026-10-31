"""Bounded concurrent full-page selection with source-bound persistence."""

import asyncio
import json
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from time import perf_counter

from clear_context.core.passage_selectors import SelectionLimits, SelectorProfile
from clear_context.core.settings import ModelSelection
from clear_context.providers.meta_passages import (
    MetaPassageProvider,
    SelectionFailure,
    build_selection_request,
)
from clear_context.repositories.retrieval import RetrievalRepository, encode, identity
from clear_context.schemas.passage_selection import validate
from clear_context.services.paragraphs import paragraphs
from clear_context.services.passage_context import source_context


@dataclass(frozen=True)
class SelectionJob:
    case_id: str
    page_id: str
    need_ids: tuple[str, ...]


class PassageSelectionService:
    def __init__(
        self,
        repository: RetrievalRepository,
        provider: MetaPassageProvider,
        method: str,
        profile: SelectorProfile,
        limits: SelectionLimits,
        system: str,
        model: ModelSelection,
        clock=time.time,
        media_rule: str = "",
    ):
        self.repository, self.provider = repository, provider
        self.method, self.profile, self.limits = method, profile, limits
        self.system, self.model, self.clock = system, model, clock
        self.media_rule = media_rule
        self.calls = 0
        self.halted = False
        self.active = 0
        self.max_active = 0

    def prepare(self, job: SelectionJob):
        page, plan = self.repository.check_selection_source(job.case_id, job.page_id, job.need_ids)
        if len(page["content"]) > self.limits.max_page_chars:
            raise SelectionFailure("page_too_large")
        if self.profile.implementation != "full_page":
            raise ValueError("Unsupported passage selector.")
        units = paragraphs(page["content"], self.limits.paragraph_max_chars)
        needs = [dict(sorted(n.model_dump().items())) for n in plan.needs if n.id in job.need_ids]
        claim_ids = {n["claim_id"] for n in needs}
        claims = [dict(sorted(c.model_dump().items())) for c in plan.claims if c.id in claim_ids]
        allowed = {n["id"]: [u.id for u in units] for n in needs}
        relation = self.repository.media_relation(job.case_id, page["source_id"])
        system = self.system
        if relation in {"same_image", "fact_check"}:
            system = f"{system}\n{self.media_rule}"
        payload = build_selection_request(
            system,
            {"url": self.repository.source_url(page["source_id"])},
            needs,
            claims,
            units,
            allowed,
            model=self.model.api_model_id,
            effort=self.limits.effort,
            max_completion_tokens=self.limits.max_completion_tokens,
            response_contract=self.profile.response_contract,
            media_match=relation,
        )
        key = identity(
            "selection_",
            encode(
                {
                    "endpoint": "https://api.meta.ai/v1/chat/completions",
                    "page_id": job.page_id,
                    "payload": payload,
                }
            ),
        )
        return units, allowed, payload, key

    async def select_pages(self, jobs: list[SelectionJob]):
        grouped = {}
        for job in jobs:
            key = (job.case_id, job.page_id)
            grouped.setdefault(key, set()).update(job.need_ids)
        jobs = [
            SelectionJob(case, page, tuple(sorted(ids))) for (case, page), ids in grouped.items()
        ]
        # Validate every association before any model request can start.
        prepared = []
        for job in jobs:
            try:
                prepared.append((job, self.prepare(job), None))
            except SelectionFailure as error:
                prepared.append((job, None, error.code))
        concurrency = self.limits.max_concurrency
        if concurrency is None:
            concurrency = max(1, min(len(prepared), self.limits.max_model_calls or 1))
        semaphore = asyncio.Semaphore(concurrency)

        async def process(job, inputs, preflight_error):
            row = {"case_id": job.case_id, "page_id": job.page_id, "need_ids": list(job.need_ids)}
            if preflight_error:
                return row | {"status": preflight_error, "cached": False}
            async with semaphore:
                started = perf_counter()
                units, allowed, payload, key = inputs
                row.update(request_key=key, paragraphs=len(units), cached=False)
                cached = self.repository.cached("selection", key, self.clock())
                try:
                    if cached:
                        body = json.loads(cached["payload"])
                        received_at = cached["fetched_at"]
                        row["cached"] = True
                        self.repository.log(
                            "selection_cache_hit", self.clock(), page_id=job.page_id, key=key
                        )
                    else:
                        if self.halted:
                            return row | {"status": "not_run_after_failure"}
                        if self.calls >= self.limits.max_model_calls:
                            return row | {"status": "call_budget_exhausted"}
                        self.calls += 1
                        self.active += 1
                        self.max_active = max(self.max_active, self.active)
                        self.repository.log(
                            "selection_started",
                            self.clock(),
                            case_id=job.case_id,
                            page_id=job.page_id,
                            key=key,
                            request=payload,
                            active=self.active,
                            call_number=self.calls,
                        )
                        try:
                            body = await self.provider.select(payload, self.limits.timeout_seconds)
                        finally:
                            self.active -= 1
                        received_at = self.clock()
                    content = body["choices"][0]["message"]["content"]
                    output = validate(content, allowed, self.profile.response_contract)
                    page = self.repository.page(job.page_id)
                    units_by_id = {u.id: u for u in units}
                    contexts = [
                        source_context(
                            page["content"],
                            units_by_id[pid],
                            selection.need_id,
                            self.limits.context_before_chars,
                            self.limits.context_after_chars,
                        )
                        for selection in output.selections
                        for pid in selection.paragraph_ids
                    ]
                    if not row["cached"]:
                        self.repository.save_cache(
                            "selection", key, body, received_at, self.limits.cache_ttl_seconds
                        )
                    selection_id = self.repository.save_selection(
                        job.case_id,
                        job.page_id,
                        self.method,
                        self.model.api_model_id,
                        sha256(self.system.encode()).hexdigest(),
                        key,
                        output,
                        units_by_id,
                        received_at,
                        context_windows=contexts,
                    )
                    row.update(
                        status="selected"
                        if any(s.paragraph_ids for s in output.selections)
                        else "not_found",
                        selection_id=selection_id,
                        output=output.model_dump(),
                        context_windows=[asdict(context) for context in contexts],
                        usage=body.get("usage"),
                    )
                    self.repository.log(
                        "selection_completed",
                        self.clock(),
                        page_id=job.page_id,
                        case_id=job.case_id,
                        selection_id=selection_id,
                        cached=row["cached"],
                    )
                except (SelectionFailure, ValueError, KeyError, IndexError, TypeError) as error:
                    self.halted = True
                    code = (
                        error.code if isinstance(error, SelectionFailure) else "invalid_selection"
                    )
                    row.update(status=code)
                    self.repository.log(
                        "selection_failed",
                        self.clock(),
                        page_id=job.page_id,
                        code=code,
                        error_type=type(error).__name__,
                    )
                row["elapsed_seconds"] = round(perf_counter() - started, 3)
                return row

        return await asyncio.gather(*(process(*item) for item in prepared))
