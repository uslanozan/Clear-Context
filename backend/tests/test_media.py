from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from clear_context.domain.investigation import MediaAnalysis, ModelUsage
from clear_context.graph.nodes.analyze_media import analyze_media, compose_analyzed_text
from clear_context.main import create_app
from clear_context.providers.reverse_image import (
    ReverseImageFailure,
    SerpApiLensSearch,
    readable_matches,
    shrink_image,
)
from clear_context.services.media import MediaRejected, sniff, store, validate

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64


def test_types_come_from_file_signatures_not_names():
    assert sniff(PNG) == ("image", "image/png")
    assert sniff(JPEG) == ("image", "image/jpeg")
    assert sniff(MP4) == ("video", "video/mp4")
    assert sniff(b"<svg xmlns='http://www.w3.org/2000/svg'/>") is None
    with pytest.raises(MediaRejected, match="use JPEG"):
        validate([("photo.png", b"<html>not an image</html>")])
    with pytest.raises(MediaRejected, match="up to 4"):
        validate([("a.png", PNG)] * 5)


def test_storage_uses_content_hash_and_drops_client_paths(tmp_path):
    stored = store(tmp_path, "../../etc/photo.png", "image", "image/png", PNG)
    assert stored.filename == "photo.png"
    assert stored.storage_name.endswith(".png") and len(stored.storage_name) == 68
    assert (tmp_path / stored.storage_name).read_bytes() == PNG


def test_upload_flow_keeps_media_honest_in_preview_mode(settings):
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/investigations/upload",
            data={"text": "Protesters in Paris yesterday.", "research_mode": "fast"},
            files=[("files", ("post.png", PNG, "image/png"))],
        )
        assert response.status_code == 202, response.text
        investigation_id = response.json()["id"]
        assert response.json()["research_mode"] == "fast"
        report = client.get(f"/api/investigations/{investigation_id}/report").json()
        media = report["media"][0]
        assert media["filename"] == "post.png"
        assert media["analysis"]["status"] == "not_analyzed"
        assert media["origin"]["status"] == "not_checked"
        assert report["analyzed_text"] == "Protesters in Paris yesterday."
        steps = [
            s["name"] for s in client.get(f"/api/investigations/{investigation_id}/steps").json()
        ]
        assert steps[:3] == ["graph_started", "analyze_media", "extract_claims"]
        file = client.get(f"/api/media/{media['id']}")
        assert file.status_code == 200
        assert file.headers["content-type"] == "image/png"
        assert file.headers["x-content-type-options"] == "nosniff"
        assert file.content == PNG


@pytest.mark.parametrize(
    ("files", "data", "detail"),
    [
        ([("files", ("fake.png", b"GIF8 nope", "image/png"))], {"text": "x"}, "use JPEG"),
    ],
)
def test_upload_rejections_create_nothing(settings, files, data, detail):
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/investigations/upload", data=data, files=files)
        assert response.status_code == 422
        assert detail in response.json()["detail"]
        assert client.get("/api/investigations").json() == []


def test_text_read_from_an_image_is_labeled_and_used_for_extraction():
    class Analyzer:
        def analyze_image(self, data, mime_type, caption):
            usage = ModelUsage(task="media_analysis", model_id="muse-spark-1.3")
            return MediaAnalysis(
                status="analyzed",
                content_type="post_screenshot",
                visible_text="@news\nBREAKING: protests in France\n2 min",
                claim_text=["BREAKING: protests in France"],
                observations=["A crowd holds flags."],
                context_cues=["Signs are written in Hungarian."],
            ), usage

    class Search:
        name = "test"

        def search(self, data, mime_type):
            raise ReverseImageFailure("rate_limited", 429)

    state = {
        "investigation_id": uuid4(),
        "text": "",
        "media": [
            {
                "id": uuid4(),
                "kind": "image",
                "mime_type": "image/png",
                "filename": "post.png",
                "path": __file__,
            }
        ],
    }
    runtime = SimpleNamespace(
        context=SimpleNamespace(media_analyzer=Analyzer(), reverse_image=Search())
    )
    result = analyze_media(state, runtime)
    assert result["analyzed_text"] == "[Text read from image 1]\nBREAKING: protests in France"
    finding = result["media_findings"][0]
    assert finding.analysis.context_cues == ["Signs are written in Hungarian."]
    assert finding.origin.status == "failed"
    assert "rate_limited" in finding.origin.reason
    assert result["model_usage"][0].task == "media_analysis"


