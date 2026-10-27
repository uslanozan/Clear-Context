"""Build the source HTML for the documented Clear Context workflows."""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent.parent
PAPER, PANEL, INK, MUTED, ACCENT = "#f8f7f4", "#eeede8", "#252c28", "#62695f", "#a84315"
FONT = "Source Sans 3"


def text(x, y, lines, size=16, color=INK, weight=400, anchor="start", line_height=24):
    if isinstance(lines, str):
        lines = [lines]
    spans = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else line_height}">{html.escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return f'<text x="{x}" y="{y}" font-family="{FONT},sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{spans}</text>'


def node(x, y, w, h, title, lines=(), focal=False, proposed=False, terminal=False):
    stroke = ACCENT if focal else MUTED
    dash = ' stroke-dasharray="6 4"' if proposed else ""
    shape = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{20 if terminal else 8}" fill="{PANEL if focal else PAPER}" stroke="{stroke}" stroke-width="1.5"{dash}/>'
    return (
        shape
        + text(x + 20, y + 32, title, 16, INK, 600)
        + text(x + 20, y + 60, list(lines), 16, MUTED, line_height=22)
    )


def arrow(points, label="", dashed=False, focal=False):
    color = ACCENT if focal else MUTED
    if len(points) == 2:
        path = f"M{points[0][0]} {points[0][1]} L{points[1][0]} {points[1][1]}"
    else:
        path = f"M{points[0][0]} {points[0][1]}"
        for i in range(1, len(points) - 1):
            before, corner, after = points[i - 1], points[i], points[i + 1]
            dx, dy = corner[0] - before[0], corner[1] - before[1]
            ex, ey = after[0] - corner[0], after[1] - corner[1]
            start = (
                corner[0] - (8 if dx > 0 else -8 if dx < 0 else 0),
                corner[1] - (8 if dy > 0 else -8 if dy < 0 else 0),
            )
            end = (
                corner[0] + (8 if ex > 0 else -8 if ex < 0 else 0),
                corner[1] + (8 if ey > 0 else -8 if ey < 0 else 0),
            )
            path += (
                f" L{start[0]} {start[1]} Q{corner[0]} {corner[1]} {end[0]} {end[1]}"
            )
        path += f" L{points[-1][0]} {points[-1][1]}"
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    output = f'<path d="{path}" fill="none" stroke="{color}" stroke-width="1.6" marker-end="url(#arrow{"-accent" if focal else ""})"{dash}/>'
    if label:
        first, second = points[0], points[1]
        x, y = (first[0] + second[0]) / 2, (first[1] + second[1]) / 2
        if first[1] == second[1]:
            width = len(label) * 7 + 16
            output += (
                f'<rect x="{x - width / 2}" y="{y - 32}" width="{width}" height="24" fill="{PAPER}"/>'
                + text(x, y - 15, label, 12, MUTED, anchor="middle")
            )
        else:
            width = len(label) * 7 + 16
            output += (
                f'<rect x="{x + 8}" y="{y - 12}" width="{width}" height="24" fill="{PAPER}"/>'
                + text(x + 16, y + 5, label, 12, MUTED)
            )
    return output


