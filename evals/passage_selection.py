"""Offline paragraph selection and BM25 candidates for controlled evaluations."""

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


@dataclass(frozen=True)
class Paragraph:
    id: str
    start: int
    end: int
    text: str


def paragraphs(text: str, max_chars: int = 1000) -> list[Paragraph]:
    if max_chars < 50:
        raise ValueError("Paragraph budget is too small.")
    result = []
    for line in re.finditer(r"[^\n]+", text):
        start, end = line.start(), line.end()
        while start < end:
            while start < end and text[start].isspace():
                start += 1
            if start == end:
                break
            stop = min(end, start + max_chars)
            if stop < end:
                spaces = list(re.finditer(r"\s+", text[start:stop]))
                if spaces:
                    stop = start + spaces[-1].start()
            while stop > start and text[stop - 1].isspace():
                stop -= 1
            result.append(
                Paragraph(f"P{len(result) + 1:03}", start, stop, text[start:stop])
            )
            start = stop
    return result


def tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold().replace("\u0307", "")
    return re.findall(r"[^\W_]+", normalized)


def bm25(query: str, items: list[Paragraph], k1: float = 1.5, b: float = 0.75):
    docs = [Counter(tokens(item.text)) for item in items]
    lengths = [sum(doc.values()) for doc in docs]
    average = sum(lengths) / len(docs) if docs else 1
    terms = sorted(set(tokens(query)))
    frequencies = {term: sum(term in doc for doc in docs) for term in terms}
    ranked = []
    for index, (item, doc, length) in enumerate(zip(items, docs, lengths)):
        score = 0.0
        for term in terms:
            tf = doc[term]
            if tf:
                idf = math.log1p(
                    (len(docs) - frequencies[term] + 0.5) / (frequencies[term] + 0.5)
                )
                score += (
                    idf
                    * tf
                    * (k1 + 1)
                    / (tf + k1 * (1 - b + b * length / (average or 1)))
                )
        ranked.append({"id": item.id, "index": index, "score": score})
    return sorted(ranked, key=lambda row: (-row["score"], row["index"]))


def candidates(needs: list[dict], items: list[Paragraph], method: str, top_k: int = 3):
    allowed, diagnostics = {}, {}
    for need in needs:
        if method == "full_page":
            ids = [item.id for item in items]
        elif method == "bm25_top3_context1":
            ranked = bm25(need["description"], items)
            diagnostics[need["id"]] = ranked
            chosen = set()
            for row in [r for r in ranked if r["score"] > 0][:top_k]:
                chosen.update(
                    range(max(0, row["index"] - 1), min(len(items), row["index"] + 2))
                )
            ids = [item.id for i, item in enumerate(items) if i in chosen]
        else:
            raise ValueError("Unknown selection method.")
        allowed[need["id"]] = ids
    union = {value for ids in allowed.values() for value in ids}
    return [item for item in items if item.id in union], allowed, diagnostics


class NeedSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    need_id: str
    status: Literal["relevant", "not_found"]
    paragraph_ids: list[str]
    reason: str = Field(max_length=400)


class Selections(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    selections: list[NeedSelection]


def validate(content: str, allowed: dict[str, list[str]]) -> Selections:
    output = Selections.model_validate_json(content)
    if len(output.selections) != len(allowed) or {
        s.need_id for s in output.selections
    } != set(allowed):
        raise ValueError("Every need must appear exactly once.")
    for selection in output.selections:
        if selection.status not in {"relevant", "not_found"}:
            raise ValueError("Invalid selection status.")
        ids = selection.paragraph_ids
        if len(ids) != len(set(ids)) or not set(ids) <= set(allowed[selection.need_id]):
            raise ValueError(
                "Selection contains duplicate or unavailable paragraph IDs."
            )
        if (selection.status == "relevant") != bool(ids):
            raise ValueError("Status and selected paragraph list disagree.")
    return output


def request(
    system: str,
    page: dict,
    needs: list[dict],
    claims: list[dict],
    items: list[Paragraph],
    allowed: dict[str, list[str]],
) -> dict:
    return {
        "model": "muse-spark-1.3",
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "source_url": page["url"],
                        "needs": needs,
                        "claims": claims,
                        "allowed_paragraph_ids_by_need": allowed,
                        "paragraphs": [{"id": p.id, "text": p.text} for p in items],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "passage_selection",
                "strict": True,
                "schema": Selections.model_json_schema(),
            },
        },
        "reasoning_effort": "low",
        "max_completion_tokens": 4096,
        "store": False,
        "stream": False,
    }