def test_analyzed_text_skips_images_without_statements():
    # Scene text such as a date stamp is transcribed but is not sent to claim extraction.
    stamp = SimpleNamespace(
        kind="image", analysis=MediaAnalysis(status="analyzed", visible_text="1996")
    )
    blank = SimpleNamespace(
        kind="image", analysis=MediaAnalysis(status="analyzed", claim_text=["  "])
    )
    assert compose_analyzed_text("Caption.", [stamp, blank]) == (
        "[Text the user sent with the attached media]\nCaption."
    )


def test_a_statement_wrapped_on_screen_reads_as_one_line():
    # The extension's screenshot of a post wrapped this sentence. A claim's quote must match the
    # composed text literally, so the wrap becomes a space; a break after a sentence stays.
    post = SimpleNamespace(
        kind="image",
        analysis=MediaAnalysis(
            status="analyzed",
            claim_text=[
                "USELESS & INTERESTING FACTS",
                "The Great Wall of China is the only man-made structure visible from\nspace.",
                "First line ends a sentence.\nSecond line stays apart.",
            ],
        ),
    )
    assert compose_analyzed_text("", [post]) == (
        "[Text read from image 1]\n"
        "USELESS & INTERESTING FACTS\n"
        "The Great Wall of China is the only man-made structure visible from space.\n"
        "First line ends a sentence.\nSecond line stays apart."
    )


