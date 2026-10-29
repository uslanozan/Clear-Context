"""Literal, bounded context restoration at artificial source cuts."""

import pytest

from clear_context.services.paragraphs import Paragraph
from clear_context.services.passage_context import source_context


def unit(text, start, end):
    return Paragraph("P001", start, end, text[start:end])


def test_restores_sentence_prefix_negation_and_continuation_without_next_sentence():
    text = "Intro. The report does not say the towns touch. Another subject."
    start, end = text.index("say"), text.index("touch") + 2
    context = source_context(text, unit(text, start, end), "n1", 500, 500)
    assert context.quote == "The report does not say the towns touch."
    assert text[context.start : context.end] == context.quote
    assert context.selected_start == start and context.selected_end == end
    assert not context.before_truncated and not context.after_truncated


def test_does_not_pad_a_complete_sentence_or_cross_into_menu_lines():
    text = "Menu\nThe city is 8 km away. Another subject.\nFooter"
    start = text.index("The city")
    end = text.index(". Another") + 1
    context = source_context(text, unit(text, start, end), "n1", 500, 500)
    assert context.quote == "The city is 8 km away."
    assert context.start == start and context.end == end


def test_budgets_are_hard_and_unfinished_context_is_explicit():
    text = "A long explanation " * 20 + "ends here."
    start = text.index("explanation", 80)
    end = start + len("explanation")
    context = source_context(text, unit(text, start, end), "n1", 12, 16)
    assert context.start >= start - 12 and context.end <= end + 16
    assert context.before_truncated and context.after_truncated
    assert text[context.start : context.end] == context.quote


def test_decimal_does_not_end_a_sentence_and_unicode_offsets_are_literal():
    text = "Önce. Ölçüm 8.5 km ve belirsiz kabul edildi. Sonra."
    start, end = text.index("Ölçüm"), text.index("8.5")
    context = source_context(text, unit(text, start, end), "n1", 500, 500)
    assert context.quote == "Ölçüm 8.5 km ve belirsiz kabul edildi."


def test_zero_budgets_preserve_selection_and_report_unresolved_boundary():
    text = "A sentence continues here."
    core = unit(text, 2, 10)
    context = source_context(text, core, "n1", 0, 0)
    assert context.quote == core.text
    assert context.before_truncated and context.after_truncated


def test_mismatched_quotes_and_invalid_ranges_are_rejected():
    with pytest.raises(ValueError):
        source_context("Original", Paragraph("P001", 0, 4, "Fake"), "n1", 10, 10)
    with pytest.raises(ValueError):
        source_context("Original", Paragraph("P001", -1, 4, "Orig"), "n1", 10, 10)
