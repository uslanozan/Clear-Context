# Initial API

Local development only, single process. Mock mode is the default. Meta mode supports claim extraction and optional bounded text research with `RESEARCH_ENABLED=true`. Images can be uploaded and, in Meta mode, are read by a Muse model; video is stored but not analyzed yet. A real key alone does not activate inference.

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Mode and paid-call status; no credentials |
| GET | `/api/models` | Validated task selections; not live provider availability |
| POST | `/api/investigations` | Accept `{ "text": "A claim to investigate", "research_mode": "balanced" }`; return 202 and Location |
| GET | `/api/investigations?limit=20&offset=0` | Recent history, newest first |
| GET | `/api/investigations/{id}` | Persisted status and input |
| GET | `/api/investigations/{id}/steps` | Recorded processing steps |
| GET | `/api/investigations/{id}/report` | Completed report; 409 until available |
| POST | `/api/investigations/upload` | Multipart: `files` (1-4), optional `text` caption and `research_mode`; return 202 and Location |
| GET | `/api/media/{id}` | An uploaded file with its detected content type |

Text must contain 1-20,000 characters after trimming. `research_mode` is optional: `fast`, `balanced` (default) or `deep`. It changes only research budgets (see the README) and is ignored when source research is disabled. Unknown fields are rejected. Missing investigations return 404; malformed UUIDs and invalid input return 422. Links in `text` (up to three HTTP(S) addresses) are read in Meta mode through Tavily Extract; preview mode reports them as not opened. The first 3,000 characters of each page are appended as `[Text read from link N]` and checked like pasted text; the page's main image is downloaded (public HTTPS hosts only, redirects re-checked, 20 MB, signature-checked) and analyzed like an upload, with `source_url` set. `links` in the report gives each link's status, title, site, `published_on` (only when a Tavily news search returns that exact page; never guessed from the page text) and why a link or image could not be read. Research does not read the checked pages as evidence, and the reported date is passed to the planner as `source_published_at`. There is no cancellation, report revision, or authentication yet.

Uploads accept JPEG, PNG, GIF, WebP and MP4, detected from file signatures rather than names or declared types; images up to 20 MB, videos up to 100 MB, at most four files and 100 MB in total. Files are stored under `MEDIA_DIR` by SHA-256. A request needs text or at least one image. In Meta mode each image is sent to the `MODEL_SCREENSHOT` model, which returns visible text (a model transcription that can contain errors), observations and place/time cues; it does not judge truth, authenticity or first publication. The model also marks which parts of that text are statements (`claim_text`: post text, captions, headlines); only those are appended to the analyzed text with a `[Text read from image N]` label, so signs, product labels and date stamps are not extracted as claims. `caption_checks` compare what the caption says about the picture (place, time, event) with visible details as `consistent`, `inconsistent` or `cannot_tell`; they are a labeled model visual assessment, never evidence. Preview mode sends nothing to a model. Reverse image search runs only in Meta mode with `REVERSE_IMAGE_PROVIDER=serpapi_lens` and `SERP_API_KEY` (Google Lens exact matches, plus visual matches when fewer than three exact matches exist). Images over SerpApi's 500 KB upload limit are re-encoded for the upload; the stored file is unchanged. Each match has the page, site and, when Lens shows one, a display date; same-image matches are ordered earliest date first. With `serpapi_lens`, Bing reverse image search (through the same SerpApi key) is also queried with a Google-hosted copy of the image that Lens found, adding direct page links with the date Bing shows; matches record `found_by`. Lens often returns Google redirect links; they are resolved only when Google answers with a plain redirect. When Google shows a request-verification page instead, the link stays a Google link, is shown to the user and is not read. Matching pages are leads, not proof of an image's origin or date. During research, up to `image_match_reads` readable matching pages (1/2/3 by mode; social feeds and redirects are skipped) are read as sources for every planned need, with the Lens date recorded as the page date, and the planner receives image observations and matching page titles as context. Otherwise the report states that the image origin was not checked. When a Google API key is set (`GOOGLE_FACT_CHECK_API_KEY`) and `FACT_CHECK_IMAGE_SEARCH` is on, the Google Fact Check Tools `claims:imageSearch` endpoint is queried with Google-hosted copies of the same image found by reverse image search; the uploaded file is not published. The Fact Check text search (`claims:search`) is also queried with the caption, or with statements read from the image when there is no caption; such reviews are marked `matched_by: text` and may concern another picture. `prior_checks` lists published fact checks with publisher, review date and the publisher's own textual rating. Those ratings are not adopted as a verdict: the fact-check pages are read first as research sources, with the review date as page date, and the evidence assessment still decides each component.