def write(
    slug,
    title,
    subtitle,
    status,
    body,
    notes,
    code,
    legend="Solid: implemented flow | Dashed: return / asynchronous message",
):
    defs = f'<defs><marker id="arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="{MUTED}"/></marker><marker id="arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0,8 3,0 6" fill="{ACCENT}"/></marker></defs>'
    svg = f'<svg viewBox="0 0 1280 720" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="{slug}-title {slug}-desc"><title id="{slug}-title">{html.escape(title)}</title><desc id="{slug}-desc">{html.escape(subtitle)}</desc>{defs}<rect width="1280" height="720" fill="{PAPER}"/>'
    svg += text(40, 64, title, 40, weight=600) + text(40, 108, subtitle, 16, MUTED)
    svg += (
        f'<line x1="40" y1="136" x2="1240" y2="136" stroke="{MUTED}" stroke-width="1"/>'
    )
    svg += text(1240, 116, status, 12, ACCENT, 600, "end") + body
    svg += (
        f'<line x1="40" y1="652" x2="1240" y2="652" stroke="{MUTED}" stroke-width="1"/>'
        + text(40, 684, legend, 12, MUTED)
        + text(1240, 684, "CLEAR CONTEXT / 2026-10-27", 12, MUTED, anchor="end")
        + "</svg>"
    )
    style = f"""*{{box-sizing:border-box}}body{{margin:0;padding:24px;background:{PAPER};color:{INK};font-family:'{FONT}',sans-serif}}.frame{{max-width:1328px;min-width:0;margin:auto}}h1{{font-size:24px;line-height:32px;margin:0 0 8px}}.page-note{{margin:0 0 16px;line-height:24px}}p,li{{line-height:1.6}}a{{color:{ACCENT};text-underline-offset:3px}}.diagram-container{{width:100%;overflow-x:auto}}svg{{display:block;width:100%;min-width:1280px}}details{{margin-top:20px}}code{{font-family:Consolas,monospace;font-size:13px}}@media print{{body{{padding:0}}h1,.page-note,details{{display:none}}.diagram-container{{overflow-x:visible}}svg{{min-width:0}}}}"""
    rendered = f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} | Clear Context</title><link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600&amp;display=swap" rel="stylesheet"><style>{style}</style></head><body><main class="frame"><h1>{html.escape(title)}</h1><p class="page-note">{html.escape(status)}. Static explanation, not an execution trace. <a href="index.html">All diagrams</a></p><div class="diagram-container">{svg}</div><details open><summary>Notes and code references</summary><p>{html.escape(notes)}</p><code>{html.escape(code)}</code></details></main></body></html>'
    (OUT / "html" / f"{slug}.html").write_text(rendered, encoding="utf-8")
    return {"slug": slug, "title": title, "status": status, "notes": notes}


def sequence():
    xs = [144, 464, 784, 1104]
    actors = ["Browser", "FastAPI + LangGraph", "Meta API", "SQLite"]
    body = "".join(
        f'<line x1="{x}" y1="232" x2="{x}" y2="608" stroke="{MUTED}" stroke-dasharray="3 5"/>'
        for x in xs
    )
    # Responses are grouped; the UI actually polls three separate GET endpoints.
    messages = [
        (0, 1, 264, "POST TEXT", False),
        (1, 3, 296, "SAVE QUEUED", False),
        (1, 0, 328, "202 + ID", True),
        (1, 2, 368, "TEXT + SCHEMA", False),
        (2, 1, 408, "CLAIMS JSON", True),
        (1, 3, 456, "SAVE REPORT", False),
        (0, 1, 504, "GET RESULTS", False),
        (1, 3, 536, "READ", False),
        (3, 1, 568, "STORED DATA", True),
        (1, 0, 608, "REPORT", True),
    ]
    for a, b, y, label, dash in messages:
        body += arrow([(xs[a], y), (xs[b], y)], label, dashed=dash)
    for x, name in zip(xs, actors):
        body += node(x - 120, 168, 240, 64, name)
    return write(
        "01-text-sequence",
        "Text request: from browser to saved report",
        "The background task extracts claims; opening the saved report does not call Meta.",
        "IMPLEMENTED",
        body,
        "The API saves queued state before responding. Background processing starts after the response. One successful extraction makes one Meta call. Internal evaluation and report validation do not call Meta. GET results groups status, steps, and report polling; it is not a single endpoint. Message spacing is illustrative, not latency. Failure paths are detailed in diagram 02.",
        "api/routes/investigations.py; services/investigation.py; graph/investigation.py; providers/meta.py",
    )


