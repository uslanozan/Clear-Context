# Changelog

## 1.0.0 — first public release

Clear Context was started at the Meta Global AI Developer Hackathon (October 26 – November 4, 2026). This is the first release meant for anyone to download and run.

### What it does

- Separates text, links, images and video into claims in their original wording and splits each claim into details a source can settle.
- Researches every detail within a fixed budget (Fast, Balanced or Deep): plans searches, reads every page found, selects passages and judges the detail only against recorded passages. Unsettled details get one follow-up round.
- Checks pictures through reverse image search (optional, SerpApi) and published fact checks (optional, Google Fact Check Tools); what a picture is said to show is settled only by pages showing the same picture.
- Transcribes video speech with Muse Voice Transcribe and reads the frames with Muse Spark.
- Reports each detail as supported, contradicted, disputed, insufficient or not assessed, with every quote shown inside its page. The claim label is counted from the details, not decided by a model. Exports PDF and JSON.
- Chrome extension that captures selected text, a link, an image, a video frame or an area of a page and opens the web report.

### New since the hackathon

- **Desktop app** for Windows, macOS (Apple Silicon and Intel) and Linux: one folder, no installation; it starts a local server, sets up its database and opens the browser. Data stays in the user's application data folder.
- **Published Docker images** on GitHub Container Registry, used with `compose.ghcr.yaml`.
- **Estimated model cost** on every report, from recorded tokens and catalog list prices.
- **Preview mode notice** on the start screen until a Meta key is added and paid calls are allowed; each key in Settings links to the page where it is created.
- **Measured accuracy** on a small labeled set; see the README.
- **Citations** that differ from the page only by a non-breaking space or a line break are accepted; the measurement found two correct judgments lost this way.
- Continuous integration for the backend, the web app, the extension and the Docker build, and release builds that smoke-test every desktop app.

### Known limitations

See [Known limitations](README.md#known-limitations). In short: no verdict on truth, models can be wrong, image provenance is limited, the app has no authentication and is meant for one person on their own machine, the desktop app is not signed and the extension is loaded unpacked.
