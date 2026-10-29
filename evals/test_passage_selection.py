"""Paragraph provenance and controlled candidate filtering checks, without inference."""

import json

import pytest
from passage_selection import bm25, candidates, paragraphs, validate


def test_paragraphs_preserve_every_nonwhitespace_character_and_offsets():
    text = "  Başlık\n\nSafranbolu bir ilçedir. " + "Açıklama ve ayrıntılar. " * 90
    items = paragraphs(text, max_chars=100)
    assert all(text[p.start : p.end] == p.text and len(p.text) <= 100 for p in items)
    assert "".join("".join(p.text.split()) for p in items) == "".join(text.split())
    assert len({p.id for p in items}) == len(items)


def test_bm25_ranks_the_predicate_and_keeps_neighboring_context():
    items = paragraphs(
        "Menu\nThe university founding date is 2007.\n"
        "Its faculty was founded earlier.\nTourism news"
    )
    ranked = bm25("university founding date", items)
    assert ranked[0]["id"] == "P002"
    chosen, allowed, _ = candidates(
        [{"id": "n1", "description": "university founding date"}],
        items,
        "bm25_top3_context1",
        top_k=1,
    )
    assert allowed == {"n1": ["P001", "P002", "P003"]}
    assert [p.id for p in chosen] == allowed["n1"]


def test_no_lexical_match_is_explicit_and_full_page_keeps_all_candidates():
    items = paragraphs("A municipality page\nGeneral information")
    chosen, allowed, _ = candidates(
        [{"id": "n1", "description": "volcano eruption"}], items, "bm25_top3_context1"
    )
    assert chosen == [] and allowed == {"n1": []}
    chosen, _, _ = candidates(
        [{"id": "n1", "description": "volcano eruption"}], items, "full_page"
    )
    assert chosen == items


@pytest.mark.parametrize(
    "selections",
    [
        [],
        [
            {
                "need_id": "unknown",
                "status": "not_found",
                "paragraph_ids": [],
                "reason": "",
            }
        ],
        [
            {
                "need_id": "n1",
                "status": "relevant",
                "paragraph_ids": ["P999"],
                "reason": "",
            }
        ],
        [{"need_id": "n1", "status": "relevant", "paragraph_ids": [], "reason": ""}],
        [
            {
                "need_id": "n1",
                "status": "not_found",
                "paragraph_ids": ["P001"],
                "reason": "",
            }
        ],
        [
            {
                "need_id": "n1",
                "status": "relevant",
                "paragraph_ids": ["P001", "P001"],
                "reason": "",
            }
        ],
    ],
)
def test_invalid_bindings_or_inconsistent_status_are_rejected(selections):
    with pytest.raises(ValueError):
        validate(json.dumps({"selections": selections}), {"n1": ["P001"]})