def guards():
    body = arrow([(312, 240), (432, 240)]) + arrow([(592, 296), (592, 352)])
    body += arrow([(432, 432), (312, 432)], "VALID") + arrow(
        [(752, 432), (864, 432)], "INVALID"
    )
    body += arrow([(180, 504), (180, 584), (432, 584)])
    body += node(
        48,
        184,
        264,
        112,
        "Original paragraph",
        ["1-20,000 characters", "One complete input"],
    )
    body += node(
        432,
        184,
        320,
        112,
        "Muse extraction",
        ["Strict JSON: claims[]", "Default: at most 8 claims"],
        focal=True,
    )
    body += (
        '<polygon points="592,352 752,432 592,512 432,432" fill="'
        + PAPER
        + '" stroke="'
        + MUTED
        + '" stroke-width="1.5"/>'
        + text(592, 428, "Accept the response?", 16, weight=600, anchor="middle")
        + text(592, 452, "Schema + exact text", 16, MUTED, anchor="middle")
    )
    body += node(
        48,
        392,
        264,
        112,
        "Claims with UUIDs",
        ["Literal source wording", "Usage receipt recorded"],
    )
    body += node(
        864,
        392,
        320,
        112,
        "Reject the target range",
        ["Record partial coverage", "Original text stays saved"],
        terminal=True,
    )
    body += node(
        432, 548, 320, 72, "Unresolved report", ["No retrieved evidence"], terminal=True
    )
    body += text(
        864,
        204,
        [
            "Required guards",
            "Completed output; valid schema",
            "Grounded source/context spans",
            "No tool calls or refusal",
        ],
        16,
        MUTED,
        line_height=24,
    )
    return write(
        "02-extraction-guards",
        "Selecting claims is not checking their truth",
        "The model proposes spans; Python accepts or rejects the returned structure.",
        "IMPLEMENTED",
        body,
        "V2 validates exact quotes and source/context offsets while storing the independent statement as a model interpretation. The default per-call completion budget is 4,096 tokens. A saturated or truncated range can split; invalid or deferred ranges remain partial. V1 remains a legacy single-call contract. Literal anchoring does not verify statement meaning or truth. See diagram 07 for bounded chunk processing.",
        "providers/meta.py: ExtractedClaims and extract_claims; domain/investigation.py: Claim; graph/nodes/validate_report.py",
        "Solid: implemented flow | VALID / INVALID: response acceptance, not truth",
    )


def media():
    body = ""
    for y in [204, 416]:
        body += arrow([(344, y + 56), (472, y + 56)]) + arrow(
            [(808, y + 56), (936, y + 56)]
        )
    body += node(
        48,
        204,
        296,
        112,
        "Image pasted or selected",
        ["PNG / JPEG / WebP / GIF", "Max 20 MB"],
        terminal=True,
    )
    body += node(
        472,
        204,
        336,
        112,
        "Browser image preview",
        ["Object URL, local only", "Remove to release preview"],
    )
    body += node(
        936,
        204,
        296,
        112,
        "No submission",
        ["Text-only POST blocked", "No image sent to Meta"],
        terminal=True,
        focal=True,
    )
    body += node(
        48,
        416,
        296,
        112,
        "Video pasted or selected",
        ["MP4 / WebM / QuickTime", "Max 100 MB"],
        terminal=True,
    )
    body += node(
        472,
        416,
        336,
        112,
        "Browser video preview",
        ["Local playback controls", "Codec errors shown inline"],
    )
    body += node(
        936,
        416,
        296,
        112,
        "No submission",
        ["No frames or transcript", "No AI detector runs"],
        terminal=True,
    )
    body += text(
        48,
        604,
        "Shared limits: 4 files / 100 MB total. Unsupported, empty, or oversized files show an error.",
        16,
        MUTED,
    )
    return write(
        "03-media-today",
        "What happens to an image or video today",
        "Accepted files remain in this browser tab; there is no server-side media pipeline.",
        "IMPLEMENTED",
        body,
        "Clipboard works when it contains actual file data; copying a media URL does not automatically fetch the file. Selection and drag/drop share validation. Duplicates are skipped. Preview errors offer removal. Attached media blocks normal and keyboard text submission rather than being silently dropped. Navigating away releases the local object URLs. No OCR, ASR, image lookup, C2PA, or generation detector is integrated.",
        "frontend/src/components/Composer.tsx; components/MediaPreview.tsx; lib/media.ts",
        "Solid: implemented flow | No submission: explicit current boundary",
    )


