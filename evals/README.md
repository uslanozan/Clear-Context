# Evaluation plan

## Query planning overview

`query_catalog.py` selects the evaluation method from `config/query_planners.yaml`;
`selected: v5` is the current candidate. `query_planning.py` builds and validates
structured research plans from saved claims. Prompt text and synthetic examples
remain in `config/prompts.yaml`.

Plans retain original claim IDs, separate information needs, and map each query to
its needs. Validation rejects unknown IDs, silent omissions, duplicate queries,
conflicting deferrals and exceeded budgets. Structural validity does not establish
semantic coverage, source relevance or factual truth. This prototype does not
execute searches or change the live application graph.

Local trials and Turkish review pages live under ignored `docs/local/experiments/`.
Run offline checks with
`python -m pytest evals/test_query_catalog.py evals/test_query_planning.py -q`.

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

## Extraction debugging

`extraction_debug.py` provides offline response inspection and a one-call HTTP capture
transport for explicitly authorized diagnostics. It records the actual request JSON,
raw response body, and ordered processing stages. Authorization headers are excluded.
Keep traces in the Git-ignored `docs/local/` directory and use permitted source data.

Schema validity, empty extraction, exact quotation matching, and semantic review are
separate outcomes. Invisible-character and apostrophe comparisons are diagnostic
candidates only; they never silently repair a quotation or make it pass exact matching.
Duplicate JSON keys, unexpected fields, and wrong types are rejected.

Run the offline checks from the repository root:

```powershell
.venv/Scripts/python.exe -m unittest discover -s evals -p test_extraction_debug.py -v
```

Tests use synthetic responses and make no network calls. Live diagnosis must have a
fixed call budget, immutable prompt/source conditions, and no automatic paid retries.

For new method-B experiments, `langextract_instructions.create_system_instruction_model`
moves the exact extraction-rule prefix into the provider's system message. Processing
context, demonstrations, and source text remain in the user message. Other request
parameters are unchanged. The adapter fails before inference if the expected prefix
is absent; it does not modify the installed LangExtract package. Historical comparisons
must explicitly retain their original user-role layout and keep result directories separate.

## Query profiles and validation

`query_planning.py` builds strict structured-output requests without executing search.
Named `experiments.query_planning_v1`, `query_planning_v2` and `query_planning_v3`
entries in `config/prompts.yaml` keep historical prompt contracts replayable.
Pass `prompt_version="query_planning_v3"` to both `build_request` and `validate_plan`
to select the component contract. The default remains the historical v1 contract;
this prototype is not integrated into the application graph.

V3 keeps original claims unchanged and records separate information needs with
`planned`, `needs_context` or `budget_deferred` status. Questions reference need IDs,
so one claim can retain searchable parts while another part waits for context.
Validators reject missing/unknown claims, duplicate needs and queries, deferred
needs attached to questions, unreferenced planned needs and query-budget overflow.
These checks establish structural coverage, not semantic completeness or factual truth.

Run offline checks with `.venv/Scripts/python.exe -m pytest evals/test_query_planning.py -q`.
Recorded outputs and Turkish review reports remain in ignored `docs/local/experiments/`.

### Query method catalog

`config/query_planners.yaml` selects an evaluation method with `selected`; pass a
`method` argument to `build_planner_request` in `query_catalog.py` for an explicit
per-run override. Profiles select an allowlisted implementation, a central prompt
and a typed response schema. No arbitrary module import or executable YAML is used.
The application research graph is not wired to this catalog yet.

`v4` adds per-query `need_ids`, validates that each question's needs are
covered by its own queries, and uses focused-predicate, causal-coverage and temporal
count rules. These structural checks do not prove semantic adequacy or retrieval
quality. Historical component/claim plans keep their original contracts.

Future spaCy or other deterministic planners require a real implementation, a new
allowlisted contract if needed, offline tests and a catalog entry. Unimplemented
methods fail before inference. Prompt changes remain in `config/prompts.yaml`.

Private comparison adapters, copied templates, licenses and recorded outputs belong
only under ignored `docs/local/benchmarks/` and `docs/local/experiments/`. They are
not distributed profiles, application dependencies or public planner implementations.


