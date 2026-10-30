# Architecture and evidence contract

The initial text-only API uses FastAPI, LangGraph, SQLite, SQLAlchemy, and Alembic. Mock processing, opt-in Meta claim extraction, token-usage records, persisted status/steps, report storage, and model-selection validation are implemented. Opt-in bounded text research (query planning, Tavily search and page reading, passage selection, and component evidence assessment) is implemented. Image-source lookup, link intake, capture, and revision contracts below are targets, not working capabilities. See [API guide](API.md).

## Backend layout

```text
backend/src/clear_context/
  api/router.py                    # Route registration
  api/routes/investigations.py      # Investigation HTTP endpoints
  api/routes/system.py             # Health and configured models
  schemas/investigation.py         # HTTP request/response contracts
  services/investigation.py        # Job lifecycle and graph execution
  repositories/investigation.py    # Investigation aggregate persistence
  models/                          # ORM records by entity
  db/base.py                       # SQLAlchemy metadata
  db/session.py                    # SQLite engine and sessions
  core/settings.py                 # Environment and model configuration
  domain/investigation.py          # Evidence rules and report contracts
  providers/base.py                # Model-provider boundary
  providers/mock.py                # Offline development behavior
  providers/meta*.py, tavily.py    # Meta model calls and Tavily keyless search/extract
  services/investigation_research.py  # Bounded text research flow used by the evaluate node
  services/query_planning.py, passage_selection.py, evidence_judgment.py  # Research stages
  repositories/judgment.py, retrieval.py  # Persisted assessments, sources and snapshots
  graph/state.py                   # Typed state and per-run dependencies
  graph/investigation.py           # Node/edge construction
  graph/nodes/                     # Focused workflow steps
```

The repository operates on an investigation aggregate; do not create empty repositories for every table. Graph nodes depend on domain/provider contracts, not API routes or database sessions. The service records node progress and saves the validated report in one transaction. Provider instances belong to runtime context, not persisted graph state.

Implemented graph: `START -> extract_claims -> evaluate_evidence -> validate_report -> END`. Mock extraction preserves the full input as one claim. Meta extraction uses a strict JSON schema and accepts only unique, exact substrings of the input; this validates text anchoring, not semantic completeness or truth. Without `RESEARCH_ENABLED`, both modes produce only unresolved findings and evaluation makes no additional call. With it, `evaluate_evidence` delegates to the bounded research service, which records sources, evidence and per-detail component assessments; the claim-wide finding stays `unresolved`. Validation checks evidence integrity, investigation ID, and claim scope. Research is not a separate graph node; its stages report progress through recorded events. Usage from successful extraction nodes is saved before subsequent evaluation, including when a later step fails.

`GRAPH_RECURSION_LIMIT` bounds graph super-steps. It is not a token, time, or monetary budget; those need separate bounds when paid tools are added. Remote LangSmith tracing is disabled during local graph execution. No graph checkpointer is configured yet; SQLite stores application records and progress, not resumable graph snapshots.

## Request flow

```text
Responsive React / TypeScript web client
  -> shared investigation-creation contract
  -> Python / FastAPI investigation service
      -> claim extraction / scope clarification
      -> bounded research loop
          -> web search
          -> page extraction
          -> optional image-source lookup
          -> evidence comparison with Muse
      -> validation and report assembly
  <- progress events and inspectable evidence report

Thin Chrome extension
  -> user-initiated capture and input preview
  -> same investigation-creation contract
  <- investigation ID / brief status / web report URL
```

Use one orchestrator with explicit tools initially. Multiple agents are justified only if an experiment shows they improve research quality or execution time.

## Client boundaries

- The web client owns the full report and evidence inspection UI. It supports desktop and phone screen sizes.
- The Chrome Manifest V3 extension owns capture, preview, starting the job, and opening the web report. It does not run the agent loop or duplicate the report application.
- A capture envelope distinguishes supplied text, original page URL, image/caption, and capture method. Display it before submission so the user can correct missing context.
- Only user-requested content is captured. No continuous monitoring of pages, browser history, cookies, or private account sessions.
- Preview and explicitly submit an image before sending it to external inference or image-lookup services.
- A future Android share receiver or installed PWA uses the same contract. It is not required for the initial release.

