# Clear Context interface

## Shared visual rules

- Do not end UI headings, section titles, or dialog titles with a period. For example, use `Check the context`, not `Check the context.` Preserve punctuation in quoted claims, source excerpts, and ordinary body sentences.
- Do not show a connection dot or provider-connection label in the header. Keep actionable service errors near the affected workflow.

Use Mantine with `frontend/src/theme.ts` and semantic tokens in `frontend/src/styles.css`. Preserve warm neutral surfaces and the current Clear Context mark. Use Source Sans 3 for controls, headings, and report text. Keep heading sizes proportional to the task; no marketing hero, slogans, decorative eyebrows, or placeholder illustrations inside the workspace.

The main action is adding material for an investigation. Keep input, attachment controls, preview, and submit together. A secondary rail explains the workflow with real state labels. Use the official Muse Jolly image and Meta wordmark sparingly, with original proportions and attribution in `frontend/public/brand/README.md`.

## Interaction rules

- Clipboard, file picker, and drag/drop feed the same bounded media intake. File previews stay local and are removable. Release object URLs when removed or unmounted.
- Never silently omit media from a text-only request. Media attachments currently block submission with an explicit preview-only message; the backend media pipeline remains future work.
- A text investigation starts only after user confirmation through the submit control. Examples fill the form; they do not submit it. Preserve input on request errors.
- Progress derives from stored graph events. Show pending, running, complete, stopped, and unavailable distinctly, with stage descriptions and timestamps. Do not invent percentages or source-search work.
- Keep one-column intake and reports on phones, an accessible navigation drawer, readable 16px input, keyboard focus, and reduced-motion support.

## Design tooling

Apply [Impeccable](https://github.com/pbakaus/impeccable) for hierarchy, restraint, and visual checks, and [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) for task-relevant interaction/accessibility guidance. These are development guidance, not runtime dependencies or a requirement to adopt unrelated generated templates. Product truth and the user's explicit brief take priority.
