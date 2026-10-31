"""Draw the opt-in text research workflow using the project diagram theme."""

from generate import arrow, node, text, write


def main():
    positions = [(40, 180), (445, 180), (850, 180), (850, 390), (445, 390), (40, 390)]
    labels = [
        ("Extract claims", ["Text input → source spans", "Meta extraction"]),
        ("Plan questions", ["V7 planner, main claims first", "Opinions: not checkable"]),
        ("Search and read", ["Every page found is read", "Skip search score < 0.30"]),
        ("Select passages", ["Muse selects per need", "Keep source text + offsets"]),
        ("Assess components", ["V5 judge, one need per call", "Repeated claim is not support"]),
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
    # Bounded loop: needs left insufficient get one follow-up search.
    body += arrow([(700, 390), (700, 336), (900, 336), (900, 292)], "ONCE, IF INSUFFICIENT")
    body += text(40, 598, "Claim-wide coverage and source reliability remain unverified.", 18)
    return write("13-text-research", "From text to source-backed details",
        "Opt-in text research · Meta + Tavily · bounded calls", "IMPLEMENTED / OPT-IN", body,
        "Planner v7 marks opinions and author-only experiences not_checkable and plans the main "
        "claims first. Every readable page that search finds is read (modes differ by search count); "
        "results Tavily scores below SEARCH_MIN_SCORE (0.30) are skipped. Pages are read as Markdown "
        "reduced to text. The v5 judge receives each passage's source type, and a passage that only "
        "repeats the claim is not support. Each need is assessed independently; a need left "
        "insufficient gets one follow-up search. Unreadable sources and unfinished steps remain "
        "limitations; the overall claim remains unresolved when coverage is unknown. Budget-limited "
        "needs can be continued (diagram 16).",
        "services/investigation_research.py; providers/tavily.py; domain/source_types.py; schemas/component_judgment.py",
        "Solid arrows: implemented flow | Images: diagram 14 | Links: diagram 15")


if __name__ == "__main__":
    main()
