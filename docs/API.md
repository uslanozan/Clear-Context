# Initial API

Local development only, single process, mock provider. No Meta, search, or image services are called. A real key in `.env` does not activate paid inference. Only `APP_MODE=mock` is accepted.

## Endpoints

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/api/health` | Mode and paid-call status; no credentials |
| GET | `/api/models` | Validated task selections; not live provider availability |
| POST | `/api/investigations` | Accept `{ "text": "A claim to investigate" }`; return 202 and Location |
| GET | `/api/investigations?limit=20&offset=0` | Recent history, newest first |
| GET | `/api/investigations/{id}` | Persisted status and input |
| GET | `/api/investigations/{id}/steps` | Recorded processing steps |
| GET | `/api/investigations/{id}/report` | Completed report; 409 until available |

Text must contain 1-20,000 characters after trimming. Unknown fields are rejected. Missing investigations return 404; malformed UUIDs and invalid input return 422. There is no URL fetching, image upload, cancellation, report revision, or authentication yet.

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

The example environment allows the future frontend on localhost/127.0.0.1 port 5173. The frontend is not implemented yet and has no configured listener. Adjust CORS origins when its address changes. CORS does not protect a network-exposed API from non-browser clients. Direct Uvicorn CLI commands use their own host/port flags; they do not read these custom settings automatically. One worker remains required.

## Persistence and lifecycle

SQLite stores investigations, claims, sources, evidence, findings, finding/evidence links, and research steps in relational tables with foreign keys enabled. Reports are validated before an atomic completion transaction: unknown references, unrelated evidence, nonmatching excerpts, and resolved findings without evidence are rejected.

`DATABASE_PATH` defaults to `.local/clear-context.db`. Relative database/catalog paths resolve from the repository root. `.env` is loaded from that root, and real keys are excluded from settings serialization and public responses. Existing `.env` files may omit new settings and inherit defaults.

Apply migrations before starting: `python -m alembic -c backend/alembic.ini upgrade head`. Do not replace migrations with runtime `create_all`. Normal upgrades retain data; downgrading the initial migration drops its tables and data.

State transitions: `queued -> running -> completed/failed`. Work runs in an in-process background task after the response, using LangGraph nodes `extract_claims -> evaluate_evidence -> validate_report`. Steps record `graph_started`, each successfully returned node, and `report_saved` or `investigation_failed`. Step status reflects the job lifecycle, so intermediate nodes retain `running` status. On restart, unfinished jobs are marked `failed` with `interrupted`, not silently resumed. No graph checkpointer is configured yet. Provider failures expose a generic `processing_failed` code without raw error messages. Run **one worker / one server instance per database**; this is not a durable queue and has no retry/resume guarantee. Bounded real research remains to be implemented.

Bind to loopback for this slice. Network-accessible self-hosting, HTTPS, and access protection will be addressed before public deployment. Docker packaging is planned; SQLite and uploads must use a persistent volume when added.

## Checks

Run pytest, Ruff lint, and Ruff format checks using the README commands. Tests use temporary migrated databases, exercise restart persistence, migration round trips, failure handling, evidence validation, input boundaries, and model selection. They block external connections, allowing loopback for Windows event-loop internals. Synthetic evidence fixtures are not real research results.