def test_meta_media_request_sends_the_image_inline_and_reads_the_schema(settings, monkeypatch):
    from clear_context.core.settings import PROJECT_ROOT, ModelSelection
    from clear_context.providers import meta_media

    live = settings.model_copy(update={"app_mode": "meta", "allow_paid_api_calls": True})
    model = ModelSelection(alias="spark", api_model_id="muse-spark-1.3", training_use=False)
    analyzer = meta_media.MetaMediaAnalyzer(live, model, PROJECT_ROOT / "config/prompts.yaml")
    request = analyzer.build_request(PNG, "image/png", "A caption.")
    parts = request["messages"][1]["content"]
    assert parts[1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "visible_text" in str(request["response_format"]["json_schema"]["schema"])

    responses = [
        {
            "choices": [
                {
                    "message": {
                        "content": '{"content_type": "post_screenshot", '
                        '"visible_text": "Trains in Konya\\nJE-779", '
                        '"claim_text": ["Trains in Konya", "Trains in Ankara", "1996", "JE-779"], '
                        '"observations": ["A street."], "context_cues": [], '
                        '"caption_checks": [{"caption_detail": "Konya", '
                        '"assessment": "inconsistent", '
                        '"visible_basis": ["Signs use Chinese characters."]}]}'
                    }
                }
            ],
            "usage": {"prompt_tokens": 1400, "completion_tokens": 50},
        },
        {"choices": [{"message": {"content": "not json"}}]},
    ]

    class Provider:
        def __init__(self, settings):
            pass

        async def complete(self, payload, timeout):
            return responses.pop(0)

    monkeypatch.setattr(meta_media, "MetaStructuredProvider", Provider)
    analysis, usage = analyzer.analyze_image(PNG, "image/png", "")
    assert analysis.status == "analyzed" and analysis.observations == ["A street."]
    # Statements absent from the transcription are dropped, with a note.
    assert analysis.claim_text == ["Trains in Konya"]
    assert "did not match" in analysis.note
    assert analysis.caption_checks[0].assessment == "inconsistent"
    assert usage.input_tokens == 1400
    assert usage.prompt_version == "media_analysis_v2"
    failed, usage = analyzer.analyze_image(PNG, "image/png", "")
    assert failed.status == "failed" and usage is None


def lens_handler(calls, exact, visual=()):
    def handler(request):
        calls.append(request)
        if request.url.path == "/image":
            return httpx.Response(200, json={"image_id": "img-1"})
        kind = request.url.params["type"]
        if kind == "exact_matches":
            return httpx.Response(200, json={"exact_matches": list(exact)})
        return httpx.Response(200, json={"visual_matches": list(visual)})

    return handler


def test_serpapi_lens_orders_exact_matches_by_displayed_date():
    calls = []
    exact = [
        {
            "link": "https://check.example/a",
            "title": "Fact check",
            "source": "Check",
            "date": "Feb 24, 2025",
        },
        {
            "link": "https://forum.example/b",
            "title": "Same driver",
            "source": "Forum",
            "date": "Feb 12, 2025",
        },
        {"link": "https://blog.example/c", "title": "Undated", "source": "Blog"},
        {"link": "javascript:alert(1)"},
    ]
    search = SerpApiLensSearch(
        "serp-key", transport=httpx.MockTransport(lens_handler(calls, exact))
    )
    origin = search.search(PNG, "image/png")
    search.close()
    # Three exact matches are enough; no second, visual search is spent.
    assert [c.url.path for c in calls] == ["/image", "/search"]
    assert calls[1].url.params["image_id"] == "img-1"
    assert [m.source for m in origin.matches] == ["Forum", "Check", "Blog"]
    assert origin.matches[0].published_on.isoformat() == "2025-02-12"
    assert origin.matches[2].published_on is None


def test_serpapi_lens_adds_similar_images_when_exact_matches_are_scarce():
    calls = []
    visual = [
        {"link": "https://snopes.example/7-headed", "title": "Seven-headed snake?"},
        {"link": "https://check.example/a", "title": "Duplicate of exact"},
    ]
    exact = [{"link": "https://check.example/a", "title": "Fact check"}]
    search = SerpApiLensSearch(
        "serp-key", transport=httpx.MockTransport(lens_handler(calls, exact, visual))
    )
    origin = search.search(PNG, "image/png")
    search.close()
    assert [c.url.params.get("type") for c in calls[1:]] == ["exact_matches", "visual_matches"]
    assert [(m.page_url, m.match) for m in origin.matches] == [
        ("https://check.example/a", "full"),
        ("https://snopes.example/7-headed", "similar"),
    ]


def test_serpapi_lens_failures_keep_only_a_code():
    def handler(request):
        return httpx.Response(200, json={"error": "Invalid API key: serp-key"})

    search = SerpApiLensSearch("serp-key", transport=httpx.MockTransport(handler))
    with pytest.raises(ReverseImageFailure) as error:
        search.search(PNG, "image/png")
    search.close()
    assert error.value.code == "provider_error"
    assert "serp-key" not in str(error.value)


def test_large_images_are_shrunk_for_upload_and_unreadable_ones_fail():
    import io

    from PIL import Image

    noisy = Image.effect_noise((1800, 1800), 120).convert("RGB")
    buffer = io.BytesIO()
    noisy.save(buffer, format="PNG")
    assert buffer.tell() > 500_000
    small = shrink_image(buffer.getvalue(), 500_000)
    assert len(small) <= 500_000 and small[:3] == b"\xff\xd8\xff"
    assert shrink_image(PNG, 500_000) == PNG
    with pytest.raises(ReverseImageFailure, match="image_unreadable"):
        shrink_image(b"x" * 600_000, 500_000)


def test_redirects_and_social_feeds_are_not_read_as_sources():
    from clear_context.domain.investigation import ImageMatch, MediaOrigin

    origin = MediaOrigin(
        status="matches_found",
        matches=[
            ImageMatch(page_url=url, match="full")
            for url in (
                "https://www.google.com/goto?url=x",
                "https://www.instagram.com/p/1/",
                "https://www.reddit.com/r/a/",
                "https://check.example/a",
                "https://news.example/b",
            )
        ],
    )
    assert [m.page_url for m in readable_matches(origin, 2)] == [
        "https://www.reddit.com/r/a/",
        "https://check.example/a",
    ]


def test_serpapi_lens_keeps_earliest_matches_and_fact_checks_and_resolves_redirects():
    calls = []
    exact = [
        {
            "link": f"https://blog{i}.example/post",
            "title": f"Old post {i}",
            "date": f"Jan {i + 1}, 2012",
        }
        for i in range(5)
    ]
    exact.append(
        {
            "link": "https://www.google.com/goto?url=abc",
            "title": "Fotoğraf Konya'yı mı gösteriyor?",
            "source": "Doğruluk Payı",
            "date": "Feb 24, 2025",
        }
    )

    def handler(request):
        if request.url.host == "www.google.com":
            calls.append("redirect")
            return httpx.Response(302, headers={"location": "https://www.dogrulukpayi.com/a"})
        return lens_handler(calls, exact)(request)

    search = SerpApiLensSearch("serp-key", max_matches=3, transport=httpx.MockTransport(handler))
    origin = search.search(PNG, "image/png")
    search.close()
    # The two earliest posts plus the fact check, which is kept despite its later date.
    assert [m.page_url for m in origin.matches] == [
        "https://blog0.example/post",
        "https://blog1.example/post",
        "https://www.dogrulukpayi.com/a",
    ]
    assert calls.count("redirect") == 1
    # Likely fact checks are read first.
    assert readable_matches(origin, 1)[0].page_url == "https://www.dogrulukpayi.com/a"


def test_serpapi_lens_empty_results_and_redirect_pages():
    calls = []
    exact = [{"link": "https://www.google.com/goto?url=x", "title": "Old post"}]

    def handler(request):
        if request.url.host == "www.google.com":
            return httpx.Response(
                200, text='<H1>302 Moved</H1><A HREF="https://blog.example/a?x=1&amp;y=2">here</A>'
            )
        if request.url.params.get("type") == "visual_matches":
            return httpx.Response(
                200, json={"error": "Google Lens hasn't returned any results for this query."}
            )
        return lens_handler(calls, exact)(request)

    search = SerpApiLensSearch("serp-key", transport=httpx.MockTransport(handler))
    origin = search.search(PNG, "image/png")
    search.close()
    assert [m.page_url for m in origin.matches] == ["https://blog.example/a?x=1&y=2"]


def test_fact_check_image_search_uses_public_copies_and_keeps_the_publisher_rating():
    from clear_context.domain.investigation import ImageMatch, MediaOrigin
    from clear_context.providers.fact_check import GoogleFactCheckSearch

    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "claim": {
                            "text": "Konyalı kondüktör",
                            "claimReview": [
                                {
                                    "publisher": {
                                        "name": "Doğruluk Payı",
                                        "site": "dogrulukpayi.com",
                                    },
                                    "url": "https://www.dogrulukpayi.com/a",
                                    "title": "Fotoğraf Konya'yı mı gösteriyor?",
                                    "reviewDate": "2025-02-24T14:41:59Z",
                                    "textualRating": "Yanlış",
                                    "languageCode": "tr",
                                },
                                {"url": "javascript:alert(1)"},
                            ],
                        }
                    }
                ]
            },
        )

    origin = MediaOrigin(
        status="matches_found",
        matches=[
            ImageMatch(page_url="https://a.example", match="similar", image_url="https://x/s.jpg"),
            ImageMatch(page_url="https://b.example", match="full", image_url="https://b/c.jpg"),
            ImageMatch(
                page_url="https://c.example",
                match="full",
                image_url="https://encrypted-tbn0.gstatic.com/images?q=1",
            ),
        ],
    )
    search = GoogleFactCheckSearch("google-key", transport=httpx.MockTransport(handler))
    prior = search.lookup(origin)
    search.close()
    # Google-hosted copies are tried first; similar images are never used.
    assert seen[0].url.params["imageUri"] == "https://encrypted-tbn0.gstatic.com/images?q=1"
    assert seen[0].headers["x-goog-api-key"] == "google-key"
    assert "google-key" not in str(seen[0].url)
    assert prior.status == "found" and len(prior.reviews) == 1
    review = prior.reviews[0]
    assert (review.rating, review.site, review.review_date.isoformat()) == (
        "Yanlış",
        "dogrulukpayi.com",
        "2025-02-24",
    )


