# Clear Context

Investigate a claim. Inspect the evidence. Recover the context.

Clear Context is a multimodal research agent being built for the Meta Global AI Developer Hackathon (October 26–November 4, 2026), in the solo Indie Developer track.

**Status: initial local API implemented in mock mode. Real model inference, source retrieval, the web UI, and the Chrome extension are not implemented yet.**

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

Accounts, subscriptions, and billing management are outside the MVP. A controlled hosted hackathon demo is separate from the local product. Simple Docker Compose packaging is planned after the first working flow; installation commands are not available yet. An open-source license will be selected before public release.

## Technology direction

- **Backend:** Python + FastAPI, with validated data contracts and a bounded LangGraph workflow. Investigation status, node progress, and reports persist in SQLite; graph checkpoints/resume are not implemented yet.
- **Frontend:** React + TypeScript + Vite, for the responsive investigation and evidence interface.
- **Extension:** a thin Chrome Manifest V3 client using the same backend; the full report stays on the web.
- **Primary models:** Muse through Meta Model API; exact model selection follows small quality/cost experiments.
- **Optional experiments:** Meta open-weight inference on Baseten, Fireworks, or Modal, subject to access and evaluation.
- **Storage:** SQLite with SQLAlchemy and Alembic migrations; no separate database server.

Partner credits have been applied for; availability is not assumed. Search, page extraction, and reverse-image lookup providers still need to be selected and verified.

## Delivery order

1. Prove a real claim-to-evidence workflow through the backend.
2. Build the complete web submission and report experience.
3. Add the thin Chrome capture extension and test the combined flow.
4. If the core is complete and time remains, test PWA installation and Android incoming sharing. iOS native integration is not part of this hackathon scope.

## Project documents

- [Build plan](docs/PLAN.md)
- [Model plan](docs/MODELS.md)
- [Architecture and evidence contract](docs/ARCHITECTURE.md)
- [Evaluation plan](evals/README.md)
- [Initial case specifications](evals/case-specs.json)

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

Mock mode is the only implemented mode. A configured API key does not enable external calls. Inputs are preserved as one claim and every mock finding is unresolved; no source has been searched or verified.

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

A project license has not been selected. Public repository visibility alone does not grant an open-source license. Third-party code and assets retain their respective licenses.
