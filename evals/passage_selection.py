"""Evaluation-only lexical candidates alongside the reusable full-page selector."""

import math
import re
import unicodedata
from collections import Counter

from clear_context.providers.meta_passages import build_selection_request as request
from clear_context.schemas.passage_selection import NeedSelection, Selections, validate
from clear_context.services.paragraphs import Paragraph, paragraphs

__all__ = [
    "NeedSelection",
    "Paragraph",
    "Selections",
    "bm25",
    "candidates",
    "paragraphs",
    "request",
    "tokens",
    "validate",
]


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
