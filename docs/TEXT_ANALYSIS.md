# How text analysis works today

Updated October 27, 2026. V2 implements bounded chunk processing. Extraction is not factual verification.

## Implemented flow

1. The browser submits trimmed text (1-20,000 characters) after an explicit user action.
2. LangGraph runs `extract_claims -> evaluate_evidence -> validate_report`. Chunk processing
   happens inside extraction; the UI does not invent intermediate node events.
3. Short inputs stay whole. Long inputs are partitioned under a 600-character target budget,
   preferring paragraph, sentence, then whitespace boundaries. Every original character is
   retained. Boundary regexes partition text; they do not extract claims. This is a character
   budget, not a tokenizer-based estimate.
4. Each request sends target plus bounded document-head, previous, and next context windows.
   Each context window is at most 600 Unicode characters. The model must identify factual
   claims in target, not summarize the most prominent facts or verify/correct them.
5. Each claim contains an exact source quote, a separate interpreted `statement`, context
   quotes, and an ambiguity flag. A quote may cross into adjacent supplied context, but must
   overlap target. Quotes entirely outside target or across unseen gaps are rejected.
6. There is no document-wide eight-claim limit. The default response capacity is 24. A response
   reaching capacity, reporting `has_more`, or truncating can cause only that target to split.
   At minimum size, unresolved capacity remains partial rather than silently complete.
7. Per-document guards bound calls (24), output tokens (32,768), and time (120 seconds).
   Remaining time constrains each HTTP timeout; this is not cancellation of an already running
   task. Unknown token usage retains its conservative reservation. Operational defaults are
   provisional bounds, not measured quality guarantees.
8. Accepted claims are deduplicated by exact source span plus interpreted statement, sorted
   by source position, and saved with coverage and usage. Semantic deduplication is absent.
   Invalid/deferred ranges remain visible in a partial report. The UI highlights source quotes
   and distinguishes incomplete extraction from unresolved factual findings.
9. Evidence evaluation retrieves nothing yet. Findings remain unresolved; there is no search,
   truth judge, media analysis, or automatic correction of intentionally altered facts.

V2 may return no claims for nonfactual input. Empty output or processed ranges do not prove
there were no missed claims. Prompt v1 retains the legacy single-call string-list contract
for baseline reproduction.

## Provenance and context

Offsets use zero-based Python Unicode code points with exclusive ends. The browser converts
input with `Array.from` before highlighting, so emoji do not shift positions as UTF-16 offsets
would. The exact quote stays in `text`; the model's self-contained interpretation stays in
`statement`. Only source/context quotations receive literal source verification.

```python
span = locate_quote(text, item.quote, visible_ranges([chunk, *context]), overlaps=chunk)
```

This does not establish semantic completeness, qualifier retention, attribution, or truth.
Repeated matches inside a target use the first matching location and are marked ambiguous.
Cross-range ambiguity is still a limitation. A name inserted into a normalized statement is
a model interpretation, not a verified entity-resolution record.

`extraction_coverage.status=processed` means all target ranges reached normal responses.
`partial` means one or more ranges were invalid, deferred, or could not finish under limits.
A model reporting `has_more=false` is not independent evidence of exhaustive extraction.

## Example boundaries

A passage might say: "The fictional Cedar Museum opened in 2024. It displays 120 objects.
According to its director, entry is free for adult students on Tuesdays."

The source quote must preserve original wording. A separate statement can clarify that `It`
refers to the museum using a recorded context quote. It must not silently drop "according to
its director", "adult students", or "Tuesdays". Today's deterministic checks cannot prove
that the interpreted statement preserved all those qualifications; reviewed evaluation is needed.

The [earlier example data](diagrams/json/claim-example.json) is a manually authored explanation
with proposed richer fields, not a live output. [Diagram 07](diagrams/html/07-chunked-claims.html)
describes the implemented chunk flow. Entity/predicate/relation graphs, full document-level
reconciliation, tokenizer-aware budgets, and independent semantic coverage checks remain future work.

## Code map

| Responsibility | Source |
| --- | --- |
| Versioned instructions | `config/prompts.yaml`, `core/prompts.py` |
| Source ranges, boundaries, visible windows | `services/text_chunks.py` |
| HTTP contract and bounded adaptive extraction | `providers/meta.py` |
| Claim, source span, coverage and usage contracts | `domain/investigation.py` |
| Final scope and provenance validation | `graph/nodes/validate_report.py` |
| Persistence and legacy readability | `repositories/investigation.py`, migration `0003` |
| Source inspection and partial warnings | `frontend/src/components/ClaimSource.tsx`, `ReportView.tsx` |

## Optional helpers to evaluate

[LangExtract](https://github.com/google/langextract) may help with source anchoring and chunking;
[spaCy](https://spacy.io/usage/linguistic-features) with language-specific sentence/entity
annotations; [DSPy](https://github.com/stanfordnlp/dspy) with prompt optimization after reviewed
labels exist. None is integrated, and none supplies truth verification automatically.
Media still has local browser previews only; photo/video research remains proposed.