`v5` retains the mapped-component schema and adds claim-bound research goals and
explicit restrictive-scope queries. A helper inventory, address or location must not
become a new information need unless asserted in the claim. Restrictive qualifiers
need a focused query even in batch planning. These are prompt-level rules, not a
semantic validator or a guarantee of complete, faithful output. Historical `v4`
requests remain replayable by explicit method selection. The selected evaluation
candidate is `v5`; no application graph integration or search execution is implied.


## Search retrieval evaluation

`search_retrieval.py` provides typed Tavily Basic request/response contracts and
claim/need bindings for saved query plans. It does not execute HTTP requests or
integrate search into the application graph. An explicit live runner must send
`X-Tavily-Access-Mode: keyless`, enforce a fixed call budget and avoid automatic
retries or paid fallback. No credentials are loaded by these helpers.

Exact request hashes include endpoint, access mode, language and all request
parameters. Identical queries share a request while retaining distinct case/need
bindings. URL identities strip tracking parameters and fragments while preserving
meaningful parameters; they identify repeated results, not independent sources.
No page fetching or persistent application cache is implemented here.

Record raw requests/responses and retrieval times in ignored local experiment
folders. Provider publication dates remain optional, unverified strings. Search
scores express provider relevance, never factual confidence; an empty or irrelevant
result is not a false-claim verdict. Human snippet review does not verify full pages.

Run offline checks with
`.venv/Scripts/python.exe -m pytest evals/test_search_retrieval.py -q`.

## Retrieval workspace (evaluation runner)

Reusable retrieval contracts, a keyless transport and a bounded service are now
available under `schemas/retrieval.py`, `providers/tavily.py` and
`services/retrieval.py`. They are not wired into the investigation API or graph.
`repositories/retrieval.py` uses SQLAlchemy and a separate, rebuildable SQLite
workspace with `research_*` tables. Do not point it at the application database.
There is no application database migration for this isolated evaluation store.

A plan has immutable, case-scoped claim/need/query IDs. Composite foreign keys
preserve query-to-need and need-to-claim edges. A canonical URL has one shared
source ID; every query keeps its own source hit, rank, snippet and provider date.
Successful search and page responses use separate TTL caches. An extracted page
snapshot retains its own ID and timestamp; existing passages keep their old page
when a later read refreshes the cache. Quote text must exactly match its recorded
character offsets. Passage/need links are candidates, not support or truth labels.

`config/retrieval.yaml` configures per-session call limits and cache lifetimes.
Unavailable pages are negatively cached for five minutes by default. Rate limits,
invalid responses and transport failures halt new live calls in that session;
there are no automatic retries, key discovery, paid fallback or local URL fetching.
Follow-up registration requires existing planned needs, an explicit gap and reason,
and a separate count limit. Query rewriting, semantic relevance detection and
judging are not automatically performed by this service.

Replay a private recorded pilot without live search or extraction:

```powershell
.venv/Scripts/python.exe evals/retrieval_workspace.py `
  --recordings docs/local/experiments/tavily-keyless-pilot `
  --selection docs/local/experiments/retrieval-workspace/selection.json `
  --workspace .local/retrieval/offline.sqlite `
  --output docs/local/experiments/retrieval-workspace-offline
```

These local inputs are not distributed fixtures. The recordings folder must contain
`cases.json`, `plans.json`, `queries.json` and `results.json` from the saved-plan
search pilot. Selection rows contain `label`, `case_id`, `query_id`, `need_ids`,
`url` and optional literal `anchors`. A selected URL must have been discovered in
the case. The runner always disables new search calls. Without
`--allow-live-extract`, only unexpired page-cache reads are permitted. This flag
explicitly allows bounded keyless Extract calls; never use it for offline replay.
Choose a new output directory to preserve historical reports.

Term windows are a deterministic inspection aid. A matching word may be in a menu,
title or unrelated passage. This does not establish relevance, semantic coverage
or factual support. Record empty/failed extraction separately from false claims.
The full successful provider JSON is kept in the workspace cache; failure events
record error codes, not complete raw failure bodies.
