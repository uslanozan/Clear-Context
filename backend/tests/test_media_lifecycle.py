import av
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_retrieval import plan
from test_video import make_video

from clear_context.main import create_app
from clear_context.models import InvestigationRow
from clear_context.repositories.retrieval import RetrievalRepository
from clear_context.services.playable_video import browser_playable, copy_path

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64


def upload(client, name, data, mime, text="A claim to check."):
    response = client.post(
        "/api/investigations/upload",
        data={"text": text, "research_mode": "fast"},
        files=[("files", (name, data, mime))],
    )
    assert response.status_code == 202, response.text
    investigation_id = response.json()["id"]
    report = client.get(f"/api/investigations/{investigation_id}/report").json()
    return investigation_id, report["media"][0]["id"]


def test_unplayable_video_gets_a_webm_copy_once(settings, tmp_path):
    # MPEG-4 Part 2 plays sound without a picture in browsers.
    clip = make_video(tmp_path / "clip.mp4")
    assert not browser_playable(clip)
    with TestClient(create_app(settings)) as client:
        _, media_id = upload(client, "clip.mp4", clip.read_bytes(), "video/mp4")
        first = client.get(f"/api/media/{media_id}/playable")
        assert first.status_code == 200
        assert first.headers["content-type"] == "video/webm"
        copies = list(settings.media_dir.glob("*.playable.webm"))
        assert len(copies) == 1
        made_at = copies[0].stat().st_mtime_ns
        assert client.get(f"/api/media/{media_id}/playable").status_code == 200
        assert copies[0].stat().st_mtime_ns == made_at
        with av.open(str(copies[0])) as container:
            assert container.streams.video[0].codec_context.name == "vp9"
            assert container.streams.audio[0].codec_context.name == "opus"
        # The original upload is still served unchanged.
        assert client.get(f"/api/media/{media_id}").content == clip.read_bytes()


def test_playable_is_only_for_videos(settings):
    with TestClient(create_app(settings)) as client:
        _, media_id = upload(client, "post.png", PNG, "image/png")
        assert client.get(f"/api/media/{media_id}/playable").status_code == 404


def test_delete_removes_records_and_unshared_files(settings, tmp_path):
    clip = make_video(tmp_path / "clip.mp4", seconds=4, audio=False)
    with TestClient(create_app(settings)) as client:
        first, _ = upload(client, "post.png", PNG, "image/png")
        second, _ = upload(client, "copy.png", PNG, "image/png")
        third, video_id = upload(client, "clip.mp4", clip.read_bytes(), "video/mp4")
        client.get(f"/api/media/{video_id}/playable")
        stored = {path.name for path in settings.media_dir.iterdir()}
        workspace = client.app.state.research_workspace
        research = RetrievalRepository(workspace)
        research.register_plan(plan(first))
        research.register_plan(plan(f"{first}:batch1"))
        research.register_plan(plan(second))
        research.close()
        # A continuation of the first report keeps its own records.
        with client.app.state.repository.sessions.begin() as session:
            session.execute(
                update(InvestigationRow)
                .where(InvestigationRow.id == second)
                .values(parent_id=first, relation="continue")
            )

        assert client.delete(f"/api/investigations/{first}").status_code == 204
        assert client.get(f"/api/investigations/{first}").status_code == 404
        # The same image is still used by the second investigation.
        assert {path.name for path in settings.media_dir.iterdir()} == stored
        assert client.get(f"/api/investigations/{second}").json()["parent_id"] is None
        research = RetrievalRepository(workspace)
        assert research.overview(first)["needs"] == []
        assert research.overview(second)["needs"]
        research.close()

        assert client.delete(f"/api/investigations/{second}").status_code == 204
        assert client.delete(f"/api/investigations/{third}").status_code == 204
        assert list(settings.media_dir.iterdir()) == []
        assert client.get("/api/investigations").json() == []
        assert client.delete(f"/api/investigations/{first}").status_code == 404


def test_delete_waits_for_a_running_investigation(settings):
    with TestClient(create_app(settings)) as client:
        investigation_id, _ = upload(client, "post.png", PNG, "image/png")
        with client.app.state.repository.sessions.begin() as session:
            session.execute(
                update(InvestigationRow)
                .where(InvestigationRow.id == investigation_id)
                .values(status="running")
            )
        response = client.delete(f"/api/investigations/{investigation_id}")
        assert response.status_code == 409
        assert client.get(f"/api/investigations/{investigation_id}").status_code == 200


def test_copy_path_sits_next_to_the_upload(tmp_path):
    assert copy_path(tmp_path / "abc.mp4") == tmp_path / "abc.playable.webm"


def test_upload_prepares_the_copy_before_anyone_opens_the_report(settings, tmp_path):
    from clear_context.services import playable_video

    clip = make_video(tmp_path / "clip.mp4", seconds=3, audio=False)
    with TestClient(create_app(settings)) as client:
        upload(client, "clip.mp4", clip.read_bytes(), "video/mp4")
        # The preparer runs one job at a time; an empty job waits for the copy.
        playable_video._preparer.submit(lambda: None).result(timeout=60)
        assert len(list(settings.media_dir.glob("*.playable.webm"))) == 1


def test_copy_of_a_deleted_upload_is_not_kept(tmp_path, monkeypatch):
    from clear_context.services import playable_video

    clip = make_video(tmp_path / "clip.mp4", seconds=2, audio=False)
    real = playable_video._transcode

    def transcode_then_delete(source, target):
        real(source, target)
        source.unlink()

    monkeypatch.setattr(playable_video, "_transcode", transcode_then_delete)
    with pytest.raises(FileNotFoundError):
        playable_video.playable(clip)
    assert list(tmp_path.glob("*.webm")) == []