def test_fact_check_lookup_without_copies_or_after_errors():
    from clear_context.domain.investigation import ImageMatch, MediaOrigin
    from clear_context.providers.fact_check import GoogleFactCheckSearch

    search = GoogleFactCheckSearch(
        "key", transport=httpx.MockTransport(lambda request: httpx.Response(403))
    )
    assert search.lookup(MediaOrigin(status="no_matches")).status == "not_checked"
    origin = MediaOrigin(
        status="matches_found",
        matches=[
            ImageMatch(page_url="https://b.example", match="full", image_url="https://b/c.jpg")
        ],
    )
    failed = search.lookup(origin)
    search.close()
    assert failed.status == "failed" and "http_error" in failed.reason


def test_bing_adds_direct_dated_pages_using_a_public_copy_found_by_lens():
    calls = []
    exact = [
        {
            "link": "https://www.google.com/goto?url=x",
            "title": "Old post",
            "date": "Jul 5, 2011",
            "image": "https://encrypted-tbn0.gstatic.com/images?q=copy",
        }
    ] * 1 + [
        {"link": f"https://blog{i}.example/a", "title": f"Post {i}", "date": "Jan 1, 2020"}
        for i in range(3)
    ]

    def handler(request):
        if request.url.host == "www.google.com":
            return httpx.Response(200, text="<html>Verifying your request</html>" * 200)
        if request.url.params.get("engine") == "bing_reverse_image":
            calls.append(request.url.params["image_url"])
            return httpx.Response(
                200,
                json={
                    "pages_with_this_image": [
                        {
                            "title": "Police archives in Sydney (1930s and 40s)",
                            "source": "https://monovisions.example/sydney",
                            "date": "2015-08-15T15:46:00Z",
                            "original": "https://monovisions.example/a.jpg",
                        },
                        {"title": "No source"},
                    ]
                },
            )
        return lens_handler([], exact)(request)

    search = SerpApiLensSearch("serp-key", transport=httpx.MockTransport(handler))
    origin = search.search(PNG, "image/png")
    search.close()
    # The user's upload is not sent to Bing; the Google-hosted copy is.
    assert calls == ["https://encrypted-tbn0.gstatic.com/images?q=copy"]
    bing = [m for m in origin.matches if m.found_by == "bing"]
    assert [(m.page_url, m.source, m.published_on.isoformat()) for m in bing] == [
        ("https://monovisions.example/sydney", "monovisions.example", "2015-08-15")
    ]
    # Ordered by displayed date: the 2011 Lens match, then the 2015 Bing page.
    assert [m.found_by for m in origin.matches[:2]] == ["google_lens", "bing"]
    assert readable_matches(origin, 1)[0].page_url == "https://monovisions.example/sydney"


