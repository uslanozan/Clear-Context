"""Export recorded investigations from a running server into the static demo's data folder.

Usage:
  python packaging/demo/export_demo.py OUT_DIR --server URL ID [ID ...]
Only GET requests are made, so nothing runs and nothing is billed. Settings and API keys are
never exported. Running it again with another server adds to the same folder's history.
"""

import argparse
import json
import re
import urllib.request
import uuid
from pathlib import Path


def get(server: str, path: str):
    with urllib.request.urlopen(server + path, timeout=30) as response:
        return json.load(response)


# The report shows 180 characters on each side of a quote; keep a little more and drop the rest,
# so the public demo does not republish whole third-party pages.
CONTEXT = 200
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def trimmed_sources(report: dict) -> list[dict]:
    excerpts: dict[str, list[str]] = {}
    for item in report["evidence"]:
        excerpts.setdefault(item["source_id"], []).append(item["excerpt"])
    sources = []
    for source in report["sources"]:
        text = source["content"]
        spans = []
        for excerpt in excerpts.get(source["id"], []):
            start = text.find(excerpt)
            if start >= 0:
                spans.append([max(0, start - CONTEXT), start + len(excerpt) + CONTEXT])
        spans.sort()
        merged: list[list[int]] = []
        for start, end in spans:
            if merged and start <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], end)
            else:
                merged.append([start, end])
        windows = "\n…\n".join(text[start:end] for start, end in merged)
        quoted = excerpts.get(source["id"], [])
        # Addresses of the page's authors or readers are removed unless a quote contains them.
        windows = EMAIL.sub(
            lambda m, quoted=quoted: (
                m.group(0) if any(m.group(0) in q for q in quoted) else "[email removed]"
            ),
            windows,
        )
        sources.append({**source, "content": windows})
    return sources


def write(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("ids", nargs="*")
    parser.add_argument(
        "--group",
        action="append",
        default=[],
        metavar="NAME=ID,ID",
        help="File exported reports under a history group; applies to the whole folder.",
    )
    parser.add_argument("--server", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    # Only exporting reports needs a server; --group alone rewrites the folder.
    if args.ids:
        health = get(args.server, "/api/health")
        # The demo reports live mode so the app shows reports as they were; it can start nothing.
        write(
            args.out / "health.json",
            {
                "status": "ok",
                "version": health.get("version"),
                "mode": "meta",
                "paid_api_calls_enabled": True,
                "research_enabled": True,
                "default_research_mode": "balanced",
            },
        )
        write(args.out / "prices.json", get(args.server, "/api/prices"))

    history_path = args.out / "history.json"
    history = json.loads(history_path.read_text(encoding="utf-8")) if history_path.exists() else []
    for investigation_id in args.ids:
        row = get(args.server, f"/api/investigations/{investigation_id}")
        if row["status"] != "completed":
            raise SystemExit(f"{investigation_id} is {row['status']}; only completed runs.")
        # Groups come only from --group, never from the source database.
        row["group_id"] = None
        base = args.out / "investigations" / investigation_id
        write(base.with_suffix(".json"), row)
        for part in ("steps", "research", "report"):
            data = get(args.server, f"/api/investigations/{investigation_id}/{part}")
            if part == "report":
                data["sources"] = trimmed_sources(data)
            write(base / f"{part}.json", data)
        history = [item for item in history if item["id"] != investigation_id] + [row]
        print(f"exported {investigation_id}: {(row.get('title') or row['text'])[:60]}")
    groups, members = [], {}
    for position, spec in enumerate(args.group):
        name, _, ids = spec.partition("=")
        group_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"clear-context-demo/{name}"))
        groups.append({"id": group_id, "name": name, "position": position})
        members |= {
            investigation_id: group_id for investigation_id in ids.split(",") if investigation_id
        }
    if args.group:
        for item in history:
            item["group_id"] = members.get(item["id"])
            write(args.out / "investigations" / f"{item['id']}.json", item)
        write(args.out / "groups.json", groups)
    elif not (args.out / "groups.json").exists():
        write(args.out / "groups.json", [])
    history.sort(key=lambda item: item["created_at"], reverse=True)
    write(history_path, history)
    print(f"{len(history)} reports in {args.out}")


if __name__ == "__main__":
    main()
