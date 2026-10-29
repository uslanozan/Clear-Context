"""Evaluate saved selection receipts; live judging requires explicit opt-in."""

import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter

from clear_context.core.judges import load_judge
from clear_context.core.settings import Settings, load_model_selections
from clear_context.providers.meta_structured import (
    MetaStructuredProvider,
    ModelResponseFailure,
)
from clear_context.repositories.judgment import JudgmentRepository
from clear_context.repositories.retrieval import RetrievalRepository
from clear_context.services.evidence_judgment import (
    EvidenceJudgmentService,
    JudgmentJob,
)


class OfflineProvider:
    async def complete(self, payload, timeout):
        raise ModelResponseFailure("live_judging_disabled")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--jobs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, default=Path("config/judges.yaml"))
    parser.add_argument("--prompts", type=Path, default=Path("config/prompts.yaml"))
    parser.add_argument("--allow-live-judging", action="store_true")
    args = parser.parse_args()
    if not args.workspace.is_file() or args.output.exists():
        raise ValueError("Use an existing workspace and a new output directory.")
    method, limits, system, contract = load_judge(args.catalog, args.prompts)
    settings = Settings() if args.allow_live_judging else Settings(_env_file=None)
    model = load_model_selections(settings)["judge"]
    if args.allow_live_judging:
        provider = MetaStructuredProvider(
            settings.model_copy(update={"app_mode": "meta"})
        )
    else:
        limits = limits.model_copy(update={"max_model_calls": 0})
        provider = OfflineProvider()
    jobs = [
        JudgmentJob(v["case_id"], tuple(v["need_ids"]), tuple(v["selection_ids"]))
        for v in json.loads(args.jobs.read_text(encoding="utf-8"))
    ]
    research = RetrievalRepository(args.workspace)
    repository = JudgmentRepository(research)
    try:
        service = EvidenceJudgmentService(
            repository,
            provider,
            method,
            limits,
            system,
            model,
            response_contract=contract,
        )
        prepared = [service.prepare(job) for job in jobs]
        args.output.mkdir(parents=True)
        for i, (packet, request, _) in enumerate(prepared, 1):
            for prefix, value in [("input", packet.model_dump()), ("request", request)]:
                (args.output / f"{prefix}-{i:02}.json").write_text(
                    json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
                )
        started = perf_counter()
        rows = asyncio.run(service.assess(jobs))
        manifest = {
            "method": method,
            "response_contract": contract,
            "model": model.api_model_id,
            "limits": limits.model_dump(),
            "actual_model_calls": service.calls,
            "max_active_requests": service.max_active,
            "batch_wall_seconds": round(perf_counter() - started, 3),
            "search_calls": 0,
            "extract_calls": 0,
            "scope": "provided_evidence_only",
            "application_graph_connected": False,
            "source_reliability_assessed": False,
        }
        for name, value in [
            ("results.json", rows),
            ("manifest.json", manifest),
            ("judgments.json", repository.export()),
            ("raw-responses.json", getattr(provider, "response_records", [])),
            ("response-metadata.json", getattr(provider, "response_metadata", [])),
        ]:
            (args.output / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        print(json.dumps(manifest))
    finally:
        research.close()


if __name__ == "__main__":
    main()
