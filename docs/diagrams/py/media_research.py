"""Draw the implemented image, link and budget-continuation workflows (diagrams 14-16)."""

from generate import MUTED, arrow, node, text, write

W, H = 270, 120
COLUMNS = [40, 342, 644, 946]
ROWS = [176, 404]


def snake(nodes, focal=(), labels=None):
    """Lay out up to eight nodes left to right, then right to left on the second row."""
    labels = labels or {}
    places = []
    for index in range(len(nodes)):
        row = index // 4
        column = index % 4 if row == 0 else 3 - index % 4
        places.append((COLUMNS[column], ROWS[row]))
    body = ""
    for index in range(len(nodes) - 1):
        (x1, y1), (x2, y2) = places[index], places[index + 1]
        label = labels.get(index, "")
        if y1 != y2:
            body += arrow([(x1 + W // 2, y1 + H), (x2 + W // 2, y2)], label)
        elif x2 > x1:
            body += arrow([(x1 + W, y1 + H // 2), (x2, y2 + H // 2)], label)
        else:
            body += arrow([(x1, y1 + H // 2), (x2 + W, y2 + H // 2)], label)
    for index, ((x, y), (title, lines)) in enumerate(zip(places, nodes)):
        body += node(x, y, W, H, title, lines, focal=index in focal, terminal=index == 0)
    return body


def image_research():
    body = snake(
        [
            ("Image uploaded", ["Type from file signature", "Stored by SHA-256"]),
            ("Muse reads image", ["Exact text, observations", "Place/time cues"]),
            ("Caption vs image", ["Fits / conflicts / can't tell", "Model check, not evidence"]),
            ("Find copies", ["Google Lens: shown dates", "Bing: direct page links"]),
            ("Published fact checks", ["Fact Check image search", "Public copy, not upload"]),
            ("Claims to check", ["Caption + post statements", "Signs and stamps excluded"]),
            ("Research", ["Fact check, then early copy", "Planner sees observations"]),
            ("Image report", ["Earliest dated copy", "Publisher ratings as theirs"]),
        ],
        focal={3, 6},
        labels={3: "COPIES"},
    )
    body += text(40, 596, "Matches are leads, not proof of first publication. No AI-generation detector is used.", 16, MUTED)
    return write(
        "14-image-research",
        "Checking a photo and its caption",
        "Implemented image path: read the image, find where it appeared before, then research the claims",
        "IMPLEMENTED",
        body,
        "Muse transcribes visible text and marks which parts are statements; only statements, not signs, labels or date stamps, are extracted as claims. Caption checks compare what the caption says about the picture with visible details and are labelled a model visual assessment. SerpApi Google Lens returns same-image matches with the date Lens shows (earliest first); Bing reverse image search, queried with a Google-hosted copy Lens found, adds direct page links. Google Fact Check Tools image search uses the same copy, never the upload, and text search uses the caption. Research reads fact checks and other matching pages alternately on its own small budget, and the planner gets observations and matching page titles as context. Google redirect links that show a verification page are not read. Reverse image search runs only in Meta mode with REVERSE_IMAGE_PROVIDER set.",
        "graph/nodes/analyze_media.py; providers/meta_media.py; providers/reverse_image.py; providers/fact_check.py; services/investigation_research.py",
        "Solid: implemented flow | Accent: where most refutations came from in measured cases",
    )


def link_research():
    body = snake(
        [
            ("Text with links", ["Up to 3 http(s) links", "Found automatically"]),
            ("Read page", ["Tavily Extract, Markdown", "First 3,000 characters"]),
            ("Publication date", ["News index, exact page only", "Otherwise: unknown"]),
            ("Main image", ["Public HTTPS address only", "Connect to checked IP"]),
            ("Image checks", ["Same path as uploads", "May be a stock photo"]),
            ("Claims to check", ["Page start like pasted text", "Opinions not researched"]),
            ("Research", ["Checked page never cited", "Date given to the planner"]),
            ("Links report", ["Read / not read / failed", "Paste text if unreadable"]),
        ],
        focal={1, 6},
    )
    body += text(40, 596, "The server never fetches the page itself; only the main image is downloaded directly.", 16, MUTED)
    return write(
        "15-link-research",
        "Checking a linked page",
        "Implemented link path: a link becomes page text and an image, then follows the text and image paths",
        "IMPLEMENTED",
        body,
        "fetch_links reads up to three links in Meta mode through Tavily Extract; preview mode lists them as not opened. Only the first 3,000 characters are checked, since a whole article produced more claims than one research budget can assess. A publication date is kept only when a Tavily news search returns the exact page; it is never guessed from page text. The main image is downloaded from a public HTTPS host, with redirects re-checked and the connection pinned to the checked address, then analysed like an upload. Research never reads the checked page as its own evidence. Unreadable links (often social posts) are reported with advice to paste the text or attach a screenshot.",
        "graph/nodes/fetch_links.py; providers/link_reader.py; services/investigation_research.py; components/LinkFindings.tsx",
        "Solid: implemented flow | Accent: text reading and research",
    )


def budget_continuation():
    body = snake(
        [
            ("Plan the needs", ["Planner v7, main claims first", "Opinions: not checkable"]),
            ("Research budget", ["Searches, judge calls by mode", "Fast / Balanced / Deep"]),
            ("Research summary", ["Assessed / budget-limited", "Not checkable / context"]),
            ("Report notice", ["Shown when needs were left", "Paid runs only on a click"]),
            ("Research remaining", ["New linked report", "Earlier report unchanged"]),
            ("Copy settled claims", ["Findings, evidence, sources", "New IDs for every record"]),
            ("Research the rest", ["Only budget-limited claims", "Cached pages reused"]),
            ("Merged report", ["Can be continued again", "Images stay in the parent"]),
        ],
        focal={3, 6},
    )
    body += text(40, 596, "Run again in Deep starts the whole input as a new report; it does not merge results.", 16, MUTED)
    return write(
        "16-budget-continuation",
        "When the research budget runs out",
        "Implemented summary, notice, rerun and continuation; reports are never edited in place",
        "IMPLEMENTED",
        body,
        "Planner v7 marks opinions, value judgments and experiences only the author could know as not_checkable; they are listed but never searched or judged. Under a tight budget it plans the headline and main claims first. Each report saves a research summary; budget-limited counts the needs the planner deferred or the judgment call budget did not reach. The notice offers Run again in Deep (same text and uploads, new report) or Research remaining details: a new investigation that copies settled claims, findings, evidence and sources under new IDs and researches only budget-limited claims, starting at evaluate_evidence and passing through merge_continuation. Images and links stay in the earlier report, which is linked.",
        "services/investigation_research.py; services/continuation.py; graph/nodes/merge_continuation.py; api/routes/investigations.py; components/BudgetNotice.tsx",
        "Solid: implemented flow | Accent: user decision and the continued research",
    )
