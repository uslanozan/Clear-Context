"""Score saved accuracy runs (evals/run_accuracy.py) against their case labels.

Usage: python evals/score_accuracy.py OUT_DIR
Every case gets one outcome: correct, unsettled (insufficient evidence, not assessed or a
failed run) or wrong. The rules are mechanical; whether the contradicted detail is the
one the label targets is checked by reading the reports, not by this script.
"""

import json
import sys
from collections import Counter
from pathlib import Path


def detail_statuses(report: dict | None) -> list[str]:
    if not report:
        return []
    return [
        component["status"]
        for finding in report.get("findings", [])
        for component in finding.get("components") or []
    ]


def outcome(kind: str, statuses: list[str]) -> str:
    supported = "supported" in statuses
    contradicted = "contradicted" in statuses
    if kind == "true":
        if contradicted:
            return "wrong"
        return "correct" if supported else "unsettled"
    if kind in {"false", "half"}:
        # A false claim can hold true details ("won the Nobel Prize") beside the false one.
        if contradicted:
            return "correct"
        return "wrong" if supported else "unsettled"
    if kind == "unsettleable":
        return "wrong" if supported or contradicted else "correct"
    raise ValueError(kind)


def main() -> None:
    out = Path(sys.argv[1])
    rows = []
    for path in sorted(out.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        case = record["case"]
        statuses = detail_statuses(record["report"])
        result = outcome(case["kind"], statuses) if record["status"] == "completed" else "unsettled"
        rows.append(
            {
                "id": case["id"],
                "kind": case["kind"],
                "lang": case["lang"],
                "status": record["status"],
                "outcome": result,
                "details": dict(Counter(statuses)),
                "cost_usd": record["cost_usd"],
                "seconds": record["seconds"],
            }
        )
    for row in rows:
        print(f"{row['id']:4} {row['kind']:13} {row['outcome']:9} {row['details']}")
    totals = Counter(row["outcome"] for row in rows)
    cost = sum(row["cost_usd"] or 0 for row in rows)
    print(f"\n{len(rows)} cases: {dict(totals)}; model cost ${cost:.2f}")
    (out.parent / "scores.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
