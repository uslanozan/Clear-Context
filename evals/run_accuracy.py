"""Run labeled claims through a running Clear Context server and record the reports.

Billable when the server runs with paid calls: each case is one investigation.
Usage:
  python evals/run_accuracy.py CASES.json OUT_DIR [--server URL] [--budget USD] [--execute]
Without --execute it prints the plan and makes no requests. Cases already saved in OUT_DIR
are skipped, so a stopped run continues without repeating paid work.
"""

import argparse
import json
import time
import urllib.request
from pathlib import Path


def call(server: str, path: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        server + path, data=data, headers={"Content-Type": "application/json"} if data else {}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def model_cost(usage: list[dict], prices: dict) -> float | None:
    total = 0.0
    for item in usage:
        price = prices["per_million_tokens"].get(item["model_id"])
        if not price or item.get("input_tokens") is None or item.get("output_tokens") is None:
            return None
        cached = min(item.get("cached_input_tokens") or 0, item["input_tokens"])
        cached_rate = price["cached_input"] if price["cached_input"] is not None else price["input"]
        total += (
            (item["input_tokens"] - cached) * price["input"]
            + cached * cached_rate
            + item["output_tokens"] * price["output"]
        ) / 1_000_000
    return total


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cases", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    parser.add_argument("--budget", type=float, default=8.0, help="Stop before exceeding (USD).")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    cases = json.loads(args.cases.read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    health = call(args.server, "/api/health")
    print(
        f"{len(cases)} cases; server mode {health['mode']}, research {health['research_enabled']}"
    )
    if not args.execute:
        print("Dry run: no investigations started. Add --execute to run.")
        return
    if health["mode"] != "meta" or not health["research_enabled"]:
        raise SystemExit("The server must run with paid calls and research enabled.")
    prices = call(args.server, "/api/prices")

    spent = 0.0
    for saved in args.out.glob("*.json"):
        spent += json.loads(saved.read_text(encoding="utf-8")).get("cost_usd") or 0.0
    for case in cases:
        target = args.out / f"{case['id']}.json"
        if target.exists():
            continue
        # Keep a margin of roughly two runs before the budget.
        if spent > args.budget - 0.3:
            print(f"Budget reached at ${spent:.2f}; stopping before {case['id']}.")
            break
        started = time.monotonic()
        created = call(
            args.server, "/api/investigations", {"text": case["text"], "research_mode": "balanced"}
        )
        while True:
            row = call(args.server, f"/api/investigations/{created['id']}")
            if row["status"] in {"completed", "failed"}:
                break
            time.sleep(3)
        report = None
        if row["status"] == "completed":
            report = call(args.server, f"/api/investigations/{created['id']}/report")
        usage = (report or row).get("model_usage") or []
        cost = model_cost(usage, prices)
        spent += cost or 0.0
        record = {
            "case": case,
            "investigation_id": created["id"],
            "status": row["status"],
            "error_code": row.get("error_code"),
            "seconds": round(time.monotonic() - started, 1),
            "cost_usd": cost,
            "report": report,
        }
        target.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        shown = f"${cost:.3f}" if cost is not None else "cost unknown"
        print(f"{case['id']} {row['status']} {record['seconds']}s {shown}; total ${spent:.2f}")


if __name__ == "__main__":
    main()
