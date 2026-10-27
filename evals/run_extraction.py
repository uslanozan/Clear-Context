"""Run one bounded extraction pass; reference labels are never loaded here."""

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx
import yaml
from clear_context.core.prompts import load_claim_extraction_prompt
from clear_context.core.settings import (
    PROJECT_ROOT,
    Settings,
    load_model_selections,
    resolve_path,
)
from clear_context.providers.errors import ProviderError
from clear_context.providers.meta import MetaInvestigationProvider

INPUTS = PROJECT_ROOT / "evals/corpus/v1/inputs.jsonl"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class RecordingTransport(httpx.BaseTransport):
    def __init__(self):
        self.inner = httpx.HTTPTransport(retries=0)
        self.receipt = {}
        self.receipts = []

    def handle_request(self, request):
        response = self.inner.handle_request(request)
        response.read()
        self.receipt = {"http_status": response.status_code}
        if response.status_code == 200:
            try:
                body = response.json()
                choice = (body.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                self.receipt.update(
                    response_model=body.get("model"),
                    usage=body.get("usage"),
                    finish_reason=choice.get("finish_reason"),
                    content=message.get("content"),
                    refused=bool(message.get("refusal")),
                )
            except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                self.receipt["invalid_response_body"] = True
        self.receipts.append(self.receipt)
        return response

    def close(self):
        self.inner.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Make billable API requests.")
    parser.add_argument("--limit", type=int, default=36, choices=range(1, 37), metavar="1..36")
    parser.add_argument("--model", help="Override the claim-extraction model alias for this run.")
    parser.add_argument("--prompt-version", help="Select a prompt version without editing .env.")
    parser.add_argument("--max-extraction-calls", type=int)
    parser.add_argument("--max-total-output-tokens", type=int)
    parser.add_argument("--max-extraction-seconds", type=float)
    parser.add_argument("--case-id", action="append", help="Select a corpus ID; repeat as needed.")
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        choices=range(128, 4097),
        metavar="128..4096",
    )
    parser.add_argument(
        "--retry-truncated-from",
        type=Path,
        help="Select only token-limit failures from a previous local run.",
    )
    args = parser.parse_args()
    overrides = (
        {"meta_max_completion_tokens": args.max_completion_tokens}
        if args.max_completion_tokens is not None
        else {}
    )
    if args.model:
        overrides["model_claim_extraction"] = args.model
    for name, value in {
        "prompt_claim_extraction": args.prompt_version,
        "extraction_max_calls": args.max_extraction_calls,
        "extraction_max_output_tokens": args.max_total_output_tokens,
        "extraction_max_seconds": args.max_extraction_seconds,
    }.items():
        if value is not None:
            overrides[name] = value
    settings = Settings(**overrides)
    selection = load_model_selections(settings)["claim_extraction"]
    prompt = load_claim_extraction_prompt(settings)
    capacity = (
        settings.meta_max_claims
        if prompt.version == "v1"
        else settings.extraction_response_capacity
    )
    input_bytes = INPUTS.read_bytes()
    inputs = [json.loads(line) for line in input_bytes.decode("utf-8").splitlines()]
    if args.case_id:
        selected_ids = set(args.case_id)
        if not selected_ids.issubset({item["id"] for item in inputs}):
            raise ValueError("Unknown corpus case ID.")
        inputs = [item for item in inputs if item["id"] in selected_ids]
    baseline = None
    if args.retry_truncated_from:
        previous = resolve_path(args.retry_truncated_from).resolve()
        if not previous.is_relative_to((PROJECT_ROOT / "evals/runs").resolve()):
            raise ValueError("The previous run must be under evals/runs.")
        baseline = json.loads((previous / "run.json").read_text(encoding="utf-8"))
        unchanged = {
            "configured_model": selection.api_model_id,
            "prompt_sha256": prompt.sha256,
            "max_claims": capacity,
            "reasoning_effort": "low",
            "timeout_seconds": settings.meta_timeout_seconds,
            "input_file_bytes_sha256": sha256(input_bytes).hexdigest(),
        }
        if any(baseline.get(key) != value for key, value in unchanged.items()):
            raise ValueError("Baseline inputs, model, prompt, and other limits must match.")
        if settings.meta_max_completion_tokens <= baseline["max_completion_tokens"]:
            raise ValueError("The selected rerun must increase the completion budget.")
        previous_records = [
            json.loads(line)
            for line in (previous / "results.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        failed = {
            row["id"]: row
            for row in previous_records
            if row.get("error_code") == "meta_incomplete_output"
        }
        inputs = [item for item in inputs if item["id"] in failed]
        if not inputs or len(inputs) != len(failed):
            raise ValueError("Expected matching token-limit failures in the corpus.")
        if any(item["text"] != failed[item["id"]]["text"] for item in inputs):
            raise ValueError("Selected input text changed since the baseline.")
    inputs = inputs[: args.limit]
    for item in inputs:
        if set(item) != {"id", "language", "text"} or not 0 < len(item["text"]) <= 20000:
            raise ValueError("Invalid corpus input.")
    with resolve_path(settings.model_catalog_path).open(encoding="utf-8-sig") as stream:
        catalog = yaml.safe_load(stream)
    metadata = {
        "configured_model": selection.api_model_id,
        "prompt_version": prompt.version,
        "prompt_sha256": prompt.sha256,
        "rendered_system_prompt": prompt.system,
        "input_file_bytes_sha256": sha256(input_bytes).hexdigest(),
        "planned_inputs": len(inputs),
        "maximum_api_calls": len(inputs)
        * (1 if prompt.version == "v1" else settings.extraction_max_calls),
        "max_claims": capacity,
        "max_completion_tokens": settings.meta_max_completion_tokens,
        "reasoning_effort": "low",
        "timeout_seconds": settings.meta_timeout_seconds,
        "retries": 0,
        "price_snapshot": catalog["models"][selection.alias].get("price"),
        "price_snapshot_date": catalog.get("checked_on"),
        "reference_labels_loaded": False,
        "scope": "Extraction only; no retrieval, truth judging, or semantic accuracy score.",
        "comparison_parent": str(args.retry_truncated_from) if baseline else None,
        "baseline_max_completion_tokens": baseline["max_completion_tokens"] if baseline else None,
        "extraction_limits": {
            "chunk_characters": settings.extraction_chunk_characters,
            "minimum_chunk_characters": settings.extraction_min_chunk_characters,
            "context_characters_per_window": settings.extraction_context_characters,
            "maximum_calls_per_input": settings.extraction_max_calls,
            "maximum_output_tokens_per_input": settings.extraction_max_output_tokens,
            "maximum_seconds_per_input": settings.extraction_max_seconds,
        }
        if prompt.version != "v1"
        else None,
    }
    if not args.execute:
        print(json.dumps(metadata, ensure_ascii=False, indent=2))
        print("Dry run only. Add --execute to make API requests.")
        return

    # Constructing the provider enforces the existing paid-call and API-key guards.
    transport = RecordingTransport()
    provider = MetaInvestigationProvider(settings, selection, transport, prompt=prompt)
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = PROJECT_ROOT / "evals/runs" / run_id
    output.mkdir(parents=True, exist_ok=False)
    metadata["started_at"] = datetime.now(UTC).isoformat()
    write_json(output / "run.json", metadata)
    records = []
    try:
        with (output / "results.jsonl").open("x", encoding="utf-8") as stream:
            for index, item in enumerate(inputs, start=1):
                transport.receipt = {}
                transport.receipts = []
                started = perf_counter()
                record = {
                    "id": item["id"],
                    "language": item["language"],
                    "text": item["text"],
                }
                try:
                    extraction = provider.extract_claims(item["text"])
                    partial = extraction.coverage and extraction.coverage.status == "partial"
                    record.update(
                        status="partial" if partial else "validated",
                        extraction=extraction.model_dump(mode="json"),
                    )
                    if partial:
                        errors = [
                            chunk.reason
                            for chunk in extraction.coverage.chunks
                            if chunk.status == "partial" and chunk.reason
                        ]
                        if errors:
                            record["error_code"] = errors[0]
                except ProviderError as error:
                    record.update(status="rejected", error_code=error.code)
                record["elapsed_seconds"] = round(perf_counter() - started, 3)
                coverage = record.get("extraction", {}).get("coverage")
                record["attempted_model_calls"] = coverage["model_calls"] if coverage else 1
                record["provider_receipt"] = transport.receipt
                record["provider_receipts"] = transport.receipts
                stream.write(json.dumps(record, ensure_ascii=False) + "\n")
                stream.flush()
                records.append(record)
                print(
                    f"{index}/{len(inputs)} {item['id']}: {record['status']} "
                    f"{record.get('error_code', '')} ({record['elapsed_seconds']}s)",
                    flush=True,
                )
                if record.get("error_code") in {
                    "meta_authentication_failed",
                    "meta_access_denied",
                    "meta_rate_limited",
                    "meta_connection_failed",
                    "meta_timeout",
                }:
                    print(
                        "Stopped after a service/transport error; no automatic retry.",
                        flush=True,
                    )
                    break
    finally:
        transport.close()
        receipts = [receipt for row in records for receipt in row["provider_receipts"]]
        summary = {
            "run_id": run_id,
            "finished_at": datetime.now(UTC).isoformat(),
            "planned_inputs": len(inputs),
            "recorded_inputs": len(records),
            "recorded_calls": sum(row["attempted_model_calls"] for row in records),
            "received_responses": len(receipts),
            "statuses": dict(Counter(row["status"] for row in records)),
            "errors": dict(Counter(row["error_code"] for row in records if "error_code" in row)),
            "accepted_claims": sum(
                len(row.get("extraction", {}).get("claims", [])) for row in records
            ),
            "recorded_elapsed_seconds": round(sum(row["elapsed_seconds"] for row in records), 3),
            "model_response_ids": dict(
                Counter(receipt.get("response_model") or "not_reported" for receipt in receipts)
            ),
            "token_totals": {},
            "missing_usage_receipts": sum(not receipt.get("usage") for receipt in receipts)
            + sum(row["attempted_model_calls"] for row in records)
            - len(receipts),
            "accuracy_measured": False,
            "billing_note": (
                "Provider usage includes rejected outputs when reported. Billing is authoritative."
            ),
        }
        for field in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            summary["token_totals"][field] = sum(
                (receipt.get("usage") or {}).get(field, 0) or 0 for receipt in receipts
            )
        write_json(output / "summary.json", summary)
        print(f"Results: {output}", flush=True)
        print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
