"""Select source-bound passages from a saved workspace with bounded concurrency."""

import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

from clear_context.core.passage_selectors import load_selector
from clear_context.core.settings import Settings, load_model_selections
from clear_context.providers.meta_passages import MetaPassageProvider, SelectionFailure
from clear_context.repositories.retrieval import RetrievalRepository
from clear_context.services.passage_selection import (
    PassageSelectionService,
    SelectionJob,
)


class OfflineProvider:
    async def select(self, payload, timeout):
        raise SelectionFailure("live_selection_disabled")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--catalog", type=Path, default=Path("config/passage_selectors.yaml")
    )
    parser.add_argument("--prompts", type=Path, default=Path("config/prompts.yaml"))
    parser.add_argument("--allow-live-selection", action="store_true")
    args = parser.parse_args()
    if not args.workspace.is_file():
        raise ValueError("Workspace must already exist.")
    if (args.output / "manifest.json").exists():
        raise ValueError(
            "Choose a new output directory; do not overwrite a recorded run."
        )
    method, profile, limits, system = load_selector(args.catalog, args.prompts)
    settings = Settings() if args.allow_live_selection else Settings(_env_file=None)
    model = load_model_selections(settings)["research"]
    if args.allow_live_selection:
        provider = MetaPassageProvider(settings.model_copy(update={"app_mode": "meta"}))
    else:
        limits = limits.model_copy(update={"max_model_calls": 0})
        provider = OfflineProvider()
    values = json.loads(args.jobs.read_text(encoding="utf-8"))
    jobs = [
        SelectionJob(v["case_id"], v["page_id"], tuple(v["need_ids"])) for v in values
    ]
    args.output.mkdir(parents=True, exist_ok=True)
    repo = RetrievalRepository(args.workspace)
    try:
        service = PassageSelectionService(
            repo, provider, method, profile, limits, system, model
        )
        for i, job in enumerate(jobs):
            _, _, payload, _ = service.prepare(job)
            (args.output / f"request-{i + 1:02}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        started = perf_counter()
        rows = asyncio.run(service.select_pages(jobs))
        elapsed = perf_counter() - started
        manifest = {
            "method": method,
            "model": model.api_model_id,
            "limits": limits.model_dump(),
            "actual_model_calls": service.calls,
            "max_active_requests": service.max_active,
            "scheduling_mode": "all_at_once"
            if limits.max_concurrency is None
            else "bounded_concurrency",
            "batch_wall_seconds": round(elapsed, 3),
            "search_calls": 0,
            "extract_calls": 0,
            "scope": "Standalone workspace; no app graph or UI integration",
        }
        for name, value in (
            ("results.json", rows),
            ("manifest.json", manifest),
            ("response-metadata.json", getattr(provider, "response_metadata", [])),
            ("raw-responses.json", getattr(provider, "response_records", [])),
            ("workspace.json", repo.export()),
        ):
            (args.output / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(manifest, ensure_ascii=False))
    finally:
        repo.close()


if __name__ == "__main__":
    main()
