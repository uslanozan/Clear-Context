"""Restore bounded context around artificial cuts without changing model selections."""

import re
from dataclasses import dataclass

from clear_context.services.paragraphs import Paragraph

SENTENCE_END = re.compile(r"""[.!?。！？](?:["'”’\)\]]*)(?=\s|$)""")


@dataclass(frozen=True)
class PassageContext:
    need_id: str
    paragraph_id: str
    selected_start: int
    selected_end: int
    start: int
    end: int
    quote: str
    before_truncated: bool
    after_truncated: bool


def source_context(
    text: str, paragraph: Paragraph, need_id: str, before_chars: int, after_chars: int
) -> PassageContext:
    if before_chars < 0 or after_chars < 0:
        raise ValueError("Context budgets cannot be negative.")
    if not 0 <= paragraph.start < paragraph.end <= len(text):
        raise ValueError("Paragraph offsets are outside the source.")
    if text[paragraph.start : paragraph.end] != paragraph.text:
        raise ValueError("Paragraph differs from the source.")
    line_start = text.rfind("\n", 0, paragraph.start) + 1
    line_end = text.find("\n", paragraph.end)
    if line_end < 0:
        line_end = len(text)
    prefix = text[line_start : paragraph.start]
    suffix = text[paragraph.end : line_end]

    # Only extend artificial cuts inside one source line, never unrelated headings.
    boundaries = list(SENTENCE_END.finditer(prefix))
    desired_start = line_start + boundaries[-1].end() if boundaries else line_start
    while desired_start < paragraph.start and text[desired_start].isspace():
        desired_start += 1
    core_ends_sentence = bool(re.search(r"""[.!?。！？]["'”’\)\]]*$""", paragraph.text))
    next_end = SENTENCE_END.search(suffix)
    desired_end = paragraph.end
    if suffix.strip() and not core_ends_sentence:
        desired_end = paragraph.end + next_end.end() if next_end else line_end

    start = max(desired_start, paragraph.start - before_chars)
    end = min(desired_end, paragraph.end + after_chars)
    # If a budget cuts a word, retain only complete added words.
    if start > desired_start and start < paragraph.start and not text[start - 1].isspace():
        while start < paragraph.start and not text[start].isspace():
            start += 1
    while start < paragraph.start and text[start].isspace():
        start += 1
    if end < desired_end and end > paragraph.end and not text[end].isspace():
        while end > paragraph.end and not text[end - 1].isspace():
            end -= 1
    while end > paragraph.end and text[end - 1].isspace():
        end -= 1
    return PassageContext(
        need_id,
        paragraph.id,
        paragraph.start,
        paragraph.end,
        start,
        end,
        text[start:end],
        start > desired_start,
        end < desired_end,
    )
