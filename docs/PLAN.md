# Build plan

This is a working plan, not a claim of implemented functionality. Keep the scope small enough for one developer to complete and demonstrate.

## Product focus

Initial audience: readers, independent researchers, and small editorial teams checking a claim before sharing it.

Core question: **What does the evidence support, and does the supplied visual belong to that context?**

Deliver a working web application plus a thin Chrome extension. The web application is usable without the extension. On desktop, the extension captures selected text, the page URL, and an optional selected image into the same investigation flow. On mobile, the first release supports the responsive website with pasted links and uploaded images; installation and system-share integration are stretch goals.

First demonstration: a verifiable event paired with an image documented in a different context. The system must establish the event and the image relationship independently, with clickable source evidence. If image-origin retrieval does not work reliably, it must report an unresolved image context rather than invent a provenance story.

## Decisions

| Decision | Current direction | Status |
| --- | --- | --- |
| Track / theme | Solo Indie / Build for Your World | Chosen |
| Main interaction | Investigate, inspect evidence, add new evidence | Chosen |
| Distribution | Self-hosted, bring your own Meta API key; no membership or subscription system | Chosen; controlled hosted demo separate |
| Backend | Python + FastAPI | Chosen |
| Frontend | React + TypeScript + Vite + Mantine | Text workspace implemented |
| Desktop capture | Thin Chrome Manifest V3 extension; preview, start, short status, open web report | In scope after the working web flow |
| Mobile | Responsive web first; installable PWA / Android sharing only if time remains | Native apps deferred |
| Orchestration | LangGraph with typed state, focused nodes, and bounded execution | Chosen; three-node graph implemented. Opt-in text research runs inside `evaluate_evidence` |
| Main inference service | Meta Model API | Credits confirmed; small extraction checks passed |
| Retrieval | Per-investigation source collection first | Implemented for opt-in text research: per-investigation sources, snapshots and passages in SQLite; no vector database |
| Web search / extraction | Tavily keyless Search/Extract used for text research; rate limits, quota and failures still need measuring | Partly open; no automatic paid fallback |
| Image-source lookup | Verify a usable provider before committing to automatic origin search | Open; highest external dependency risk |
| Open-weight inference | Small experiments on available partner services | Optional |
| Persistence | SQLite + SQLAlchemy + Alembic | Initial API implemented |
| Packaging / hosting | Docker Compose after the working flow; hosted demo separate | Local Docker Compose implemented; hosted demo not started |

## Milestones

| Date (Istanbul) | Outcome | Acceptance check |
| --- | --- | --- |
| Oct 26 | Local repository, agreed scope, tool-access checks | Initial local commit authorized; push and GitHub creation still await authorization; one small Muse call when credits are visible or a separate test budget is authorized; search and image lookup feasibility checked |
| Oct 27 | Text claim to evidence report | One real case completes with excerpts supporting the stated finding |
| Oct 28 | Source validation and failure handling | Duplicate reporting is not counted as independent evidence; missing evidence stays unresolved |
| Oct 29 | Image/caption workflow | A licensed, known-context image is compared with retrieved evidence; uncertain origin is explicit |
| Oct 30 | Complete usable web flow | A user can submit input, open evidence, see research progress, and understand failed steps on desktop and phone screens |
| Oct 31 | Thin Chrome extension and report updates | User-initiated capture previews the input and opens the same web report; new evidence invalidates affected findings |
| Nov 1 | Evaluation and scope freeze | Run the selected cases, review citation accuracy, record failures and latency |
| Nov 2 | Hosted demonstration | Check in a signed-out browser; document setup and limitations |
| Nov 3 | Three-minute video and submission draft | Demonstrate implemented features with visible evidence; prepare a recording fallback |
| Nov 4 | Final checks and submission | Submit well before the Nov 5, 05:00 Istanbul deadline and verify confirmation |

Dates can shift; the deliverable order matters more than adding features.

## First implementation slice

Current progress: the text-only API, model configuration validation, relational persistence, migrations, and API tests are implemented. The three-node LangGraph workflow supports mock processing and opt-in Meta claim extraction with token usage records. With `RESEARCH_ENABLED=true`, the same graph also runs bounded text research: V5 query planning, Tavily keyless search and page reading, `full_page_v1` passage selection, and component V2 evidence assessment, saved with source-highlighted excerpts. A responsive Mantine web workspace supports text submission, history, recorded progress, report inspection, and JSON export. Claim-wide verdicts stay `unresolved` by design, and one real end-to-end smoke case does not establish general quality. Link intake, graph checkpoints/resume, revisions, fast/balanced/deep research modes, source reliability, server-side media analysis, and extension capture remain pending. Local media paste, drop, selection, and previews are implemented. See [API guide](API.md).

