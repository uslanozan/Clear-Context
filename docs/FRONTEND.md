# Frontend

React, TypeScript, Vite, Mantine, TanStack Query, and React Router power the local web workspace. The backend remains the only place that holds the Meta key.

## Run

Start the backend from the repository root, then run `npm ci` and `npm run dev` in `frontend/`. The default URL is `http://clearcontext.localhost:5173` (or `http://127.0.0.1:5173`); Vite accepts `*.localhost` host names.

| Root environment setting | Default | Purpose |
| --- | --- | --- |
| `WEB_HOST` | `127.0.0.1` | Web dev server bind address |
| `WEB_PORT` | `5173` | Strict dev server port |
| `API_HOST` / `API_PORT` | `127.0.0.1` / `8000` | Backend proxy destination |
| `API_PROXY_TARGET` | Empty | Optional HTTP(S) backend override |

Restart Vite after changing these settings. The **Settings** page (`/settings`) changes server settings at runtime: API keys are write-only fields that are never filled from the server, paid calls need a confirmation dialog, and only changed fields are sent. Browser requests use relative `/api` paths. Only deliberately public variables prefixed `VITE_PUBLIC_` can enter client code; never put credentials in that namespace. Binding a dev server on a network interface is not a production deployment or authentication solution.

## Shared design

- `src/theme.ts`: Mantine palette, fonts, radii, and component defaults.
- `src/styles.css`: shared surface/text tokens, layout, reusable domain classes, responsive rules, focus, and reduced-motion styles.
- A dark theme: near-black navy page, lifted navy surfaces and rail, Meta blue for actions and a cream highlighter for quoted evidence. Onest for text and JetBrains Mono for timestamps and counts; both are bundled locally.
- `components/StepGlyph.tsx` draws one glyph per recorded stage; it moves only while that stage runs and stays still under reduced motion. `components/Logo.tsx` holds the Clear Context mark (also in `public/brand/`).
- `Composer`, `Sidebar`, and `ReportView` share this system. Use Mantine controls for forms, dialogs, alerts, and disclosure rather than introducing a second component library.

## Working flow

Paste text, explicitly start an investigation, follow recorded progress, and inspect the saved report. Examples only fill the form. History links and report reloads do not run inference. Reports support copying their local URL and exporting JSON; a local link requires access to the same server and database.

Submission never retries automatically. A failed submission preserves the passage, and a failed investigation can reopen its original text for editing. Query polling stops at terminal status. The current API has no idempotency key: a lost network response can leave an accepted investigation in history, so check history before manually resubmitting.

Source research and server-side media analysis are pending. Clipboard, file picker, and drag/drop accept up to 4 local image/video previews (20 MB per image, 100 MB per video, 100 MB combined). Previews can be removed and are cleaned up on unmount. Media is not uploaded or persisted; attached media explicitly blocks text-only submission. Video playback depends on browser codec support, with a visible failure fallback. All current findings remain unresolved; the UI displays this explicitly. Activity and token usage come from stored API data. Mobile layout uses a navigation drawer and a single-column report; it is not an installable PWA yet.

## Checks

Run in `frontend/`:

```sh
npm test
npm run build
npm run format:check
```

Behavior tests mock HTTP responses and cover example loading without POST, double-click submission protection, report rendering, input preservation with no automatic retry, saved-report reads, and disconnected submission. They do not spend Meta credits. Browser checks use the actual local API and saved reports.

For production, build output is `frontend/dist/`. Serve it with SPA fallback to `index.html` for `/investigations/:id` and reverse-proxy `/api` to FastAPI before that fallback. Vite preview alone does not proxy the API. The Docker image does this with nginx; see [frontend/nginx.conf](../frontend/nginx.conf) and the README's Docker section.

## Dependencies and assets

Mantine (MIT), React (MIT), Vite (MIT), TanStack Query (MIT), React Router (MIT), and Lucide (ISC) retain their upstream licenses. Onest and JetBrains Mono fonts use the SIL Open Font License; packaged font licenses remain in their installed dependencies. The Clear Context mark is original to this project.

The durable visual rules are in [DESIGN.md](../DESIGN.md). The official Meta and Muse assets have separate [attribution](../frontend/public/brand/README.md).

## Review saved extraction runs

Open **Extraction review** in the web workspace and choose the local `evals/runs` folder. The browser reads matching `run.json` and `results.jsonl` files locally; it does not upload them or start model calls. Select up to two runs and an input to inspect their recorded claims, source passages, processing ranges, and token-based cost estimates. The folder is ignored by Git and may not be present in another checkout. Reloading the page requires selecting the folder again. Extracted statements and processed ranges do not establish truth or exhaustive extraction.

## Chrome extension

`extension/` holds the Manifest V3 extension; `npm run build:extension` builds it into `dist-extension/` with `vite.extension.config.ts`. It shares the theme, styles, types and stage titles (`src/lib/stages.ts`) with the web app. `background.ts` owns the context menus and cuts captures from `chrome.tabs.captureVisibleTab` (the `activeTab` grant from a menu or toolbar click); `area.ts` is a self-contained content script for drag selection; `CaptureApp.tsx` previews, starts the investigation on an explicit click, polls recorded steps and opens the web report; `PopupApp.tsx` is the toolbar menu. Captures live in `chrome.storage.session` and are removed once the server accepts them.
