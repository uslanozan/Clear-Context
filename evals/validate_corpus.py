"""Validate corpus provenance, edits, spans, and counts without inference."""

import json
import re
from collections import Counter
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "corpus/v1"


def digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def validate():
    inputs = read_jsonl(ROOT / "inputs.jsonl")
    annotations = read_jsonl(ROOT / "reference/annotations.jsonl")
    sources = json.loads((ROOT / "reference/sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    by_id = {row["id"]: row for row in inputs}
    by_source = {row["id"]: row for row in sources}
    assert len(by_id) == len(inputs)
    assert len(by_source) == len(sources)
    assert {row["id"] for row in annotations} == set(by_id)
    assert len(annotations) == len(inputs) == manifest["case_count"]
    assert len(sources) == manifest["source_count"]
    assert (
        digest((ROOT / "inputs.jsonl").read_text(encoding="utf-8")) == manifest["input_file_sha256"]
    )
    labels = Counter()
    for row in annotations:
        item = by_id[row["id"]]
        assert set(item) == {"id", "language", "text"}
        assert re.fullmatch(r"cc-v1-[0-9a-f]{12}", item["id"])
        text, original = item["text"], row["original_text"]
        assert 0 < len(text) <= 20000 and "\ufffd" not in text
        assert len(text) == row["length_characters"]
        assert digest(text) == row["input_sha256"]
        assert digest(original) == row["original_sha256"]
        assert original in by_source[row["source_id"]]["selected_passages"]
        assert item["language"] == by_source[row["source_id"]]["language"]
        restored = original
        for edit in sorted(row["mutations"], key=lambda edit: edit["start"], reverse=True):
            start, before, after = edit["start"], edit["before"], edit["after"]
            assert original[start : start + len(before)] == before
            restored = restored[:start] + after + restored[start + len(before) :]
        assert restored == text, row["id"]
        assert bool(row["mutations"]) == (row["variant"] == "controlled_mutation")
        for target in row["target_claims"]:
            assert text[target["start"] : target["end"]] == target["quote"]
            assert target["expected_label"] in {"true", "false", "unknown"}
            assert target["confidence"] is None
            assert target["rationale"]
            if target["expected_label"] != "unknown":
                assert target["evidence_urls"]
            labels[target["expected_label"]] += 1
    assert dict(labels) == manifest["target_label_counts"]
    assert dict(Counter(row["language"] for row in inputs)) == manifest["language_counts"]
    assert (
        dict(Counter(row["length_bucket"] for row in annotations))
        == manifest["length_bucket_counts"]
    )
    assert (
        sum(not row["target_claims"] for row in annotations) == manifest["unannotated_case_count"]
    )
    groups = {}
    for row in annotations:
        groups.setdefault(row["group_id"], set()).add(row["split"])
    assert all(len(splits) == 1 for splits in groups.values())
    for filename in manifest["reference_files"]:
        path = ROOT / filename
        assert path.is_file(), filename
        if path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
    print(
        f"Validated {len(inputs)} inputs, {len(sources)} sources, "
        f"and {sum(labels.values())} targets."
    )


if __name__ == "__main__":
    validate()
