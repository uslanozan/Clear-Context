"""Draw the opt-in text research workflow using the project diagram theme."""

from generate import arrow, node, text, write


def main():
    positions = [(40, 180), (445, 180), (850, 180), (850, 390), (445, 390), (40, 390)]
    labels = [
        ("Extract claims", ["Text input → source spans", "Meta extraction"]),
        ("Plan questions", ["V5 query planner", "Claim → need → query"]),
        ("Search and read", ["Tavily keyless", "Up to 6 searches / 3 pages"]),
        ("Select passages", ["Muse selects per need", "Keep source text + offsets"]),
        ("Assess components", ["V2 judge, one need per call", "Supported / conflicting / unknown"]),
        ("Save and inspect", ["Report, sources and excerpts", "Highlight exact source text"]),
    ]
    body = ""
    for (x, y), (title, lines) in zip(positions, labels):
        body += node(x, y, 350, 112, title, lines, focal=title == "Assess components")
    for a, b in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]:
        x1, y1 = positions[a]
        x2, y2 = positions[b]
        if y1 != y2:
            body += arrow([(x1 + 175, y1 + 112), (x2 + 175, y2)])
        elif x2 > x1:
            body += arrow([(x1 + 350, y1 + 56), (x2, y2 + 56)])
        else:
            body += arrow([(x1, y1 + 56), (x2 + 350, y2 + 56)])
    body += text(40, 598, "Claim-wide coverage and source reliability remain unverified.", 18)
    return write("13-text-research", "From text to source-backed details",
        "Opt-in text research · Meta + Tavily · bounded calls", "IMPLEMENTED / OPT-IN", body,
        "Each need is assessed independently. Unreadable sources and unfinished steps remain limitations. "
        "The report preserves relevant source context; the overall claim remains unresolved when coverage is unknown.",
        "services/investigation_research.py; schemas/component_judgment.py; components/ReportView.tsx",
        "Solid arrows: implemented flow | Image and video analysis not connected")


if __name__ == "__main__":
    main()