1. Define investigation, claim, source, evidence, and finding records.
2. Implement a Meta provider adapter, with a mock for local work before billing is ready.
3. Connect web search and page extraction with timeouts and source recording.
4. Implement a bounded loop: plan -> retrieve -> compare -> identify gaps -> stop/report.
5. Produce one report with evidence excerpts and unresolved items.
6. Put a minimal web interface around that working flow.
7. Complete evidence inspection and report revision in the web UI before building the extension.
8. Add a thin extension using the same investigation-creation contract; validate the captured content before research.

## Product surfaces

| Surface | Responsibilities | Not included in the MVP |
| --- | --- | --- |
| Web | Text/URL/image input; input preview; progress; complete evidence report; correction/new-source flow; stable report URLs | Generic chat interface, graph/dashboard as the main feature |
| Chrome extension | User-invoked selected-text/page capture; optional selected image when accessible; preview; start investigation; brief status; open the web report | Full duplicate report UI, background scanning of all browsing, promise of universal social-site extraction |
| Mobile web | Responsive input and evidence inspection; link paste and file upload | Native Android/iOS app, mobile browser extension |
| Optional installed web app | Installation experiment and Android incoming-share feasibility check after core completion | Guaranteed cross-platform share-target behavior, offline AI research |

Capture and fetching are separate. A public URL may not expose the same content visible in the user's logged-in browser. If content is missing, ask for a selected excerpt or screenshot; never pretend an unreadable post was reviewed. Desktop Chrome support does not imply an equivalent extension experience on mobile.

## Provider allocation

Initial model choice and cost assumptions are recorded in [Model plan](MODELS.md). Validate them with a small reviewed evaluation before adding model routing.

- **Meta API:** primary reasoning and multimodal evaluation. Begin here.
- **Baseten:** optional Muse Spark Open experiment for decomposition, queries, and source comparison.
- **Fireworks:** optional open-weight inference comparison. Check actual eligible models before integration.
- **Modal:** optional open-weight endpoints or processing jobs. Verify the promotional credit's coverage before using paid compute.

Do not implement four integrations merely because four credit applications were submitted. Add a provider only to answer a specific quality, cost, or availability question.

## Presentation backlog — after the working product

- Design a simple logo and favicon, with readable small-size and single-color variants.
- Build a concise landing page explaining the actual working product, with a demo, limitations, and links to the application and extension.
- Keep the landing page in the web frontend unless separate static hosting solves a real deployment need.
- Once a public repository and deployment are authorized and exist, put the landing page URL in GitHub's About / Website field and link it from the README. This field is a link, not hosting; GitHub Pages cannot run the FastAPI backend.
- These tasks must not delay source validation, the complete web + extension workflow, evaluation, or the required demo video. Mobile installation is also optional; prioritize by remaining time.

## Boundaries and stop conditions

- If reverse-image lookup is unavailable, demonstrate context comparison using retrieved or user-supplied source candidates, and label the limitation.
- If a source cannot be read, show the access failure; a search snippet alone must not be represented as a reviewed source document.
- If the basic research loop fails on reviewed examples, fix it before adding graph views, accounts, or extra agents.
- If an extension capture cannot retrieve an image, preserve the source URL and ask for an upload instead of silently omitting the image.
- PWA, Capacitor, Android share handling, and native iOS work must not delay the complete web + extension flow.
- No numerical confidence percentages without calibration. Prefer evidence descriptions and explicit uncertainty.
- No medical recommendations. Initial demos should avoid medical advice and allegations against identifiable private people.
- No real model calls before confirming available credits or obtaining an explicit test-spend budget.

## Kickoff requirements captured from supplied slides

- New work between October 26 and November 4; judges must distinguish event work.
- Solo participation permitted; teams up to four.
- Public GitHub repository, accessible without signing in.
- Three-minute demo video showing event work.
- Submission through the CV platform, listing the participating builder.
- Top five per track proceed to the November 9 live final.
- Basic RAG applications, simple image analyzers, and dashboard-first projects are specifically discouraged in the anti-project slide. The investigation must perform and expose meaningful research steps.
- Recordings and credit resources are to be published by the organizers; verify the current resource links.

These notes summarize kickoff screenshots supplied on October 26. The written Official Rules take precedence; detailed permissions for pre-existing libraries and submission fields still need checking.