## Initial technical boundaries

- Use a single modular backend: thin API routes, workflow services, local persistence repositories, and external-service adapters. Domain rules must not depend on FastAPI, provider SDKs, or database implementations. Add interfaces only at useful boundaries, not for every class.
- Keep model keys in the user's backend environment and history in local persistence. No membership or subscription system is required. Plan simple local packaging after the working flow; limit live research separately in a hosted demo.
- Persist explicit investigation states and research steps without introducing event sourcing, a message broker, or microservices. These are not prerequisites for the state machine.
- FastAPI handles request validation and investigation APIs; use explicit Python data models for all tool and evidence records.
- React/TypeScript with Vite provides the web UI. Choose a small shared package for extension/web input types only when implementation needs it.
- Research work runs outside an individual HTTP request's lifetime. Start with one service and persistent investigation state, not a distributed queue architecture.
- Progress transport (polling or server-sent events) follows the first working flow's needs; expose tool outcomes and errors rather than internal chain-of-thought.
- Use LangGraph for workflow execution and explicit investigation states for API lifecycle. Add conditional research loops, checkpoints, or parallel branches only with implemented tools and focused tests.
- No native mobile shell, Capacitor integration, or incoming-share dependency in the MVP.

## Records

| Record | Essential fields |
| --- | --- |
| Investigation | ID, original input, supplied context, timestamps, status, limits, revision |
| Claim | ID, exact wording, normalized proposition, subject, date/place/conditions, modality |
| Source | ID, original/canonical URL, title, publisher, published/updated time if known, retrieved time, access status |
| Evidence | ID, claim ID, source ID, exact excerpt, locator, supports/contradicts/contextualizes, source type |
| Finding | Claim ID, assessment, explanation, evidence IDs, missing information, limitations |
| Research step | Tool, purpose, sanitized arguments, outcome/error, elapsed time, revision |

Never fill unknown publication dates with retrieval dates. Keep model inference separate from quoted source content.

## Assessment values

- **supported:** retrieved evidence directly supports the bounded proposition.
- **contradicted:** retrieved evidence directly conflicts with it.
- **mixed:** different parts or conditions have different evidentiary outcomes.
- **unresolved:** insufficient, inaccessible, ambiguous, or conflicting evidence prevents a defensible finding.

These are evidence assessments, not guarantees of truth. Image-context assessment is a separate finding from the associated event claim. A source containing an image is not automatically its original publisher. An earliest-found result is not proof of first publication.

## Tool contracts

Tools return structured results and explicit errors. The application executes tool calls; the model must not imply that it searched or fetched something without a successful recorded call.

- `search_web`: query, optional filters -> result URLs and snippets.
- `fetch_source`: public URL -> extracted content, metadata, access result.
- `lookup_image_sources` (conditional): image -> candidate source URLs, provider metadata.
- `compare_evidence`: selected claims and fetched evidence -> proposed findings with evidence IDs.

Validate model output structure. Reject invented evidence IDs. Check quoted text against the fetched document; describe OCR-derived text as such. Expose disagreements and evidence gaps rather than forcing a verdict.

## Limits and safety

- Configurable limits for model calls, search queries, fetched pages, wall time, and output length; record termination reasons.
- Retrieved content is untrusted data. Embedded instructions cannot change the task, grant tool permissions, or request credentials.
- URL fetching must block local/private addresses, cloud metadata endpoints, and unsafe redirects, with content-size and timeout limits.
- Keys stay on the backend. Do not expose them in browser code, logs, commits, screenshots, or demo videos.
- Redact secrets from traces. Do not log authentication headers or signed asset URLs.
- Source duplication and syndication must not inflate apparent corroboration.

## Updates and persistence

Keep sources and research steps attached to an investigation revision. When a user changes the claim or adds evidence, mark dependent findings stale and recompute them. Do not silently reuse a conclusion from the previous scope.

Start with local persistence suitable for a single developer. Cross-investigation semantic memory, accounts, and a global source graph are later decisions, not MVP prerequisites.
