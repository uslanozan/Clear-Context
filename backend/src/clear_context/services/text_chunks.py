"""Partition original text without changing its source coordinates."""

import re
from dataclasses import dataclass

from clear_context.domain.investigation import TextSpan


@dataclass(frozen=True)
class TextChunk:
    start: int
    end: int


def boundary(text: str, start: int, end: int, preferred: int) -> int:
    lower = start + max(1, (preferred - start) // 2)
    for pattern in (r"\n[ \t]*\n", r"(?<=[.!?])\s+", r"\s+"):
        candidates = [
            start + match.end()
            for match in re.finditer(pattern, text[start:preferred])
            if lower <= start + match.end() < end
        ]
        if candidates:
            return candidates[-1]
    return min(preferred, end - 1)


def partition(text: str, maximum: int) -> list[TextChunk]:
    chunks = []
    start = 0
    while start < len(text):
        end = (
            len(text)
            if len(text) - start <= maximum
            else boundary(text, start, len(text), start + maximum)
        )
        chunks.append(TextChunk(start, end))
        start = end
    return chunks


def bisect(text: str, chunk: TextChunk) -> tuple[TextChunk, TextChunk]:
    middle = boundary(text, chunk.start, chunk.end, (chunk.start + chunk.end) // 2)
    return TextChunk(chunk.start, middle), TextChunk(middle, chunk.end)


def context_ranges(text: str, chunk: TextChunk, maximum: int) -> list[TextChunk]:
    candidates = [
        TextChunk(0, min(maximum, chunk.start)),
        TextChunk(max(0, chunk.start - maximum), chunk.start),
        TextChunk(chunk.end, min(len(text), chunk.end + maximum)),
    ]
    return list(dict.fromkeys(item for item in candidates if item.start < item.end))


def visible_ranges(ranges: list[TextChunk]) -> list[TextChunk]:
    merged = []
    for item in sorted(ranges, key=lambda value: value.start):
        if merged and item.start <= merged[-1].end:
            merged[-1] = TextChunk(merged[-1].start, max(merged[-1].end, item.end))
        else:
            merged.append(item)
    return merged


def locate_quote(
    text: str, quote: str, ranges: list[TextChunk], *, overlaps: TextChunk | None = None
) -> TextSpan:
    if not quote.strip():
        raise ValueError("Blank source quote.")
    for item in ranges:
        position = text.find(quote, item.start, item.end)
        while position >= 0:
            end = position + len(quote)
            if overlaps is None or (position < overlaps.end and end > overlaps.start):
                return TextSpan(start=position, end=end, text=quote)
            position = text.find(quote, position + 1, item.end)
    raise ValueError("Quote is absent from the allowed source ranges.")
