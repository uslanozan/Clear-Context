# Clear Context

Investigate a claim. Inspect the evidence. Recover the context.

Clear Context is a multimodal research agent being built for the Meta Global AI Developer Hackathon (October 26–November 4, 2026), in the solo Indie Developer track.

**Status: local API and LangGraph workflow implemented, with mock mode by default. Optional Meta text research connects query planning, Tavily keyless search, source reading, passage selection and evidence assessment to saved web reports. Server-side media analysis and the Chrome extension are not implemented yet. Local image/video attachment previews are available.**

A separate evaluation workspace now replays saved query plans, shares source URLs,
reads selected pages through Tavily keyless, and preserves claim/need/passage links
with bounded calls and TTL caches. Full-page Muse paragraph selection now supports
ten concurrent requests by default and persists source-bound selection receipts. The opt-in
application flow uses bounded search, selection and component assessment. It does not
produce global claim verification or source-trust scores. See [retrieval evaluation](evals/README.md#retrieval-workspace-evaluation-runner)
and [evidence judgment](docs/EVIDENCE_JUDGMENT.md).

V2 extraction now partitions long text under bounded character budgets, carries source
context, and saves exact quote positions separately from interpreted statements. There is
no document-wide eight-claim cap. Budget or validation gaps appear as partial extraction;
processed ranges do not guarantee exhaustive claim coverage. Database migration `0005`
is required. See [text analysis](docs/TEXT_ANALYSIS.md) and [prompt settings](docs/PROMPTS.md).

## The problem

An event can be real while its accompanying photograph comes from another place or year. A statement can accurately quote a source while leaving out the condition that changes its meaning. Readers need to see the evidence for each part of a claim and where the investigation remains unresolved.

## Planned experience

1. Submit a statement, article URL, or image through the web app, or capture selected content with the Chrome extension.
2. Preview what was captured and confirm the intended claim before starting research.
3. Review the specific claims the agent extracts, including dates, places, and qualifications.
4. Watch the investigation gather sources, identify missing evidence, and refine searches.
5. Inspect a web report connecting findings to source excerpts and links.
6. Add a correction or new source and see which findings change.

Textual claims and image context are evaluated separately. Finding no supporting source is not sufficient to label a claim false. The agent must show uncertainty and failed research steps.

## Hackathon MVP

- Text or URL submission; optional single image.
- A responsive web application that is the complete investigation and evidence workspace.
- A thin Chrome extension for user-initiated capture, preview, short status, and opening the web report.
- Bounded, tool-driven web research and source comparison.
- Claim-level evidence excerpts, source dates, and retrieval timestamps.
- Visual-context checks when external evidence can be retrieved.
- A report that distinguishes supported, contradicted, mixed, and unresolved findings.
- A small manually reviewed evaluation set and a three-minute demonstration.

Native mobile apps, PWA installation and incoming share integration, video investigation, universal image provenance, deepfake detection, and a general-purpose knowledge base are outside the initial scope. The web interface should still work on phone screens. Visual inspection alone cannot establish an image's date, location, or authenticity.

## Distribution and access

The planned release is a self-hosted application with a browser interface and an optional Chrome capture extension. Users supply their own Meta Model API key on the backend; a Muse Code subscription is not required. Research history stays in local storage, while selected inputs and evidence are sent to external services for inference and retrieval. This is not offline inference.

Accounts, subscriptions, and billing management are outside the MVP. A controlled hosted hackathon demo is separate from the local product. Docker Compose packaging runs the API and web interface on one local port; see [Run with Docker](#run-with-docker).

## Technology direction

- **Backend:** Python + FastAPI, with validated data contracts and a bounded LangGraph workflow. Investigation status, node progress, and reports persist in SQLite; graph checkpoints/resume are not implemented yet.
- **Frontend:** React + TypeScript + Vite, Mantine for shared components/theme, and TanStack Query for API state.
- **Extension:** a thin Chrome Manifest V3 client using the same backend; the full report stays on the web.
- **Primary models:** Muse through Meta Model API; exact model selection follows small quality/cost experiments.
- **Optional experiments:** Meta open-weight inference on Baseten, Fireworks, or Modal, subject to access and evaluation.
- **Storage:** SQLite with SQLAlchemy and Alembic migrations; no separate database server.

Text research uses Tavily Search and Extract. Set `TAVILY_API_KEY` to use your own Tavily account (the free plan includes monthly credits); without it, research falls back to keyless access, which is rate-limited without a published quota and stopped repeated or `deep` runs in testing. No paid fallback runs automatically. A reverse-image lookup provider has not been selected or verified. Users must confirm their own billing/credit availability before enabling paid inference.

## Delivery order

1. Prove a real claim-to-evidence workflow through the backend.
2. Build the complete web submission and report experience.
3. Add the thin Chrome capture extension and test the combined flow.
4. If the core is complete and time remains, test PWA installation and Android incoming sharing. iOS native integration is not part of this hackathon scope.

## Project documents

- [Build plan](docs/PLAN.md)
- [Text analysis explained](docs/TEXT_ANALYSIS.md)
- [Workflow diagrams](docs/diagrams/md/README.md)
- [Model plan](docs/MODELS.md)
- [Prompt management](docs/PROMPTS.md)
- [Architecture and evidence contract](docs/ARCHITECTURE.md)
- [Frontend guide and design system](docs/FRONTEND.md)
- [Research resources: claim extraction and verification](docs/RESEARCH_RESOURCES.md)
- [Evaluation plan](evals/README.md)
- [Initial case specifications](evals/case-specs.json)

## Run with Docker

Requires Docker with Compose v2.24 or newer. From the repository root:

```powershell
# Copy only when creating your local settings; preserve an existing .env.
# Copy-Item .env.example .env
docker compose up -d --build
```

Open `http://127.0.0.1:8080`. The `web` container serves the built interface and proxies `/api` to the `api` container, which applies database migrations before starting. Settings come from `.env`; the container overrides only the bind address, the database path and CORS. Mock mode stays the default, and the paid-call settings described below apply unchanged.

Both SQLite databases (investigations and research cache) live in the `clear-context-data` volume and survive `docker compose down` and image rebuilds. `docker compose down -v` deletes them. The volume starts empty. To bring over reports from a non-Docker setup, stop the local API, then run:

```powershell
docker compose stop api
docker compose run --rm --no-deps -v "${PWD}/.local:/import:ro" api python -m clear_context.db.import_local /import/clear-context.db
docker compose start api
```

The command copies `clear-context.db` and the `research.sqlite` cache beside it with SQLite's backup API, refuses to overwrite a volume that already holds data unless you add `--replace`, and refuses a source with an unfinished journal. Pending migrations run when the API starts. In Git Bash, prefix the `run` command with `MSYS_NO_PATHCONV=1` so `/import` is not rewritten.

The published port binds to loopback because the application has no authentication. Set `CLEAR_CONTEXT_PORT` to change the port. Changing `CLEAR_CONTEXT_BIND` exposes the app to your network without access control or HTTPS; do not do that on an untrusted network. Interactive API documentation is available at `http://127.0.0.1:8080/docs` (and `/redoc`) unless `API_DOCS_ENABLED=false`.

## Development

Python 3.12 or newer is required. From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e backend
# Copy only when creating your local settings; preserve an existing .env.
# Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m clear_context
```

On Linux/macOS, use `.venv/bin/python` instead of `.venv\Scripts\python.exe`. The dependency snapshot was tested on Windows/Python 3.12. See [API guide](docs/API.md) for endpoints and limitations. Open the interactive API documentation at `http://127.0.0.1:8000/docs`.

Mock mode is the default. A configured API key does not enable calls by itself. To enable Meta claim extraction, set both `APP_MODE=meta` and `ALLOW_PAID_API_CALLS=true`, then restart. To also enable source research, set `RESEARCH_ENABLED=true`: the flow sends generated queries and source URLs to Tavily and selected text to Meta. Each investigation picks a research depth that changes only call budgets, never the methods. `balanced` (default) uses up to six searches, three page reads, one planning call, three selection calls and six judgment calls, in addition to extraction; research needs left with insufficient evidence then get one follow-up round of one more planning call, up to two searches, two page reads, three selection calls and two judgment calls. `fast` uses three searches, two page reads, two selection calls and four judgment calls with no follow-up. `deep` uses ten searches, five page reads, five selection calls and ten judgment calls, plus a follow-up of up to four searches, three page reads, four selection calls and four judgment calls; it costs more and is more likely to reach Tavily keyless rate limits. Needs beyond the judgment budget are reported as not assessed. Claim-wide coverage and source reliability remain unresolved. Run `alembic upgrade head` for migration `0005`. See the [API guide](docs/API.md) for limits and data handling.

Start the web workspace in a second terminal (Node.js 22.12+ or a supported newer release):

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://127.0.0.1:5173`. Root `.env` settings `WEB_HOST`, `WEB_PORT`, and optional `API_PROXY_TARGET` configure the dev server; by default `/api` proxies to `API_HOST` / `API_PORT`. Selecting an example fills the form without submitting. Starting an investigation in Meta mode uses credits. Opening saved reports does not call the model. See the [frontend guide](docs/FRONTEND.md) for production routing and checks.

Checks from the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m ruff check backend
.\.venv\Scripts\python.exe -m ruff format backend --check
```

New project work starts on October 26, 2026. External dependencies and reused components must be attributed; earlier private work must not be presented as hackathon output.

## Submission target

Public GitHub repository and a three-minute demo submitted through Cerebral Valley by **November 5, 2026, 05:00 Europe/Istanbul** (November 4, 21:00 US Eastern). Recheck the event's written rules before submission.

## License

Clear Context is released under the [MIT License](LICENSE). Third-party dependencies keep their own licenses. The Meta wordmark and Muse artwork in `frontend/public/brand/` are third-party trademarks and artwork, not covered by this license; see [brand asset notes](frontend/public/brand/README.md).
