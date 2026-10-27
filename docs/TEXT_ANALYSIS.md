# How text analysis works today

Status checked against the source on October 27, 2026. This document explains implemented behavior and clearly labels proposed extensions. No paid inference was run to create these examples.

## Code map

| Responsibility | Source |
| --- | --- |
| Validate the request and schedule work | `backend/src/clear_context/api/routes/investigations.py` |
| Accept trimmed text, 1-20,000 characters | `backend/src/clear_context/schemas/investigation.py` |
| Run the graph and record completed node events | `backend/src/clear_context/services/investigation.py` |
| Wire the three graph nodes | `backend/src/clear_context/graph/investigation.py` |
| Delegate extraction to the selected provider | `backend/src/clear_context/graph/nodes/extract_claims.py` |
| Build the Meta prompt, call HTTP, and validate output | `backend/src/clear_context/providers/meta.py` |
| Check the report and evidence references | `backend/src/clear_context/domain/investigation.py` and `graph/nodes/validate_report.py` |

## Implemented extraction

1. The browser sends `{ "text": "..." }` only after an explicit Start action. The API stores a queued investigation, returns HTTP 202 with its ID, and schedules a FastAPI background task.
2. LangGraph executes `extract_claims -> evaluate_evidence -> validate_report`. The provider receives the complete text in one call. LangGraph orchestrates; it does not understand grammar or invent claim relationships.
3. The system prompt asks Muse for independently checkable, unique, exact contiguous substrings, preserving the original language, dates, negations, conditions, and attribution. It asks the model to treat the passage as data and not to verify or add sources. These are instructions, not a guarantee of semantic compliance.
4. A strict JSON schema requests `claims: list[str]`. The default maximum is 8 claims, configurable from 1 to 12; the default output budget is 1,024 completion tokens. No chunks or continuation call recover omitted claims.
5. The code requires a completed response without refusal or tool calls, valid schema, count within the configured limit, no duplicate strings, and every nonblank claim occurring literally in the input. Reworded or invented text fails the job. There is no automatic paid retry.
6. Accepted claim strings receive UUIDs. Token usage is recorded. Evidence evaluation currently makes no second model call: sources and evidence are empty and every finding is unresolved. The validated report is saved to SQLite.

If no factual claim exists, the prompt currently asks the model to return the whole input for later clarification. There is no implemented fact/opinion/clarification classifier, and that fallback is not a proof that the input is a factual proposition.

### The key guard

```python
if any(not claim.strip() or claim not in text for claim in extracted.claims):
    raise ProviderError("meta_ungrounded_claim")
```

This proves literal inclusion only. It does not prove that a quote is a complete proposition, preserves every qualification, was attributed correctly, or is true. It also does not record which occurrence was selected when the same wording appears twice. Current claims contain only `id` and `text`; offsets, normalized subjects, predicates, and relation edges are not stored.

## A longer paragraph

Synthetic input:

> The fictional Cedar Museum opened on 12 May 2024. It displays 120 objects. According to its director, entry is free for students aged 18 or over on Tuesdays; it is not free on other days. A post says the attached photograph was taken there yesterday, but the post provides no source for the date.

The companion [example data](diagrams/json/claim-example.json) contains manually selected exact spans and proposed richer records. It is an explanation fixture, not a live model response or a new backend schema.

What needs care:

- `It` refers to the museum; `there` needs an antecedent. Today's code does not resolve these references into explicit entity fields.
- `According to its director` is attribution. The director making a statement is different from independent evidence proving it.
- Free entry on Tuesdays and paid entry on other days are compatible conditions, not an automatic contradiction.
- `Yesterday` cannot become an absolute date without a known posting time and timezone. The server's current date is not a safe replacement.
- The existence of a museum, the date of an image, and whether that image depicts the museum are separate claims. A vision model seeing a building does not establish the image's date or origin.
- Exact-string checking can still accept a misleading partial quote that omitted a condition. Semantic coverage and qualifier retention need separate evaluation.

## Longer-document design: proposed

Keep original text and stable offsets. Split at paragraph/sentence boundaries under a token budget, carry overlap and bounded context, extract local spans, and preserve document-level attribution/entities. Map every quote back to the original document, deduplicate overlap using offsets and meaning, and mark omitted/ambiguous claims rather than silently truncating.

Add normalized propositions alongside quotes, with subject/predicate/object, conditions, attribution, and resolvable time references. Relations must have explicit types and provenance, such as shared subject, condition, or attribution. Support/contradiction require evidence and aligned subject/time/scope; adjacency or shared keywords are insufficient. Keep bounded model calls and total token limits; review claim coverage and qualifier retention on an evaluation set.

This is not implemented. A large model context window does not remove the current claim-count/output cap or guarantee recall. A 20,000-character input can contain many more than eight relevant claims. Raising the cap alone is not a long-document strategy.

## Photo and video cases

Today files are browser-local previews only. Attached media blocks the text-only POST. There is no media upload, OCR, frame extraction, transcription, image-origin lookup, C2PA inspection, or AI-generation detector. Opening or removing a preview never calls Meta.

Proposed photo/caption processing extracts textual assertions separately from visual observations, searches for source context, then reports text and image-context findings independently. Metadata or AI-detection signals are optional separate experiments, not proof of authenticity or truth. Missing credentials do not imply AI generation; a synthetic image can illustrate a true event and a real photograph can have a false caption.

Proposed video processing samples bounded frames and optionally transcribes audio, preserves timestamps, extracts claims linked to those intervals, and compares external evidence. A sampled frame cannot prove the entire clip is authentic. No default AI-detector dependency is selected.

## Useful repositories to evaluate

| Project | Possible contribution | Limits for Clear Context |
| --- | --- | --- |
| [Google LangExtract](https://github.com/google/langextract) | Exact source spans, chunking, multi-pass extraction, visualization | Most relevant candidate. Its OpenAI-compatible provider accepts a base URL/model configuration; Meta compatibility and schema behavior still require an adapter test. Not installed or integrated. |
| [spaCy](https://spacy.io/usage/linguistic-features) | Sentence segmentation, entities, dependency annotations | Useful preprocessing; language/model coverage must be checked, especially for Turkish. Not a turnkey claim verifier or relation reasoner. |
| [DSPy](https://github.com/stanfordnlp/dspy) | Optimize extraction prompts/programs against labeled examples and metrics | Useful after a reviewed evaluation set exists; does not automatically supply correct domain claims or replace the current graph. |

Recommendation: evaluate LangExtract's source anchoring and chunking ideas first, keep LangGraph as the orchestrator, and compare a small prototype with the current extractor before adding dependencies. Avoid importing a framework solely for popularity.
