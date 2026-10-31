from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from clear_context.graph.nodes.fetch_links import fetch_links
from clear_context.providers.link_reader import (
    LinkFailure,
    LinkPage,
    TavilyLinkReader,
    find_links,
    same_page,
)

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def real_jpeg(width: int, height: int) -> bytes:
    import io

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(buffer, format="JPEG")
    return buffer.getvalue()


PHOTO = real_jpeg(640, 480)
ICON = real_jpeg(96, 96)


def test_links_are_found_in_text_without_trailing_punctuation():
    text = (
        "Bu doğru mu? https://news.example/a/b?id=1). Ayrıca (https://other.example/x), "
        "tekrar https://news.example/a/b?id=1 ve ftp://files.example/y"
    )
    assert find_links(text) == ["https://news.example/a/b?id=1", "https://other.example/x"]
    assert find_links("no links here") == []
    assert len(find_links(" ".join(f"https://s{i}.example/" for i in range(5)))) == 3


def test_same_page_ignores_www_trailing_slash_and_tracking():
    assert same_page("https://www.news.example/a/?utm_source=x", "https://news.example/a")
    assert not same_page("https://news.example/a", "https://news.example/b")


def reader(handler, resolver=lambda host: "93.184.216.34"):
    return TavilyLinkReader("key", transport=httpx.MockTransport(handler), resolver=resolver)


def test_reader_returns_text_title_images_and_an_exact_page_date():
    def handler(request):
        if request.url.path == "/extract":
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "url": "https://news.example/a",
                            "title": "Headline",
                            "raw_content": "# Headline\n\n![](/main.jpg)\n\nBody text.",
                            "images": ["/main.jpg", "http://insecure.example/x.jpg"],
                        }
                    ]
                },
            )
        assert request.headers["authorization"] == "Bearer key"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://elsewhere.example/a",
                        "published_date": "Mon, 01 Jan 2024 00:00:00 GMT",
                    },
                    {
                        "url": "https://www.news.example/a/",
                        "published_date": "Wed, 24 Apr 2024 00:00:00 GMT",
                    },
                ]
            },
        )

    link_reader = reader(handler)
    page = link_reader.read("https://news.example/a")
    assert (page.title, page.text) == ("Headline", "Headline\n\nBody text.")
    assert page.images == ["https://news.example/main.jpg"]
    # Only the result for this exact page gives the date.
    assert link_reader.published_on(page) == date(2024, 4, 24)
    link_reader.close()


def test_unreadable_page_and_missing_date_are_reported_not_guessed():
    def handler(request):
        if request.url.path == "/extract":
            return httpx.Response(200, json={"results": [], "failed_results": [{"url": "x"}]})
        return httpx.Response(200, json={"results": [{"url": "https://other.example/"}]})

    link_reader = reader(handler)
    with pytest.raises(LinkFailure, match="unreadable"):
        link_reader.read("https://x.com/user/status/1")
    page = LinkPage(url="https://news.example/a", title="Title", text="t", truncated=False)
    assert link_reader.published_on(page) is None
    link_reader.close()


def test_image_download_connects_to_the_checked_address_and_rejects_private_hosts():
    calls = []

    def handler(request):
        # The request goes to the checked address; the host name travels in Host and SNI.
        calls.append(
            (str(request.url), request.headers["host"], request.extensions["sni_hostname"])
        )
        if request.headers["host"] == "redirect.example":
            return httpx.Response(302, headers={"location": "https://internal.example/x.jpg"})
        if request.url.path == "/page.html":
            return httpx.Response(200, content=b"<html></html>")
        return httpx.Response(200, content=JPEG)

    public = {"cdn.example": "93.184.216.34", "redirect.example": "2606:2800:220:1::248"}
    link_reader = reader(handler, resolver=public.get)
    assert link_reader.download_image("https://cdn.example/a.jpg?w=1") == ("image/jpeg", JPEG)
    assert calls[0] == ("https://93.184.216.34/a.jpg?w=1", "cdn.example", "cdn.example")
    for url, code in [
        ("http://cdn.example/a.jpg", "image_address_rejected"),
        ("https://localhost/a.jpg", "image_address_rejected"),
        # A redirect to a non-public host is checked again and refused.
        ("https://redirect.example/a.jpg", "image_address_rejected"),
        ("https://cdn.example/page.html", "image_type_rejected"),
    ]:
        with pytest.raises(LinkFailure, match=code):
            link_reader.download_image(url)
    assert any(url.startswith("https://[2606:2800:220:1::248]/") for url, _, _ in calls)
    assert not any("internal.example" in host for _, host, _ in calls)
    link_reader.close()


def test_public_address_refuses_hosts_with_any_private_address(monkeypatch):
    from clear_context.providers import link_reader as module

    answers = {
        "public.example": ["93.184.216.34"],
        "mixed.example": ["93.184.216.34", "10.0.0.5"],
        "loopback.example": ["127.0.0.1"],
    }
    monkeypatch.setattr(
        module.socket,
        "getaddrinfo",
        lambda host, *args, **kwargs: [(None, None, None, None, (a, 443)) for a in answers[host]],
    )
    assert module.public_address("public.example") == "93.184.216.34"
    assert module.public_address("mixed.example") is None
    assert module.public_address("loopback.example") is None