def longtext():
    arrows = (
        arrow([(312, 240), (432, 240)], dashed=True)
        + arrow([(752, 240), (864, 240)], dashed=True)
        + arrow([(1016, 296), (1016, 392)], dashed=True)
        + arrow([(864, 448), (752, 448)], dashed=True)
        + arrow([(432, 448), (312, 448)], dashed=True)
    )
    body = arrows + node(
        48,
        184,
        264,
        112,
        "Document + context",
        ["Keep original text", "Posting time, if known"],
        proposed=True,
    )
    body += node(
        432,
        184,
        320,
        112,
        "Bounded context chunks",
        ["Paragraph boundaries", "Overlap + stable offsets"],
        proposed=True,
    )
    body += node(
        864,
        184,
        304,
        112,
        "Extract quoted spans",
        ["Per-chunk budget", "No silent truncation"],
        proposed=True,
    )
    body += node(
        864,
        392,
        304,
        112,
        "Resolve qualifiers",
        ["Who, when, conditions", "Keep attribution explicit"],
        proposed=True,
    )
    body += node(
        432,
        392,
        320,
        112,
        "Validate and merge",
        ["Anchor to original offsets", "Deduplicate overlap"],
        proposed=True,
    )
    body += node(
        48,
        392,
        264,
        112,
        "Claim relationships",
        ["Shared subject / condition", "Evidence still required"],
        proposed=True,
    )
    body += text(
        48,
        580,
        [
            'Example: "It" can refer to Cedar Museum; "yesterday" stays unresolved without posting context.',
            "Free on Tuesdays and not free on other days are compatible conditions, not a contradiction.",
        ],
        16,
        MUTED,
        line_height=26,
    )
    return write(
        "04-long-text-proposal",
        "Preserving context in longer text",
        "A richer document model remains proposed; bounded chunk processing now exists in diagram 07.",
        "PROPOSED",
        body,
        "Character-budget partitioning, context windows, literal offsets, separate interpreted statements, and partial coverage are now implemented; see diagram 07. This figure remains a proposal for richer document reconciliation and explicit entity/relation records. Processing all input ranges does not establish exhaustive claim coverage. Relationship extraction is not automatic verification.",
        "Proposed extension to providers/meta.py and domain/investigation.py; see docs/TEXT_ANALYSIS.md",
        "Dashed nodes and connectors: proposed, not implemented",
    )