## Try it

With the server running, in another PowerShell session:

```powershell
$investigation = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/investigations -ContentType application/json -Body '{"text":"A claim to investigate."}'
Invoke-RestMethod "http://127.0.0.1:8000/api/investigations/$($investigation.id)"
Invoke-RestMethod "http://127.0.0.1:8000/api/investigations/$($investigation.id)/report"
```

Poll status until `completed` or `failed` before reading the report. Mock mode preserves the entire input as one claim, creates no sources/evidence, and returns an unresolved finding with explicit limitations. It does not simulate a successful search or establish truth.

## Runtime settings

Start with `python -m clear_context` to apply `.env` host, port, and logging settings. Explicit OS environment variables take precedence over `.env`, then application defaults. Restart after changing settings.

| Variable | Default | Purpose |
| --- | --- | --- |
| `API_HOST` | `127.0.0.1` | Bind address; `0.0.0.0` exposes the listener to reachable networks |
| `API_PORT` | `8000` | API port, 1-65535 |
| `LOG_LEVEL` | `info` | Server log level |
| `API_DOCS_ENABLED` | `true` | Enable `/docs`, `/redoc`, and `/openapi.json` |
| `GRAPH_RECURSION_LIMIT` | `12` | Maximum LangGraph super-steps, configured range 4-100 |
| `CORS_ALLOWED_ORIGINS` | `[]` | JSON array of explicit allowed HTTP(S) browser origins |
| `DATABASE_PATH` | `.local/clear-context.db` | SQLite file; shared by server and migrations |
| `MODEL_CATALOG_PATH` | `config/models.yaml` | Model catalog |
| `APP_MODE` | `mock` | `mock` or `meta` |
| `ALLOW_PAID_API_CALLS` | `false` | Explicit opt-in required with Meta mode and a non-empty key |
| `META_TIMEOUT_SECONDS` | `60` | HTTP timeout; configurable up to 120 seconds |
| `META_MAX_COMPLETION_TOKENS` | `4096` | Visible plus reasoning output tokens per request, range 128-4096 |
| `META_MAX_CLAIMS` | `8` | V1 legacy single-call limit only |
| `PROMPT_CLAIM_EXTRACTION` | `v2` | Bounded extraction contract; v1 remains available |
| `EXTRACTION_RESPONSE_CAPACITY` | `24` | Capacity per response, not a document-wide limit |
| `EXTRACTION_CHUNK_CHARACTERS` | `600` | Initial target bound in Unicode characters |
| `EXTRACTION_MIN_CHUNK_CHARACTERS` | `200` | Splitting stops at at most twice this size |
| `EXTRACTION_CONTEXT_CHARACTERS` | `600` | Bound per head/adjacent context window |
| `EXTRACTION_MAX_CALLS` | `24` | Maximum model calls per document |
| `EXTRACTION_MAX_OUTPUT_TOKENS` | `32768` | Total output budget; unknown usage stays reserved |
| `EXTRACTION_MAX_SECONDS` | `120` | Time budget constraining subsequent requests |

The example environment allows the implemented Vite frontend on localhost/127.0.0.1 port 5173. Adjust CORS origins when its address changes. CORS does not protect a network-exposed API from non-browser clients. Direct Uvicorn CLI commands use their own host/port flags; they do not read these custom settings automatically. One worker remains required.

## Meta adapter

Set `APP_MODE=meta`, `ALLOW_PAID_API_CALLS=true`, and a local `META_API_KEY` only after confirming credit or spending authorization. Restart the server. Mock remains the default and makes no external calls, even when a key is present.

The adapter calls `https://api.meta.ai/v1/chat/completions` using Bearer authentication, a strict JSON schema, `reasoning_effort=low`, `store=false`, bounded completion tokens, and no tools. It does not follow redirects, inherit proxy settings, retry automatically, switch models, or repair invalid outputs with another paid call. V2 explicitly splits capacity/truncation cases into smaller targets, within a bounded budget. HTTP timeouts are not a guaranteed total job deadline.

