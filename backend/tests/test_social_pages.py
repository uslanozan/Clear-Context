"""Social post pages keep the post and drop counts, replies and menus.

The page texts are synthetic, shaped like what Tavily returned for each platform.
"""

import httpx
import pytest

from clear_context.providers.link_reader import LinkFailure, TavilyLinkReader
from clear_context.providers.social_pages import platform, post_text, profile_picture

X_PAGE = """Log inSign up

Post

Log inSign up

Sample Author on X: "The bridge opened in 1932."

Sample Author@sample_author

The bridge opened in 1932.

Quoted Person@quoted_person

04/18/2024

The bridge is the oldest in the city.

Readers added context

A note from readers about the bridge.

02:00:32 PM · 11/01/2026·86.9K

Views

12

*

  Sample Author@sample_author

  The bridge opened in 1932.

*

  Someone Else@someone_else

  20h

  This reply is not part of the post."""

THREADS_PAGE = """Home

New thread

Search

Log in

More

Thread

147K views

sample.account

10/09/26

The museum reopens on Monday.

2.2K

213

Log in or sign up for Threads See what people are talking about."""

FACEBOOK_PAGE = """Log In

Forgot Account?

Sample Page's Post

* * *

Online status indicator Active

Sample Page

March 7 ·

The library was founded in 1850.

It moved to its current building in 1901.

All reactions:

7

2 comments

Most relevant

A Commenter

This comment is not part of the post."""

INSTAGRAM_PAGE = """Log In
Sign Up
Never miss a post from sample_account
Sign up for Instagram to stay in the loop.
By continuing, you agree to Instagram's Terms of Use and Privacy Policy.
sample_account
•
Follow
Original audio
sample_account
The tower is 300 meters tall.
#history
commenter_one
Not true!
1 like
Reply
More posts from sample_account"""


def test_platforms_are_recognized_by_host():
    assert platform("https://x.com/a/status/1") == "x"
    assert platform("https://mobile.twitter.com/a/status/1") == "x"
    assert platform("https://www.threads.com/@a/post/1") == "threads"
    assert platform("https://m.facebook.com/page/posts/1") == "facebook"
    assert platform("https://www.instagram.com/reel/1") == "instagram"
    assert platform("https://www.tiktok.com/@a/video/1") == "tiktok"
    assert platform("https://news.example/x.com") is None


def test_x_keeps_the_post_and_its_quote_but_not_counts_note_or_replies():
    text = post_text("https://x.com/sample_author/status/1", X_PAGE)
    assert "The bridge opened in 1932." in text
    assert "The bridge is the oldest in the city." in text
    assert "Sample Author@sample_author" in text
    for dropped in (
        "86.9K",
        "Views",
        "Readers added context",
        "A note from readers",
        "This reply",
        "Log inSign up",
        'on X: "',
    ):
        assert dropped not in text
    # The post appears once even though the page repeats it below the timestamp.
    assert text.count("The bridge opened in 1932.") == 1


def test_threads_keeps_only_the_post():
    text = post_text("https://www.threads.com/@sample.account/post/1", THREADS_PAGE)
    assert text == "sample.account\n\nThe museum reopens on Monday."


def test_facebook_keeps_the_post_and_drops_reactions_and_comments():
    text = post_text("https://www.facebook.com/page/posts/1", FACEBOOK_PAGE)
    assert text == "The library was founded in 1850.\n\nIt moved to its current building in 1901."


def test_instagram_keeps_the_caption_and_drops_comments():
    text = post_text("https://www.instagram.com/reel/1", INSTAGRAM_PAGE)
    assert "The tower is 300 meters tall." in text
    assert "Not true!" not in text
    assert "Never miss a post" not in text and "More posts from" not in text


@pytest.mark.parametrize(
    ("url", "page"),
    [
        (
            "https://www.facebook.com/page/posts/1",
            "Explore the things you love.\nLog into Facebook\nSign Up",
        ),
        (
            "https://www.tiktok.com/@a/video/1",
            "Dear Users,\nWe regret to inform you that we have discontinued operating TikTok "
            "in Hong Kong.",
        ),
    ],
)
def test_a_login_wall_or_notice_is_no_post(url, page):
    assert post_text(url, page) is None


def test_other_pages_and_unrecognized_layouts_are_left_unchanged():
    article = "Headline\n\n12\n\nThe article text."
    assert post_text("https://news.example/story", article) == article
    # Without the timestamp marker the X rule does not guess where the post ends.
    loose = "Sample Author@sample_author\n\nA post without a timestamp line."
    assert post_text("https://x.com/a/status/1", loose) == loose


def test_reader_reports_a_login_wall_as_unreadable_after_both_depths():
    depths = []

    def handler(request):
        depths.append(request.read())
        wall = "Explore the things you love.\n\nLog into Facebook"
        return httpx.Response(200, json={"results": [{"raw_content": wall}]})

    reader = TavilyLinkReader("key", transport=httpx.MockTransport(handler))
    with pytest.raises(LinkFailure) as error:
        reader.read("https://www.facebook.com/page/posts/1")
    assert error.value.code == "unreadable"
    assert len(depths) == 2


def test_reader_returns_the_cleaned_post_text():
    def handler(request):
        return httpx.Response(200, json={"results": [{"raw_content": X_PAGE, "title": "t"}]})

    page = TavilyLinkReader("key", transport=httpx.MockTransport(handler)).read(
        "https://x.com/sample_author/status/1"
    )
    assert "This reply" not in page.text and "86.9K" not in page.text
    assert not page.truncated


def test_avatars_are_not_taken_for_a_post_picture():
    assert profile_picture("https://pbs.twimg.com/profile_images/1/a_400x400.jpg")
    assert profile_picture("https://pbs.twimg.com/profile_banners/1/2")
    assert profile_picture("https://abs.twimg.com/emoji/v2/svg/1f447.svg")
    assert not profile_picture("https://pbs.twimg.com/media/ABC?format=webp&name=large")
    assert not profile_picture("https://news.example/profile_images/photo.jpg")