def photo():
    body = arrow([(312, 324), (352, 324), (352, 236), (432, 236)], dashed=True) + arrow(
        [(312, 372), (384, 372), (384, 444), (432, 444)], dashed=True
    )
    body += arrow(
        [(752, 236), (840, 236), (840, 324), (904, 324)], dashed=True
    ) + arrow([(752, 444), (872, 444), (872, 372), (904, 372)], dashed=True)
    body += (
        arrow([(1056, 408), (1056, 520)], dashed=True)
        + arrow([(180, 404), (180, 520)], dashed=True)
        + arrow([(312, 572), (904, 572)], "OPTIONAL", dashed=True)
    )
    body += node(
        48,
        292,
        264,
        112,
        "Photo + caption",
        ["Explicit upload consent", "Keep them separate"],
        proposed=True,
    )
    body += node(
        432,
        184,
        320,
        104,
        "Caption assertions",
        ["Event / date / place", "Do not infer from pixels"],
        proposed=True,
    )
    body += node(
        432,
        392,
        320,
        104,
        "Visual observations",
        ["Visible objects + OCR", "Date / origin still unknown"],
        proposed=True,
    )
    body += node(
        904,
        296,
        304,
        112,
        "Source comparison",
        ["Find earlier appearances", "Compare text and context"],
        proposed=True,
    )
    body += node(
        904,
        520,
        304,
        104,
        "Independent findings",
        ["Text may be supported", "Photo may be unrelated"],
        proposed=True,
    )
    body += node(
        48,
        520,
        264,
        104,
        "Authenticity signals",
        ["Optional credentials", "Detector only if evaluated"],
        proposed=True,
    )
    return write(
        "05-photo-proposal",
        "A true event can have an unrelated photograph",
        "Research the caption and the image context independently before combining findings.",
        "PROPOSED / OPTIONAL",
        body,
        "Synthetic case: a current event uses an older photograph. No source lookup has been performed for this example. Metadata/credentials and any AI-generation detector would be optional independent signals. Missing credentials do not imply generation. A model cannot prove date, location, or authenticity from appearance alone. No detector or media provider is selected or integrated.",
        "Proposed media branch; current boundary remains docs/diagrams/html/03-media-today.html",
        "Dashed: proposed flow | OPTIONAL: experiment, not a truth verdict",
    )


def video():
    body = arrow([(312, 324), (352, 324), (352, 236), (432, 236)], dashed=True) + arrow(
        [(312, 372), (384, 372), (384, 444), (432, 444)], dashed=True
    )
    body += (
        arrow([(752, 236), (840, 236), (840, 324), (904, 324)], dashed=True)
        + arrow([(752, 444), (872, 444), (872, 372), (904, 372)], dashed=True)
        + arrow([(1056, 408), (1056, 520)], dashed=True)
    )
    body += node(
        48,
        292,
        264,
        112,
        "Video + description",
        ["Bound file size / duration", "Preserve original clip"],
        proposed=True,
    )
    body += node(
        432,
        184,
        320,
        104,
        "Sample bounded frames",
        ["Record frame timestamps", "Sampling is not full coverage"],
        proposed=True,
    )
    body += node(
        432,
        392,
        320,
        104,
        "Optional audio transcript",
        ["Only when audio exists", "Preserve segment times"],
        proposed=True,
    )
    body += node(
        904,
        296,
        304,
        112,
        "Time-linked claims",
        ["Caption / speech / visuals", "Keep their sources distinct"],
        proposed=True,
    )
    body += node(
        904,
        520,
        304,
        104,
        "Evidence per interval",
        ["Sources linked to time", "Report unseen portions"],
        proposed=True,
    )
    body += text(
        48,
        592,
        [
            "Example: a claim about 00:12 needs the corresponding frame or audio segment.",
            "A frame detector cannot certify a whole video; no detector is connected today.",
        ],
        16,
        MUTED,
        line_height=24,
    )
    return write(
        "06-video-proposal",
        "Video claims need timestamps and coverage limits",
        "Frame sampling and optional transcription are proposed preprocessing, not working features.",
        "PROPOSED / OPTIONAL",
        body,
        "A silent clip takes only the frame branch. If transcription or decoding fails, preserve that gap. Compare claims with external sources and the relevant interval. Sampling can miss edits or events; neither a few real frames nor a detector score proves the entire clip. Media analysis, sampling, ASR, and AI detection are not implemented.",
        "Proposed preprocessing and timestamped claim contracts; current input supports local previews only",
        "Dashed: proposed flow | Optional audio is skipped for silent clips",
    )