def test_bing_failure_keeps_lens_matches_with_a_note():
    exact = [{"link": "https://a.example/p", "image": "https://encrypted-tbn0.gstatic.com/c"}] * 3

    def handler(request):
        if request.url.params.get("engine") == "bing_reverse_image":
            return httpx.Response(500)
        return lens_handler([], exact)(request)

    search = SerpApiLensSearch("serp-key", transport=httpx.MockTransport(handler))
    origin = search.search(PNG, "image/png")
    search.close()
    assert origin.status == "matches_found" and len(origin.matches) == 1
    assert "Bing" in origin.reason


def test_fact_check_text_search_adds_reviews_matched_by_the_caption():
    from clear_context.domain.investigation import MediaOrigin
    from clear_context.providers.fact_check import GoogleFactCheckSearch

    seen = []

    def handler(request):
        seen.append(request.url.path)
        return httpx.Response(
            200,
            json={
                "claims": [
                    {
                        "text": "Domuz eti satışına izin verildi",
                        "claimReview": [
                            {
                                "url": "https://teyit.example/domuz",
                                "textualRating": "Yanlış",
                                "reviewDate": "2024-04-19T00:00:00Z",
                            }
                        ],
                    }
                ]
            },
        )

    search = GoogleFactCheckSearch("key", transport=httpx.MockTransport(handler))
    prior = search.lookup(MediaOrigin(status="no_matches"), "Domuz eti satışına izin verildi")
    search.close()
    # No public copy, so only the text endpoint is called.
    assert seen == ["/v1alpha1/claims:search"]
    assert prior.status == "found"
    assert prior.reviews[0].matched_by == "text"
