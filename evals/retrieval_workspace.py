"""Replay saved searches into a workspace; optionally read explicitly selected URLs."""

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from clear_context.providers.tavily import RetrievalFailure, TavilyKeyless
from clear_context.repositories.retrieval import RetrievalRepository, identity
from clear_context.schemas.retrieval import SavedResearchPlan, canonical_source_url
from clear_context.services.retrieval import RetrievalSession, load_retrieval_policy


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def replay(recordings: Path, repository: RetrievalRepository, ttl: int):
    cases = {v["id"]: v for v in load(recordings / "cases.json")}
    plans = {v["case_id"]: v["plan"] for v in load(recordings / "plans.json")}
    rows = load(recordings / "results.json")
    jobs = {v["id"]: v for v in load(recordings / "queries.json")}
    for case_id, case in cases.items():
        queries = [
            {
                "id": row["id"],
                "request": jobs[row["id"]]["request"],
                "need_ids": binding["need_ids"],
            }
            for row in rows
            for binding in row["bindings"]
            if binding["plan_case_id"] == case_id
        ]
        plan = SavedResearchPlan.model_validate(
            {
                "case_id": case_id,
                "claims": [
                    {k: v[k] for k in ("id", "statement", "quote")}
                    for v in case["claims"]
                ],
                "needs": [
                    {k: v[k] for k in ("id", "claim_id", "description", "status")}
                    for v in plans[case_id]["needs"]
                ],
                "queries": queries,
            }
        )
        repository.register_plan(plan)
    for row in rows:
        if row["status"] != "ok":
            continue
        retrieved_at = datetime.fromisoformat(row["retrieved_at"]).timestamp()
        for binding in row["bindings"]:
            repository.ingest_search(
                binding["plan_case_id"], row["id"], row["response"], retrieved_at
            )
        repository.save_cache(
            "search", row["cache_key"], row["response"], retrieved_at, ttl
        )


def candidate_window(content: str, anchors: list[str], radius: int = 240):
    """Select a literal context window; do not interpret its meaning."""
    for anchor in anchors:
        if not anchor.strip():
            continue
        match = re.search(re.escape(anchor), content, re.IGNORECASE)
        if match:
            start, end = (
                max(0, match.start() - radius),
                min(len(content), match.end() + radius),
            )
            return start, end, content[start:end]
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recordings", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=Path("config/retrieval.yaml"))
    parser.add_argument("--allow-live-extract", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if (args.output / "manifest.json").exists():
        raise ValueError("Output already has a run; choose a new directory.")
    selection = load(args.selection)
    policy = load_retrieval_policy(args.policy)
    # The replay workflow never issues a new search or changes saved queries.
    policy = policy.model_copy(
        update={
            "max_search_calls": 0,
            "max_extract_calls": policy.max_extract_calls
            if args.allow_live_extract
            else 0,
        }
    )
    repository = RetrievalRepository(args.workspace)
    provider = TavilyKeyless(timeout=policy.timeout_seconds)
    service = RetrievalSession(repository, provider, policy)
    observed = []
    try:
        replay(args.recordings, repository, policy.search_ttl_seconds)
        hits = repository.export()["research_hits"]
        for item in selection:
            source_id = identity("s_", canonical_source_url(item["url"]))
            if not any(
                h["case_id"] == item["case_id"]
                and h["query_id"] == item["query_id"]
                and h["source_id"] == source_id
                for h in hits
            ):
                raise ValueError("Selected source was not discovered in its case.")
            allowed = {
                n.id
                for n in repository.plan(item["case_id"]).needs
                if n.status == "planned"
            }
            if not item["need_ids"] or not set(item["need_ids"]) <= allowed:
                raise ValueError("Selection references an unknown or deferred need.")
        for item in selection:
            row = {**item, "status": "not_run"}
            try:
                source_id = identity("s_", canonical_source_url(item["url"]))
                page_id = service.read_source(source_id)
                # A second read checks real cache reuse without another provider call.
                if service.read_source(source_id) != page_id:
                    raise ValueError("Cached page identity changed.")
                page = repository.page(page_id)
                row.update(
                    status="page_read",
                    source_id=source_id,
                    page_id=page_id,
                    characters=len(page["content"]),
                )
                window = candidate_window(page["content"], item.get("anchors", []))
                if window:
                    start, end, quote = window
                    passage_id = repository.add_passage(
                        page_id, start, end, quote, item["case_id"], item["need_ids"]
                    )
                    row.update(
                        status="candidate_passage",
                        passage_id=passage_id,
                        start=start,
                        end=end,
                        quote=quote,
                        selection_method="literal_term_window_not_semantic_verification",
                    )
            except RetrievalFailure as error:
                row.update(status=error.code)
            observed.append(row)
            (args.output / "reads.json").write_text(
                json.dumps(observed, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(item["label"], row["status"], flush=True)
        manifest = {
            "calls": service.calls,
            "allow_live_extract": args.allow_live_extract,
            "policy": policy.model_dump(),
            "followups_executed": 0,
            "llm_calls": 0,
            "verdicts_produced": 0,
            "semantic_passage_validation": False,
            "scope": "Saved searches and source reads; no application integration",
        }
        (args.output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (args.output / "workspace.json").write_text(
            json.dumps(repository.export(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    finally:
        provider.close()
        repository.close()


if __name__ == "__main__":
    main()