V2 extraction returns literal source/context spans plus separately interpreted statements and extraction coverage. V1 retains unique string spans for legacy baselines. UUIDs are assigned locally. This anchoring cannot establish semantic completeness or truth. Without external evidence, evaluation deterministically creates unresolved findings and makes no second model call. `MODEL_JUDGE` and `MODEL_REPORT` are validated selections but not called yet.

Meta records and reports have `mode=meta`. `model_usage` stores the configured task/model, prompt version, rendered-system-prompt SHA-256, and API-reported input/output/cache token counts; missing metrics remain null. Historical records without prompt metadata remain readable. See [Prompt management](PROMPTS.md). Successful node usage survives later graph failures. Failed or rejected responses may still consume credit and may have no saved receipt; consult Meta Billing for authoritative totals. Local settings and per-call limits are not an account-wide monetary cap.

V1 provider errors fail the investigation. V2 invalid or deferred ranges produce explicit partial coverage; service errors stop further model calls and retain available results and receipts. No provider response bodies, keys, or raw exception text are returned. No automatic retry means a failed investigation requires a deliberate new submission.

The account's promotional-credit notice says content may be used for product improvement while free credits are used. `store=false` is a request option, not a guarantee overriding promotion/account terms. Keep initial experiments limited to public or self-created non-sensitive text.

Reference: [Meta structured output](https://dev.meta.ai/docs/structured-output), [Chat Completions schema](https://dev.meta.ai/docs/api-reference/chat-completions/schemas).

## Persistence and lifecycle

SQLite stores investigations, claims, sources, evidence, findings, finding/evidence links, and research steps in relational tables with foreign keys enabled. Reports are validated before an atomic completion transaction: unknown references, unrelated evidence, nonmatching excerpts, and resolved findings without evidence are rejected.

`DATABASE_PATH` defaults to `.local/clear-context.db`. Relative database/catalog paths resolve from the repository root. `.env` is loaded from that root, and real keys are excluded from settings serialization and public responses. Existing `.env` files may omit new settings and inherit defaults.

Apply migrations before starting: `python -m alembic -c backend/alembic.ini upgrade head`. Do not replace migrations with runtime `create_all`. Normal upgrades retain data; downgrading the initial migration drops its tables and data.

State transitions: `queued -> running -> completed/failed`. Work runs in an in-process background task after the response, using LangGraph nodes `extract_claims -> evaluate_evidence -> validate_report`. Opt-in research records completed planning, retrieval, selection and assessment steps as they occur, plus `followup_research` when a follow-up search round ran. On restart, unfinished jobs are marked `failed` with `interrupted`, not silently resumed. No graph checkpointer is configured yet. Provider failures expose a generic `processing_failed` code without raw error messages. Run **one worker / one server instance per database**; this is not a durable queue and has no retry/resume guarantee.

Bind to loopback for this slice. Network-accessible self-hosting, HTTPS, and access protection will be addressed before public deployment. Docker Compose stores SQLite in a named volume and publishes only the web container on loopback; server-side uploads do not exist yet and will need the same volume.

## Checks

Run pytest, Ruff lint, and Ruff format checks using the README commands. Tests use temporary migrated databases, exercise restart persistence, migration round trips, failure handling, evidence validation, input boundaries, and model selection. They block external connections, allowing loopback for Windows event-loop internals. Synthetic evidence fixtures are not real research results.


## V2 report fields

Claims may include `statement`, `source_span`, `context_spans`, and `context_status`.
Original quote text remains in `text`; the interpreted statement is not literal evidence.
`extraction_coverage` records `processed` or `partial`, model-call count, chunk ranges,
outcomes and notes. `processed` is not a semantic completeness guarantee. Partial reports
can have investigation status `completed`: processing ended, but extraction coverage is
explicitly partial. These reports must not be presented as fully extracted documents.

Database revision `0003` adds provenance and coverage while retaining legacy rows. Run
Alembic upgrade head before restarting. SQLite offsets are Python Unicode code points;
JavaScript clients must not use them directly as UTF-16 string indexes.
