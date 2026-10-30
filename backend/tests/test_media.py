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
        ([("files", ("clip.mp4", MP4, "video/mp4"))], {}, "video analysis"),
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
                visible_text="BREAKING: protests in France",
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


def test_analyzed_text_skips_images_without_text():
    finding = SimpleNamespace(analysis=SimpleNamespace(visible_text="  "))
    assert compose_analyzed_text("Caption.", [finding]) == "Caption."


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
                        "content": '{"content_type": "photo", "visible_text": "", '
                        '"observations": ["A street."], "context_cues": []}'
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
    assert usage.input_tokens == 1400
    failed, usage = analyzer.analyze_image(PNG, "image/png", "")
    assert failed.status == "failed" and usage is None
