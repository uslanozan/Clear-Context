# Workflow diagrams

Updated October 27, 2026 from the actual implementation. Start with [the gallery](../html/index.html) or [the text-analysis explanation](../../TEXT_ANALYSIS.md).

| Diagram | Meaning | Status |
| --- | --- | --- |
| [01 Text sequence](../html/01-text-sequence.html) | Browser, FastAPI/LangGraph, Meta, SQLite, and report reads | Implemented |
| [02 Extraction guards](../html/02-extraction-guards.html) | What the model proposes and Python validates | Implemented |
| [03 Media today](../html/03-media-today.html) | Separate photo and video examples with the current submission boundary | Implemented |
| [04 Longer text](../html/04-long-text-proposal.html) | Context chunks, offsets, qualifier handling, and relationships | Proposed |
| [05 Photo/caption](../html/05-photo-proposal.html) | Caption claims, visual observations, independent evidence, optional authenticity signals | Proposed / optional |
| [06 Video](../html/06-video-proposal.html) | Bounded frame sampling, optional speech transcription, timestamps, and partial coverage | Proposed / optional |

Each numbered HTML source has matching SVG and 2560 x 1440 PNG exports in the format-specific sibling folders. HTML is the editable source of truth. Its layout and inline SVG are standalone; the only external resource is the approved Google Fonts stylesheet for Source Sans 3. SVG exports embed the local font for portability; PNGs are static pixels. Font licensing remains SIL Open Font License from the frontend font dependency.

All cases are synthetic, manually authored explanations, not live model results. [claim-example.json](../json/claim-example.json) verifies exact character spans and explicitly labels proposed data fields. `Unresolved` is a result, not an error and not evidence of falsehood. An image detector is not integrated or required in the proposed core research path.

## Regenerate

Run `python docs/diagrams/py/generate.py` from the project root after installing frontend dependencies (`npm ci` in `frontend/`). The generator follows [Diagram Design](https://github.com/cathrynlavery/diagram-design) and the approved local [style](STYLE.md). Check each HTML with that skill's `scripts/self_check.py`, then export with its `scripts/export_svg.py` and `scripts/export_png.py` helpers. The export helper requires Playwright and Chromium; tooling is separate from the application dependencies.

Use `docs/diagrams/py/export.py` for the current repeatable export pass; it invokes the packaged helpers and adds the already licensed local Source Sans 3 font to the vector export. No Meta calls are needed. Review rendering and source-code correspondence after every material workflow change. Diagram 01 groups three GET endpoints for readability; diagram 02 combines several Python guards into one acceptance gate. No application components are omitted from the described text path, but failure/time details are expanded only where they matter.

## Folder layout

- `html/`: standalone diagrams and gallery index.
- `svg/`: editable vector exports.
- `png/`: presentation images.
- `json/`: manifest and explanatory fixtures.
- `md/`: guide and style notes.
- `py/`: generation and export tools.
