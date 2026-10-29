"""Bounded source units retaining exact character offsets."""

import re
from dataclasses import dataclass


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
            result.append(Paragraph(f"P{len(result) + 1:03}", start, stop, text[start:stop]))
            start = stop
    return result
