"""Generate the source-sharing example using the approved project theme."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "docs/diagrams"
PAPER, INK, MUTED, ACCENT = "#f8f7f4", "#252c28", "#62695f", "#a84315"


def node(x, y, title, line1, line2, focal=False):
    stroke = ACCENT if focal else "#bfc0c0"
    return f'''<g><rect x="{x}" y="{y}" width="270" height="132" rx="8" fill="white" stroke="{stroke}" stroke-width="2"/>
<text x="{x + 22}" y="{y + 36}" font-size="24" font-weight="600">{title}</text>
<text x="{x + 22}" y="{y + 72}" font-size="19">{line1}</text>
<text x="{x + 22}" y="{y + 104}" font-size="19" fill="{MUTED}">{line2}</text></g>'''


def main():
    nodes = node(
        60, 200, "Q1 · Founding date", "Need n1 → claim C1", "One search request"
    )
    nodes += node(
        60, 405, "Q2 · Faculty history", "Need n2 → claim C1", "A different query"
    )
    nodes += node(
        430, 303, "Source S1", "Same canonical URL", "Keep both query hits", True
    )
    nodes += node(800, 303, "Page P1", "Read once; reuse cache", "Keep dated snapshots")
    nodes += node(
        1170, 303, "Passage E1", "Muse selects paragraph IDs", "Candidate, not a verdict"
    )
    arrows = """<path d="M330 266H380V369H430"/><path d="M330 471H380V369H430"/>
<path d="M700 369H800"/><path d="M1070 369H1170"/>"""
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="sharing-title sharing-description">
<title id="sharing-title">Two queries share a source without losing their needs</title>
<desc id="sharing-description">Synthetic example. Q1 references need n1 and Q2 references need n2; both needs reference C1. They discover one URL S1. One cached page P1 supplies a literal candidate E1 that may be linked for review to both needs. No factual verdict or application integration is implied.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="{MUTED}"/></marker></defs>
<rect width="1600" height="900" fill="{PAPER}"/>
<g font-family="Source Sans 3, sans-serif" fill="{INK}">
<text x="60" y="76" font-size="36" font-weight="600">Share the page, preserve every research link</text>
<text x="60" y="122" font-size="22" fill="{MUTED}">Implemented research service and evaluation runner · Not connected to the app graph</text>
<g fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#arrow)">{arrows}</g>{nodes}
<text x="60" y="642" font-size="25" font-weight="600">The relationships are records, not guessed similarities</text>
<text x="60" y="694" font-size="22">Q1 → n1 → C1     ·     Q2 → n2 → C1     ·     E1 → n1, n2 for review</text>
<text x="60" y="743" font-size="22" fill="{MUTED}">Case-scoped IDs + foreign keys prevent cross-case collisions and orphan links</text>
<text x="60" y="801" font-size="20" fill="{MUTED}">Default: ten model calls in flight; each hit keeps its rank, snippet and retrieval time</text>
<text x="60" y="849" font-size="18" fill="{MUTED}">Synthetic illustration · Existing planned needs only · No automatic truth judgment</text>
</g></svg>'''
    (OUT / "svg/10-source-sharing.svg").write_text(svg, encoding="utf-8")
    page = (
        """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Shared sources | Clear Context</title><style>body{margin:0;padding:24px;background:#f8f7f4;color:#252c28;font:18px/1.6 'Source Sans 3',sans-serif}main{max-width:1600px;margin:auto}svg{width:100%;height:auto}a{color:#a84315}code{font-size:15px}</style></head><body><main>"""
        + svg
        + """<p>Arrows show data movement. The bottom row shows the stored identity links. Candidate passages require semantic review; exact offsets alone do not prove support.</p><p>Code: <code>backend/src/clear_context/services/passage_selection.py</code> and <code>backend/src/clear_context/repositories/retrieval.py</code></p></main></body></html>"""
    )
    (OUT / "html/10-source-sharing.html").write_text(page, encoding="utf-8")

    return {
        "slug": "10-source-sharing",
        "title": "Shared sources and preserved research links",
        "status": "EVALUATION SERVICE",
        "notes": "Two saved queries share a source while keeping their need and claim links. Literal candidate passages are not factual verdicts. Not connected to the application graph.",
    }


if __name__ == "__main__":
    main()