def chunked():
    body = arrow([(320, 234), (432, 234)])
    body += arrow([(744, 234), (888, 234)])
    body += arrow([(1044, 284), (1044, 330)])
    body += arrow([(896, 400), (744, 400)], "YES")
    body += arrow([(588, 348), (588, 284)], "SMALLER TARGETS")
    body += arrow([(1044, 470), (1044, 520)], "NO")
    body += arrow([(432, 252), (380, 252), (380, 564), (348, 564)])
    body += text(370, 416, "NO BUDGET", 12, MUTED, anchor="end")
    body += node(
        48,
        184,
        272,
        100,
        "Original document",
        ["Preserve every character", "Short input stays whole"],
    )
    body += node(
        432,
        184,
        312,
        100,
        "Target + context queue",
        ["Prefer paragraph boundaries", "Head and nearby text are context"],
    )
    body += node(
        888,
        184,
        312,
        100,
        "One bounded model call",
        ["Quotes + independent statements", "No search or factual verdict"],
    )
    body += (
        f'<polygon points="1044,330 1192,400 1044,470 896,400" fill="{PAPER}" stroke="{ACCENT}" stroke-width="1.5"/>'
        + text(1044, 395, "More / truncated?", 16, weight=600, anchor="middle")
        + text(1044, 420, "Capacity is per response", 16, MUTED, anchor="middle")
    )
    body += node(
        432,
        348,
        312,
        104,
        "Split only this target",
        ["Keep its global source positions", "Stop at the minimum size"],
        focal=True,
    )
    body += node(
        48,
        520,
        300,
        88,
        "Partial extraction",
        ["Keep available claims and receipts", "Expose deferred/invalid ranges"],
        terminal=True,
    )
    body += node(
        888,
        520,
        312,
        88,
        "Save literal provenance",
        ["Deduplicate exact span + statement", "Processed does not mean exhaustive"],
        terminal=True,
    )
    body += text(
        432,
        555,
        [
            "Global guards: calls, output tokens, time",
            "Unsplittable capacity stays partial",
        ],
        16,
        MUTED,
    )
    return write(
        "07-chunked-claims",
        "Claim coverage without an eight-claim ceiling",
        "Implemented v2: bounded text ranges, supplied context, adaptive splitting, and explicit partial outcomes.",
        "IMPLEMENTED",
        body,
        "The default target budget is 600 Unicode characters, not tokens. Context includes document-head, previous, and next windows, each bounded to 600 characters. A response can hold 24 claims by default; capacity is not a document-wide limit. Capacity or truncation can split a target. Minimum-size, invalid, timeout, and budget cases remain partial. All source spans are anchored literally; statements remain model interpretations. No external evidence is retrieved. The figure groups error paths for readability.",
        "services/text_chunks.py; providers/meta.py; domain/investigation.py; graph/nodes/validate_report.py",
        "Solid: implemented | Partial extraction is distinct from unresolved truth",
    )


if __name__ == "__main__":
    for folder in ["html", "svg", "png", "json", "md", "py"]:
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    records = [sequence(), guards(), media(), longtext(), photo(), video(), chunked()]
    (OUT / "json/manifest.json").write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8"
    )
    links = "".join(
        f'<li><strong>{html.escape(row["title"])}</strong> <span>{row["status"]}</span><p>{html.escape(row["notes"])}</p><a href="{row["slug"]}.html">Open HTML</a> / <a href="../svg/{row["slug"]}.svg">SVG</a> / <a href="../png/{row["slug"]}.png">PNG for slides</a></li>'
        for row in records
    )
    (OUT / "html/index.html").write_text(
        f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Clear Context workflow diagrams</title><style>body{{background:{PAPER};color:{INK};font:16px/1.6 system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 24px}}li{{margin:32px 0}}a{{color:{ACCENT}}}span{{font-size:12px}}</style></head><body><h1>Clear Context workflow diagrams</h1><p>October 27, 2026. Diagrams 01-03 and 07 describe working code. Diagrams 04-06 describe proposals; 04 also notes the implemented subset. All examples are synthetic explanations, not live inference results. Source HTML is self-contained; PNG exports are 2560 x 1440.</p><ol>{links}</ol></body></html>',
        encoding="utf-8",
    )
    print(f"Generated {len(records)} HTML diagrams and index.")
