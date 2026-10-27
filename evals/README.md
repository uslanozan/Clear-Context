# Evaluation plan

The specifications in `case-specs.json` describe broader product cases to collect; they are **not** a finished dataset or measured results.

An initial [web text development corpus](corpus/v1/README.md) now contains 36 original and
controlled inputs from 14 source pages in four languages. It separates input text from
provenance, edits, and draft true/false/unknown target labels. Four natural interior windows
remain unannotated. The first local Muse Spark 1.3 extraction baseline attempted 36 inputs:
14 passed current output validation and 22 hit the 1,024-token completion limit. The
accepted outputs contain 50 exact source spans. These are mechanical outcomes, not an
accuracy score; no truth judging or semantic completeness measurement was performed.
Review the draft labels before scoring; this does not finish the media/failure case specifications.

A follow-up selected only those 22 truncated cases, kept the same model/prompt and
eight-claim limit, and raised the completion budget to 4,096. All 22 passed current
validation, producing 148 spans. Combined with the 14 earlier outputs, the local view
contains 36 inputs and 198 spans. This mixes two budgets and is not a new whole-corpus
pass or an accuracy measurement. Fifteen follow-up outputs reached eight claims; the
altered Curie award year was absent from its output, so completeness remains an open issue.

## Extraction runs

`run_extraction.py` uses the configured Meta provider and prompt. It reads only
`corpus/v1/inputs.jsonl`, never reference labels or mutation records. By default it prints
configuration without making requests:

```powershell
.\.venv\Scripts\python.exe evals/run_extraction.py
# Billable: requires APP_MODE=meta, ALLOW_PAID_API_CALLS=true, and a local API key.
.\.venv\Scripts\python.exe evals/run_extraction.py --execute --limit 36
```

Each execution creates a new ignored `evals/runs/<run-id>/` directory with configuration,
per-case outputs, latency, reported usage, validation errors, and a summary. Raw diagnostic
completion content is retained separately from accepted claims; rejected or truncated
responses must not be treated as accepted extractions. Reasoning content, credentials,
headers, and non-success HTTP bodies are not saved. The run records both the configured
model and the response model ID when available.

At most 36 inputs are selected. V1 uses one call per input; v2 can use multiple bounded
calls per input. Metadata records the maximum call budget; summaries distinguish attempted
requests from received responses. There are no automatic HTTP retries. A service or transport
error stops further requests. Re-running starts another billable pass, not a free resume.
The runner performs extraction only and does not populate application history or measure
truth, semantic completeness, or model accuracy. Existing claim/token limits remain in
effect so their failures remain visible in a baseline run. An explicit experiment can
override only the completion budget without editing `.env`:

```powershell
# First omit --execute to inspect the selected inputs and configuration.
.\.venv\Scripts\python.exe evals/run_extraction.py --prompt-version v1 --retry-truncated-from evals/runs/<run-id> --max-completion-tokens 4096
```

This selection includes only previous `meta_incomplete_output` cases. It verifies that the
input file/text, model, prompt, claim limit, reasoning setting, and timeout match the parent
run. Adding `--execute` makes a new bounded, billable pass. Compare this selected subset
against the same previous cases, not against the original whole-corpus success rate.

Use repeatable `--case-id <opaque-id>` arguments and `--model <catalog-alias>` for a
small explicit model experiment without changing `.env`. These options do not supply
labels to the model. A two-input Curie spot check with Wonder at the same v1 prompt,
eight-claim limit, and 4,096-token budget included the selected Chemistry award year in
both passages; the earlier Spark output included the original year but omitted the
altered year. This is
one generation per selected case and model, not a general model ranking. Both Wonder
outputs still reached the eight-claim cap and did not establish exhaustive coverage.

V2 now removes the document-wide cap and records quote provenance, separate interpreted
statements, adaptive splits, and partial outcomes. See [chunking results](CHUNKING_RESULTS.md)
for the selected Spark/Wonder check. `--prompt-version v2` selects this contract explicitly;
`--max-extraction-calls`, `--max-total-output-tokens`, and `--max-extraction-seconds` can
bound an experiment without editing local application settings. A v2 result can be partial
while retaining valid claims; do not count it as a fully processed document.

Before scoring any case, attach source URLs, access dates, a human-written bounded claim, expected evidence, and permission/license notes for assets. Use openly licensed or self-created image assets. No fabricated source URLs, citations, or benchmark numbers.

## Initial set

Collect 10 cases covering straightforward support, contradiction, omitted context, image reuse, uncertainty, duplicate reporting, inaccessible sources, misleading excerpts, hostile source instructions, and corrected input.

Use controlled local fixtures for deterministic failure/security scenarios, label them synthetic, and keep real-web examples for the demonstration. A controlled fixture is not evidence of broad real-world accuracy.

## Review dimensions

1. Does claim decomposition preserve the original qualifications?
2. Does each quotation appear in the retrieved source at the stated location?
3. Does the cited evidence support the exact finding?
4. Are image context and event claims assessed independently?
5. Does the system retain uncertainty when the evidence is insufficient?
6. Does it recognize copied sources and access failures?
7. Does a correction trigger an appropriate update?
8. What are the observed latency, tool calls, and model costs?

Record per-case outputs and review notes. Report numerator/denominator counts and failures. Ten cases are a development check, not a validated general accuracy claim. Budget and latency targets will be set after measuring the first working examples.
