"""Build judge inputs only from saved, source-bound selection receipts."""

import json

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from clear_context.models.retrieval_cache import (
    hits,
    judgment_selections,
    judgments,
    selection_passages,
    selections,
)
from clear_context.repositories.retrieval import RetrievalRepository, encode, identity
from clear_context.schemas.evidence_judgment import EvidenceContext, JudgmentPacket


class JudgmentRepository:
    def __init__(self, research: RetrievalRepository):
        self.research = research

    def packet(self, case_id: str, need_ids: tuple[str, ...], selection_ids: tuple[str, ...]):
        plan = self.research.plan(case_id)
        known = {n.id: n for n in plan.needs}
        if not need_ids or len(set(need_ids)) != len(need_ids) or not set(need_ids) <= set(known):
            raise ValueError("Unknown or duplicate requested needs.")
        if len(selection_ids) != len(set(selection_ids)):
            raise ValueError("Duplicate selection receipts.")
        selected_needs = [n for n in plan.needs if n.id in need_ids]
        evidence = []
        deduplicated = set()
        with self.research.engine.connect() as connection:
            for receipt_id in sorted(selection_ids):
                receipt = (
                    connection.execute(select(selections).where(selections.c.id == receipt_id))
                    .mappings()
                    .first()
                )
                if receipt is None or receipt["case_id"] != case_id:
                    raise ValueError("Selection receipt is not in this case.")
                page = self.research.page(receipt["page_id"])
                value = json.loads(receipt["result"])
                selected = {
                    (s["need_id"], pid) for s in value["selections"] for pid in s["paragraph_ids"]
                }
                if selected and "context_windows" not in value:
                    raise ValueError("Selection needs recorded source context before judging.")
                windows = value.get("context_windows", [])
                if (
                    len(windows) != len(selected)
                    or {(c["need_id"], c["paragraph_id"]) for c in windows} != selected
                ):
                    raise ValueError("Selection context does not match its selected paragraphs.")
                source_hits = connection.execute(
                    select(hits.c.result).where(
                        hits.c.case_id == case_id, hits.c.source_id == page["source_id"]
                    )
                ).scalars()
                dates = sorted(
                    {d for raw in source_hits if (d := json.loads(raw).get("published_date"))}
                )
                for window in windows:
                    if window["need_id"] not in need_ids:
                        continue
                    start, end = window["start"], window["end"]
                    core_start, core_end = window["selected_start"], window["selected_end"]
                    if not (
                        0 <= start <= core_start < core_end <= end <= len(page["content"])
                        and page["content"][start:end] == window["quote"]
                    ):
                        raise ValueError("Evidence context differs from its source snapshot.")
                    passage_id = identity("e_", encode([page["id"], core_start, core_end]))
                    binding = connection.execute(
                        select(selection_passages.c.passage_id).where(
                            selection_passages.c.selection_id == receipt_id,
                            selection_passages.c.case_id == case_id,
                            selection_passages.c.need_id == window["need_id"],
                            selection_passages.c.passage_id == passage_id,
                        )
                    ).first()
                    if binding is None:
                        raise ValueError("Context lacks an exact selected passage binding.")
                    signature = (window["need_id"], page["id"], start, end)
                    if signature in deduplicated:
                        continue
                    deduplicated.add(signature)
                    evidence.append(
                        EvidenceContext(
                            id=identity("ev_", encode([case_id, *signature])),
                            need_id=window["need_id"],
                            selection_id=receipt_id,
                            paragraph_id=window["paragraph_id"],
                            page_id=page["id"],
                            source_id=page["source_id"],
                            source_url=self.research.source_url(page["source_id"]),
                            fetched_at=float(page["fetched_at"]),
                            reported_publication_dates=dates,
                            selected_start=core_start,
                            selected_end=core_end,
                            start=start,
                            end=end,
                            quote=window["quote"],
                            before_truncated=window["before_truncated"],
                            after_truncated=window["after_truncated"],
                        )
                    )
        return JudgmentPacket(
            case_id=case_id,
            selection_ids=sorted(selection_ids),
            needs=selected_needs,
            claims=[c for c in plan.claims if c.id in {n.claim_id for n in selected_needs}],
            evidence=sorted(evidence, key=lambda e: (e.need_id, e.page_id, e.start, e.id)),
        )

    def save(self, packet, method, model, key, result, usage, at):
        # Rebuild immediately before persistence to reject changed provenance.
        current = self.packet(
            packet.case_id, tuple(n.id for n in packet.needs), tuple(packet.selection_ids)
        )
        if current != packet:
            raise ValueError("Judgment input changed before persistence.")
        receipt_id = identity("jud_", encode([packet.case_id, key, result]))
        with self.research.engine.begin() as connection:
            connection.execute(
                insert(judgments)
                .values(
                    id=receipt_id,
                    case_id=packet.case_id,
                    method=method,
                    model=model,
                    request_key=key,
                    packet=encode(packet.model_dump()),
                    result=encode(result),
                    usage=encode(usage or {}),
                    created_at=at,
                )
                .on_conflict_do_nothing()
            )
            for selection_id in packet.selection_ids:
                connection.execute(
                    insert(judgment_selections)
                    .values(
                        judgment_id=receipt_id,
                        selection_id=selection_id,
                    )
                    .on_conflict_do_nothing()
                )
        return receipt_id

    def export(self):
        with self.research.engine.connect() as connection:
            return {
                t.name: [dict(r) for r in connection.execute(select(t)).mappings()]
                for t in [judgments, judgment_selections]
            }
