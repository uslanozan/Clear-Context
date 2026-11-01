"""A separate SQLite research workspace; never modifies the application database."""

import json
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from sqlalchemy import create_engine, delete, event, func, or_, select
from sqlalchemy.dialects.sqlite import insert

from clear_context.models.retrieval_cache import (
    cache,
    cases,
    claims,
    events,
    hits,
    metadata,
    needs,
    pages,
    passage_needs,
    passages,
    queries,
    query_needs,
    selection_passages,
    selections,
    sources,
)
from clear_context.schemas.retrieval import SavedResearchPlan, canonical_source_url, parse_response


def identity(prefix: str, value: str) -> str:
    return prefix + sha256(value.encode("utf-8")).hexdigest()


def encode(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


class RetrievalRepository:
    def __init__(self, path: Path):
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine("sqlite:///" + path.as_posix())

        @event.listens_for(self.engine, "connect")
        def configure(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")

        metadata.create_all(self.engine)

    def close(self):
        self.engine.dispose()

    def overview(self, investigation_id: str) -> dict:
        """What research recorded for one investigation: plans, searches, results, selections.

        A complete run splits into batches whose case ids carry a ':batchN' suffix.
        """
        with self.engine.connect() as conn:
            case_ids = list(
                conn.scalars(
                    select(cases.c.id).where(
                        or_(
                            cases.c.id == investigation_id,
                            cases.c.id.like(f"{investigation_id}:batch%"),
                        )
                    )
                )
            )
            if not case_ids:
                return {
                    "queries": [],
                    "needs": [],
                    "results": 0,
                    "sources_found": 0,
                    "selections": 0,
                }
            needs_out = []
            for payload in conn.scalars(select(cases.c.plan).where(cases.c.id.in_(case_ids))):
                plan = SavedResearchPlan.model_validate_json(payload)
                needs_out += [
                    {"claim_id": n.claim_id, "description": n.description, "status": n.status}
                    for n in plan.needs
                ]
            queries_out = []
            for payload, origin in conn.execute(
                select(queries.c.payload, queries.c.origin).where(queries.c.case_id.in_(case_ids))
            ):
                search = json.loads(payload)
                # Reverse image lookups carry no query text or language.
                queries_out.append(
                    {
                        "kind": search.get("kind", "text"),
                        "query": search.get("query"),
                        "language": search.get("language"),
                        "origin": origin,
                    }
                )
            results = conn.scalar(
                select(func.count()).select_from(hits).where(hits.c.case_id.in_(case_ids))
            )
            found = conn.scalar(
                select(func.count(func.distinct(hits.c.source_id))).where(
                    hits.c.case_id.in_(case_ids)
                )
            )
            chosen = conn.scalar(
                select(func.count())
                .select_from(selections)
                .where(selections.c.case_id.in_(case_ids))
            )
        return {
            "queries": queries_out,
            "needs": needs_out,
            "results": results or 0,
            "sources_found": found or 0,
            "selections": chosen or 0,
        }

    def register_plan(self, plan: SavedResearchPlan):
        payload = encode(plan.model_dump())
        with self.engine.begin() as conn:
            old = conn.scalar(select(cases.c.plan).where(cases.c.id == plan.case_id))
            if old is not None:
                if old != payload:
                    raise ValueError("Case already exists with a different immutable plan.")
                return
            conn.execute(insert(cases).values(id=plan.case_id, plan=payload))
            for claim in plan.claims:
                conn.execute(insert(claims).values(case_id=plan.case_id, id=claim.id))
            for need in plan.needs:
                conn.execute(
                    insert(needs).values(case_id=plan.case_id, id=need.id, claim_id=need.claim_id)
                )
            for query in plan.queries:
                self._insert_query(
                    conn,
                    plan.case_id,
                    query.id,
                    query.request.model_dump(),
                    query.need_ids,
                    "initial",
                )

    @staticmethod
    def _insert_query(conn, case_id, query_id, request, need_ids, origin):
        conn.execute(
            insert(queries).values(
                case_id=case_id, id=query_id, payload=encode(request), origin=origin
            )
        )
        for need_id in need_ids:
            conn.execute(
                insert(query_needs).values(case_id=case_id, query_id=query_id, need_id=need_id)
            )

    def plan(self, case_id: str) -> SavedResearchPlan:
        with self.engine.connect() as conn:
            payload = conn.scalar(select(cases.c.plan).where(cases.c.id == case_id))
        if payload is None:
            raise ValueError("Unknown case.")
        return SavedResearchPlan.model_validate_json(payload)

    def query(self, case_id, query_id):
        with self.engine.connect() as conn:
            payload = conn.scalar(
                select(queries.c.payload).where(
                    queries.c.case_id == case_id, queries.c.id == query_id
                )
            )
        if payload is None:
            raise ValueError("Unknown query in this case.")
        from clear_context.schemas.retrieval import SearchRequest

        return SearchRequest.model_validate_json(payload)

    def add_followup(self, case_id, query_id, request, need_ids):
        plan = self.plan(case_id)
        known = {n.id for n in plan.needs if n.status == "planned"}
        if not need_ids or len(set(need_ids)) != len(need_ids) or not set(need_ids) <= known:
            raise ValueError("Follow-up must reference existing planned needs.")
        with self.engine.begin() as conn:
            self._insert_query(conn, case_id, query_id, request.model_dump(), need_ids, "followup")

    def add_image_matches(self, case_id, query_id, need_ids, results, retrieved_at):
        """Record reverse image matches as discovered sources for planned needs.

        The query row only links these pages to needs; it is never sent to a search provider.
        """
        plan = self.plan(case_id)
        known = {n.id for n in plan.needs if n.status == "planned"}
        if not need_ids or not set(need_ids) <= known:
            raise ValueError("Image matches must reference existing planned needs.")
        with self.engine.begin() as conn:
            self._insert_query(
                conn, case_id, query_id, {"kind": "reverse_image"}, need_ids, "image_match"
            )
            for rank, result in enumerate(results, 1):
                url = canonical_source_url(result["url"])
                source_id = identity("s_", url)
                conn.execute(insert(sources).values(id=source_id, url=url).on_conflict_do_nothing())
                conn.execute(
                    insert(hits)
                    .values(
                        case_id=case_id,
                        query_id=query_id,
                        source_id=source_id,
                        rank=rank,
                        result=encode(result),
                        retrieved_at=retrieved_at,
                    )
                    .on_conflict_do_nothing()
                )

    def cached(self, kind, key, now):
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(cache).where(
                        cache.c.kind == kind, cache.c.key == key, cache.c.expires_at > now
                    )
                )
                .mappings()
                .first()
            )
        return dict(row) if row else None

    def save_cache(self, kind, key, payload, now, ttl):
        if ttl <= 0:
            raise ValueError("Cache TTL must be positive.")
        values = dict(
            kind=kind, key=key, payload=encode(payload), fetched_at=now, expires_at=now + ttl
        )
        with self.engine.begin() as conn:
            conn.execute(
                insert(cache)
                .values(**values)
                .on_conflict_do_update(index_elements=["kind", "key"], set_=values)
            )

    def ingest_search(self, case_id, query_id, response, retrieved_at):
        request = self.query(case_id, query_id)
        parsed = parse_response(encode(response), request)
        with self.engine.begin() as conn:
            conn.execute(delete(hits).where(hits.c.case_id == case_id, hits.c.query_id == query_id))
            seen = set()
            for rank, result in enumerate(parsed.results, 1):
                url = canonical_source_url(result.url)
                source_id = identity("s_", url)
                conn.execute(insert(sources).values(id=source_id, url=url).on_conflict_do_nothing())
                if source_id not in seen:
                    conn.execute(
                        insert(hits).values(
                            case_id=case_id,
                            query_id=query_id,
                            source_id=source_id,
                            rank=rank,
                            result=encode(result.model_dump()),
                            retrieved_at=retrieved_at,
                        )
                    )
                    seen.add(source_id)

    def media_relation(self, case_id, source_id) -> str | None:
        """How reverse image search linked this source to the user's media, if it did."""
        with self.engine.connect() as conn:
            rows = conn.execute(
                select(hits.c.result).where(
                    hits.c.case_id == case_id, hits.c.source_id == source_id
                )
            ).scalars()
            relations = {json.loads(raw).get("media_relation") for raw in rows}
        # The closest relation wins when a page was found more than one way.
        return next(
            (r for r in ("fact_check", "same_image", "similar_image") if r in relations), None
        )

    def source_url(self, source_id):
        with self.engine.connect() as conn:
            url = conn.scalar(select(sources.c.url).where(sources.c.id == source_id))
        if url is None:
            raise ValueError("Unknown source.")
        return url

    def save_page(self, source_id, content, fetched_at):
        self.source_url(source_id)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Empty page cannot become evidence.")
        page_id = identity("p_", encode([source_id, content, float(fetched_at)]))
        with self.engine.begin() as conn:
            conn.execute(
                insert(pages)
                .values(id=page_id, source_id=source_id, content=content, fetched_at=fetched_at)
                .on_conflict_do_nothing()
            )
        return page_id

    def page(self, page_id):
        with self.engine.connect() as conn:
            row = conn.execute(select(pages).where(pages.c.id == page_id)).mappings().first()
        if row is None:
            raise ValueError("Unknown page.")
        return dict(row)

    def add_passage(self, page_id, start, end, quote, case_id, need_ids):
        page = self.page(page_id)
        if not 0 <= start < end <= len(page["content"]) or page["content"][start:end] != quote:
            raise ValueError("Passage must match exact page offsets and text.")
        plan = self.plan(case_id)
        allowed = {n.id for n in plan.needs if n.status == "planned"}
        if not need_ids or len(set(need_ids)) != len(need_ids) or not set(need_ids) <= allowed:
            raise ValueError("Invalid passage/need reference.")
        passage_id = identity("e_", encode([page_id, start, end]))
        with self.engine.begin() as conn:
            discovered = conn.scalar(
                select(hits.c.source_id).where(
                    hits.c.case_id == case_id, hits.c.source_id == page["source_id"]
                )
            )
            if discovered is None:
                raise ValueError("Source was not discovered in this case.")
            conn.execute(
                insert(passages)
                .values(id=passage_id, page_id=page_id, start=start, end=end, quote=quote)
                .on_conflict_do_nothing()
            )
            for need_id in need_ids:
                conn.execute(
                    insert(passage_needs)
                    .values(passage_id=passage_id, case_id=case_id, need_id=need_id)
                    .on_conflict_do_nothing()
                )
        return passage_id

    def check_selection_source(self, case_id, page_id, need_ids):
        page = self.page(page_id)
        plan = self.plan(case_id)
        known = {n.id for n in plan.needs if n.status == "planned"}
        if not need_ids or len(need_ids) != len(set(need_ids)) or not set(need_ids) <= known:
            raise ValueError("Selection must reference existing planned needs.")
        with self.engine.connect() as conn:
            discovered = conn.scalar(
                select(hits.c.source_id).where(
                    hits.c.case_id == case_id, hits.c.source_id == page["source_id"]
                )
            )
        if discovered is None:
            raise ValueError("Selected source was not discovered in this case.")
        return page, plan

    def save_selection(
        self,
        case_id,
        page_id,
        method,
        model,
        prompt_sha256,
        request_key,
        output,
        units,
        created_at,
        *,
        context_windows=None,
    ):
        need_ids = [s.need_id for s in output.selections]
        page, _ = self.check_selection_source(case_id, page_id, need_ids)
        bindings = []
        for selection in output.selections:
            for paragraph_id in selection.paragraph_ids:
                unit = units[paragraph_id]
                if (
                    not 0 <= unit.start < unit.end <= len(page["content"])
                    or page["content"][unit.start : unit.end] != unit.text
                ):
                    raise ValueError("Selected paragraph differs from its page snapshot.")
                passage_id = identity("e_", encode([page_id, unit.start, unit.end]))
                bindings.append((selection.need_id, passage_id, unit))
        result = output.model_dump()
        if context_windows is not None:
            selected = {(s.need_id, pid) for s in output.selections for pid in s.paragraph_ids}
            if (
                len(context_windows) != len(selected)
                or {(c.need_id, c.paragraph_id) for c in context_windows} != selected
            ):
                raise ValueError("Every selected passage needs exactly one context window.")
            for context in context_windows:
                unit = units[context.paragraph_id]
                if not (
                    0
                    <= context.start
                    <= unit.start
                    < unit.end
                    <= context.end
                    <= len(page["content"])
                    and context.selected_start == unit.start
                    and context.selected_end == unit.end
                    and page["content"][context.start : context.end] == context.quote
                ):
                    raise ValueError("Context differs from its selected source range.")
            result["context_windows"] = [asdict(c) for c in context_windows]
        selection_id = identity(
            "sel_", encode([case_id, page_id, request_key, float(created_at), result])
        )
        with self.engine.begin() as conn:
            conn.execute(
                insert(selections)
                .values(
                    id=selection_id,
                    case_id=case_id,
                    page_id=page_id,
                    method=method,
                    model=model,
                    prompt_sha256=prompt_sha256,
                    request_key=request_key,
                    result=encode(result),
                    created_at=created_at,
                )
                .on_conflict_do_nothing()
            )
            for need_id, passage_id, unit in bindings:
                conn.execute(
                    insert(passages)
                    .values(
                        id=passage_id,
                        page_id=page_id,
                        start=unit.start,
                        end=unit.end,
                        quote=unit.text,
                    )
                    .on_conflict_do_nothing()
                )
                conn.execute(
                    insert(passage_needs)
                    .values(passage_id=passage_id, case_id=case_id, need_id=need_id)
                    .on_conflict_do_nothing()
                )
                conn.execute(
                    insert(selection_passages)
                    .values(
                        selection_id=selection_id,
                        passage_id=passage_id,
                        case_id=case_id,
                        need_id=need_id,
                    )
                    .on_conflict_do_nothing()
                )
        return selection_id

    def log(self, event_kind, at, **payload):
        with self.engine.begin() as conn:
            conn.execute(insert(events).values(kind=event_kind, at=at, payload=encode(payload)))

    def export(self):
        with self.engine.connect() as conn:
            return {
                table.name: [dict(row) for row in conn.execute(select(table)).mappings()]
                for table in (
                    cases,
                    claims,
                    needs,
                    queries,
                    query_needs,
                    sources,
                    hits,
                    pages,
                    passages,
                    passage_needs,
                    selections,
                    selection_passages,
                    events,
                )
            }