class Reader:
    def __init__(self, fail=()):
        self.fail = fail

    def read(self, url):
        if url in self.fail:
            raise LinkFailure("unreadable")
        return LinkPage(
            url=url,
            title="Bakanlık izin verdi",
            text="Tarım Bakanlığı domuz eti satışına izin verdi.",
            truncated=False,
            images=["https://cdn.example/icon.png", "https://cdn.example/a.jpg"],
        )

    def published_on(self, page):
        return date(2024, 4, 18)

    def download_image(self, url):
        # Pages often list an icon first; the post's picture comes after it.
        return "image/jpeg", ICON if "icon" in url else PHOTO


def run_node(text, link_reader, tmp_path):
    attached = []

    def attach(stored, url):
        attached.append((stored.storage_name, url))
        return str(uuid4())

    runtime = SimpleNamespace(
        context=SimpleNamespace(link_reader=link_reader, attach_media=attach, media_dir=tmp_path)
    )
    return fetch_links({"investigation_id": uuid4(), "text": text}, runtime), attached


def test_fetch_links_adds_page_text_and_image_and_reports_unreadable_links(tmp_path):
    text = "Doğru mu? https://news.example/a https://x.com/u/status/1"
    result, attached = run_node(text, Reader(fail={"https://x.com/u/status/1"}), tmp_path)
    assert result["analyzed_text"] == (
        f"{text}\n\n[Text read from link 1]\nTarım Bakanlığı domuz eti satışına izin verdi."
    )
    read, failed = result["link_findings"]
    assert (read.status, read.published_on, read.site) == (
        "read",
        date(2024, 4, 18),
        "news.example",
    )
    assert failed.status == "failed" and "screenshot" in failed.reason
    # The page image joins the image pipeline, compared with the page rather than the note.
    [image] = result["media"]
    assert image["source_url"] == "https://news.example/a"
    assert image["caption"].startswith("Bakanlık izin verdi")
    assert UUID(str(image["id"])) == read.media_ids[0]
    assert attached[0][1] == "https://news.example/a"
    # The 96 px icon was skipped; the post's picture was kept.
    assert len(attached) == 1
    assert (tmp_path / attached[0][0]).read_bytes() == PHOTO


def test_preview_mode_does_not_open_links(tmp_path):
    result, attached = run_node("https://news.example/a", None, tmp_path)
    assert result["link_findings"][0].status == "not_read"
    assert "analyzed_text" not in result and attached == []


def test_checked_page_is_not_read_as_its_own_evidence(monkeypatch, tmp_path):
    from test_investigation_research import PLANNED_NEED, TWO_COMPONENTS, run_research

    planner = []
    claim, report = run_research(
        monkeypatch,
        tmp_path,
        [PLANNED_NEED],
        TWO_COMPONENTS,
        planner_requests=planner,
        subject_urls=["https://example.org/bridge"],
        published_on=date(2024, 4, 18),
    )
    assert "https://example.org/bridge" not in {s.url for s in report.sources}
    import json

    context = json.loads(planner[0]["messages"][1]["content"])
    assert context["source_published_at"] == "2024-04-18"


def test_preview_report_lists_links_and_persists_them(settings):
    from fastapi.testclient import TestClient

    from clear_context.main import create_app

    with TestClient(create_app(settings)) as client:
        created = client.post(
            "/api/investigations", json={"text": "Is this true? https://news.example/a"}
        ).json()
        report = client.get(f"/api/investigations/{created['id']}/report").json()
        steps = [s["name"] for s in client.get(f"/api/investigations/{created['id']}/steps").json()]
    assert steps[:3] == ["graph_started", "fetch_links", "extract_claims"]
    [link] = report["links"]
    assert (link["url"], link["status"]) == ("https://news.example/a", "not_read")
    assert report["analyzed_text"] == "Is this true? https://news.example/a"
    with TestClient(create_app(settings)) as client:
        again = client.get(f"/api/investigations/{created['id']}/report").json()
    assert again["links"] == report["links"]


def test_reader_retries_once_with_advanced_extraction():
    depths = []

    def handler(request):
        import json

        depth = json.loads(request.content)["extract_depth"]
        depths.append(depth)
        if depth == "basic":
            return httpx.Response(200, json={"results": [], "failed_results": [{"url": "x"}]})
        return httpx.Response(
            200,
            json={"results": [{"url": "https://www.reddit.com/r/a/", "raw_content": "Post text"}]},
        )

    link_reader = reader(handler)
    assert link_reader.read("https://www.reddit.com/r/a/").text == "Post text"
    assert depths == ["basic", "advanced"]
    # A page that fails both is reported unreadable after exactly two attempts.
    depths.clear()
    failing = reader(
        lambda request: (
            depths.append(1)
            or httpx.Response(200, json={"results": [], "failed_results": [{"url": "x"}]})
        )
    )
    with pytest.raises(LinkFailure, match="unreadable"):
        failing.read("https://www.facebook.com/a")
    assert len(depths) == 2
    link_reader.close()
    failing.close()
