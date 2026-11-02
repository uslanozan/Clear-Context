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
- A dark theme built from two logo blues (#0161dd, #047bf2), the gray #1f1f22 and glass (translucent, blurred surfaces over a blurred copy of the logo). Funnel Display for headings, Funnel Sans for text, JetBrains Mono for data; all bundled locally.
- `components/StepJolly.tsx` shows the Jolly illustration for a recorded stage (`public/brand/jolly/<event>.webp`) on the progress page and in the step list, and in place of the stage that failed. `components/StepGlyph.tsx` draws one glyph per recorded stage; it moves only while that stage runs and stays still under reduced motion. `components/Logo.tsx` holds the Clear Context mark (also in `public/brand/`).
- `Composer`, `Sidebar`, and `ReportView` share this system. Use Mantine controls for forms, dialogs, alerts, and disclosure rather than introducing a second component library.

## Working flow

Paste text, attach images or video, or include links, explicitly start an investigation, follow recorded progress, and inspect the saved report. History links and report reloads do not run inference. The report's input card shows the entered text, the links in it (with images taken from linked pages) and the attached files. Each investigation step opens what it recorded. Reports export as JSON or as a Clear Context PDF built in the browser. History items can be grouped and deleted; deleting asks for confirmation and is refused while an investigation runs.

Submission never retries automatically. A failed submission preserves the passage, and a failed investigation can reopen its original text for editing. Query polling stops at terminal status. The current API has no idempotency key: a lost network response can leave an accepted investigation in history, so check history before manually resubmitting.

Clipboard, file picker, and drag/drop accept up to 4 image/video files (20 MB per image, 100 MB per video, 100 MB combined), with local previews that can be removed and are cleaned up on unmount. Report videos play from `/api/media/{id}/playable`, which serves a WebM copy when the browser cannot show the uploaded codec; a video that still cannot play shows a note. Each detail of a claim shows its recorded result, and the claim's label is counted from those results without a model call. Activity and token usage come from stored API data. Mobile layout uses a navigation drawer and a single-column report; it is not an installable PWA yet.

## Checks

Run in `frontend/`:

```sh
npm test
npm run build
npm run format:check
```

Behavior tests mock HTTP responses and cover loading without POST, double-click submission protection, confirmed deletion, claim labels, report rendering, input preservation with no automatic retry, saved-report reads, and disconnected submission. They do not spend Meta credits. Browser checks use the actual local API and saved reports.

For production, build output is `frontend/dist/`. Serve it with SPA fallback to `index.html` for `/investigations/:id` and reverse-proxy `/api` to FastAPI before that fallback. Vite preview alone does not proxy the API. The Docker image does this with nginx; see [frontend/nginx.conf](../frontend/nginx.conf) and the README's Docker section.

## Dependencies and assets

Mantine (MIT), React (MIT), Vite (MIT), TanStack Query (MIT), React Router (MIT), react-pdf (MIT), and Lucide (ISC) retain their upstream licenses. Funnel Display, Funnel Sans and JetBrains Mono fonts use the SIL Open Font License; packaged font licenses remain in their installed dependencies, and the static copies used by the PDF export keep theirs in `src/pdf/fonts/`. The logos are original to this project (AI-generated, see `public/brand/README.md`). Glass is a CSS adaptation of the idea behind [liquid-glass-js](https://github.com/dashersw/liquid-glass-js) (MIT); no code was copied. Panel and text transitions follow patterns from [transitions.dev](https://github.com/Jakubantalik/transitions.dev) under its license, with its credit comments kept.

The durable visual rules are in [DESIGN.md](../DESIGN.md). The official Meta and Muse assets have separate [attribution](../frontend/public/brand/README.md).

## Chrome extension

`extension/` holds the Manifest V3 extension; `npm run build:extension` builds it with `vite.extension.config.ts` into the repository's `chrome-extension/` folder, which is committed so users can load it without Node; rebuild and commit it with every extension or shared-source change, and `npm run check:extension` fails when it is out of date. It shares the theme, styles, types and stage titles (`src/lib/stages.ts`) with the web app. `background.ts` owns the context menus and cuts captures from `chrome.tabs.captureVisibleTab` (the `activeTab` grant from a menu or toolbar click); `area.ts` is a self-contained content script for drag selection; `CaptureApp.tsx` previews, starts the investigation on an explicit click, polls recorded steps and opens the web report; `PopupApp.tsx` is the toolbar menu. Captures live in `chrome.storage.session` and are removed once the server accepts them.
