"""Keep only the post itself from social media pages read through Tavily.

A post page also carries menus, view and like counts, the post's own timestamp, replies and
comments. Without this step those lines reached claim extraction: a view count and a stranger's
reply became claims of the post. Each rule cuts only at a marker seen on that platform's pages;
when the marker is missing the text is returned unchanged rather than guessed at.
"""

import re
from urllib.parse import urlsplit

# A page that only asks to log in, or a regional notice, carries no post at all.
NO_POST = (
    "We regret to inform you that we have discontinued operating TikTok",
    "Log into Facebook",
)

# "02:00:32 PM · 11/01/2026·86.9K": the post's own time, date and view count on X.
X_TIMESTAMP = re.compile(r"^\d{1,2}:\d{2}(?::\d{2})?\s?[AP]M\s?·\s?\d{1,2}/\d{1,2}/\d{2,4}")
X_MENU = {"Log inSign up", "Log in", "Sign up", "Post", "Views"}
VIDEO_TIME = re.compile(r"^\d{1,2}:\d{2}$")
# Counts and short dates shown around a post: "12", "2.2K", "1 like", "53 views", "10/09/26".
COUNT = re.compile(r"^[\d.,]+\s?[KMB]?(?:\s(?:likes?|views?|comments?|shares?|replies))?$", re.I)
SHORT_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{2,4}$")
THREADS_MENU = {
    "Home",
    "New thread",
    "Search",
    "Messages",
    "Activity",
    "Profile",
    "Insights",
    "Log in",
    "More",
    "Thread",
}
FACEBOOK_MENU = {"Log In", "Forgot Account?", "* * *", "Online status indicator Active"}
# "March 7 ·" or "2 November at 14:05 ·": the line right above a Facebook post's text.
FACEBOOK_DATE = re.compile(r"·\s*$")
INSTAGRAM_CHROME = re.compile(
    r"^(Log In|Sign Up|Sign up|Log in|Follow|•|Original audio|Never miss a post from .+"
    r"|Sign up for Instagram to stay in the loop\.|By continuing, you agree to .+"
    r"|.+'s profile picture|(Video|Photo) by .+ on .+)$"
)
INSTAGRAM_END = ("No comments yet.", "Log in to like or comment.", "More posts from ")
TIKTOK_MENU = {
    "TikTok",
    "Log in",
    "Search",
    "For You",
    "Explore",
    "Following",
    "Short dramas",
    "LIVE",
    "Upload",
    "Profile",
    "More",
    "Get Coins",
    "Get App",
    "watch nowWatch now",
    "more",
}


def platform(url: str) -> str | None:
    host = (urlsplit(url).hostname or "").lower().removeprefix("www.").removeprefix("m.")
    if host in {"x.com", "twitter.com", "mobile.twitter.com"}:
        return "x"
    if host in {"threads.net", "threads.com"}:
        return "threads"
    if host in {"facebook.com", "fb.com", "web.facebook.com"}:
        return "facebook"
    if host == "instagram.com":
        return "instagram"
    if host == "tiktok.com":
        return "tiktok"
    return None


def profile_picture(image_url: str) -> bool:
    """Whether an image address is an avatar or banner rather than a post's picture.

    X lists the author's 400x400 avatar before the post's photo, and it is large enough to pass
    the size check; post photos live under /media/ instead.
    """
    parts = urlsplit(image_url)
    host = (parts.hostname or "").lower()
    if host == "abs.twimg.com":
        return True
    return host == "pbs.twimg.com" and parts.path.startswith(
        ("/profile_images/", "/profile_banners/")
    )


def post_text(url: str, text: str) -> str | None:
    """The post's own wording; None when the page holds no post (a login wall or a notice)."""
    if any(marker in text for marker in NO_POST):
        return None
    cleaners = {
        "x": x_post,
        "threads": threads_post,
        "facebook": facebook_post,
        "instagram": instagram_post,
        "tiktok": tiktok_post,
    }
    clean = cleaners.get(platform(url))
    if clean is None:
        return text
    lines = clean([line.strip() for line in text.split("\n")])
    kept = "\n\n".join(line for line in lines if line)
    return kept or None


def first_index(lines: list[str], test) -> int | None:
    return next((i for i, line in enumerate(lines) if test(line)), None)


def x_post(lines: list[str]) -> list[str]:
    end = first_index(lines, X_TIMESTAMP.match)
    if end is None:
        return lines
    post = lines[:end]
    # A reader's community note follows the post; it is context, not the author's statement.
    note = first_index(post, lambda line: line == "Readers added context")
    if note is not None:
        post = post[:note]
    return [
        line
        for line in post
        if line not in X_MENU
        and not VIDEO_TIME.match(line)
        # The page title repeats the post: 'Name on X: "…"'.
        and not re.match(r'^.+ on X: ".*"?$', line)
    ]


def threads_post(lines: list[str]) -> list[str]:
    start = first_index(lines, lambda line: re.match(r"^[\d.,]+\s?[KMB]?\sviews$", line))
    end = first_index(lines, lambda line: line.startswith("Log in or sign up for Threads"))
    if start is None or end is None or end <= start:
        return lines
    return [
        line
        for line in lines[start + 1 : end]
        if line not in THREADS_MENU and not COUNT.match(line) and not SHORT_DATE.match(line)
    ]


def facebook_post(lines: list[str]) -> list[str]:
    start = first_index(lines, FACEBOOK_DATE.search)
    end = first_index(lines, lambda line: line == "All reactions:")
    if start is None:
        return lines
    body = lines[start + 1 : end] if end and end > start else lines[start + 1 :]
    return [line for line in body if line not in FACEBOOK_MENU]


def instagram_post(lines: list[str]) -> list[str]:
    end = first_index(lines, lambda line: line.startswith(INSTAGRAM_END))
    # A comment is a user name, its text, then "1 like" and "Reply".
    reply = first_index(lines, lambda line: line == "Reply")
    if reply is not None and reply >= 3 and (end is None or reply - 3 < end):
        end = reply - 3
    body = lines[:end] if end is not None else lines
    return [line for line in body if not INSTAGRAM_CHROME.match(line) and not COUNT.match(line)]


def tiktok_post(lines: list[str]) -> list[str]:
    end = first_index(lines, lambda line: line in {"Comments", "You may like"})
    body = lines[:end] if end is not None else lines
    return [
        line
        for line in body
        if line not in TIKTOK_MENU
        and not line.startswith("©")
        and not COUNT.match(line)
        and not re.match(r"^\d{2}:\d{2} / \d{2}:\d{2}$", line)
    ]
