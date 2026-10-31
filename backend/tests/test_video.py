import io
import json
import math
import wave
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import av
import httpx
import pytest
from PIL import Image

from clear_context.domain.investigation import (
    ImageMatch,
    MediaAnalysis,
    MediaOrigin,
    SpeechTurn,
)
from clear_context.graph.nodes.analyze_media import analyze_media, compose_analyzed_text
from clear_context.providers.meta_media import (
    ScreenTextOutput,
    VideoDescription,
    to_video_analysis,
)
from clear_context.providers.meta_voice import MetaVoiceTranscriber, TranscriptionFailure
from clear_context.services import video
from clear_context.services import video_analysis as pipeline


def make_video(path: Path, seconds: int = 6, audio: bool = True) -> Path:
    """A small MP4: grey until 3 s, then a bright pattern; a 440 Hz tone as audio."""
    with av.open(str(path), "w", format="mp4") as container:
        stream = container.add_stream("mpeg4", rate=10)
        stream.width, stream.height, stream.pix_fmt = 160, 96, "yuv420p"
        sound = container.add_stream("aac", rate=16000) if audio else None
        for index in range(seconds * 10):
            colour = (90, 90, 90) if index < 30 else (230, 40, 40)
            image = Image.new("RGB", (160, 96), colour)
            if index >= 30:
                image.paste((20, 20, 200), (40, 20, 120, 76))
            frame = av.VideoFrame.from_image(image)
            frame.pts = index
            container.mux(stream.encode(frame))
        container.mux(stream.encode(None))
        if sound is not None:
            sound.time_base = Fraction(1, 16000)
            samples = 1024
            for block in range(seconds * 16000 // samples):
                tone = bytearray()
                for i in range(samples):
                    value = 0.3 * math.sin(2 * math.pi * 440 * (block * samples + i) / 16000)
                    tone += __import__("struct").pack("<f", value)
                frame = av.AudioFrame(format="flt", layout="mono", samples=samples)
                frame.planes[0].update(bytes(tone))
                frame.sample_rate, frame.pts = 16000, block * samples
                container.mux(sound.encode(frame))
            container.mux(sound.encode(None))
    return path


@pytest.fixture
def clip(tmp_path):
    return make_video(tmp_path / "clip.mp4")


def test_probe_audio_chunks_and_frames(clip, tmp_path):
    info = video.probe(clip)
    assert 5.5 <= info.duration_seconds <= 6.5 and info.has_audio
    chunks = video.audio_chunks(clip, chunk_seconds=2)
    assert [round(offset) for offset, _ in chunks][:3] == [0, 2, 4]
    with wave.open(io.BytesIO(chunks[0][1])) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        # A chunk ends with the audio frame that crosses its length.
        assert 32000 <= audio.getnframes() < 32000 + 2048
    # The largest visual change is at 3 s; frames near an avoided time are not picked.
    [(at, data)] = video.scene_frames(clip, 1)
    assert 2.9 <= at <= 3.6 and data.startswith(b"\xff\xd8")
    assert video.scene_frames(clip, 1, avoid=[3.0]) != [(at, data)]
    assert [round(at) for at, _ in video.frames_at(clip, [1, 4])] == [1, 4]
    assert video.probe(make_video(tmp_path / "silent.mp4", audio=False)).has_audio is False
    assert video.moment_seconds("01:05 - a crowd") == 65 and video.moment_seconds("soon") is None
    with pytest.raises(video.VideoUnreadable):
        (tmp_path / "bad.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42not a video")
        video.probe(tmp_path / "bad.mp4")


def settings_for_voice():
    from clear_context.core.settings import Settings

    return Settings(_env_file=None, app_mode="meta", allow_paid_api_calls=True, meta_api_key="k")


def test_voice_transcriber_sends_wav_and_drops_noise_turns():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "turns": [
                    {
                        "startMs": 1000,
                        "endMs": 4000,
                        "speaker": "A",
                        "transcript": "Bridge closed.",
                    },
                    # An internal marker in a turn of zero length, and an empty turn.
                    {
                        "startMs": 76000,
                        "endMs": 76000,
                        "speaker": None,
                        "transcript": "speaker_A|>",
                    },
                    {
                        "startMs": 5000,
                        "endMs": 9000,
                        "speaker": "A",
                        "transcript": " <|nospeech|> ",
                    },
                    # One character over twenty seconds: wind noise, not speech.
                    {"startMs": 27000, "endMs": 47000, "speaker": "A", "transcript": "就。"},
                ]
            },
        )

    transcriber = MetaVoiceTranscriber(settings_for_voice(), transport=httpx.MockTransport(handler))
    [turn] = transcriber.transcribe(b"RIFF....WAVE", offset=570)
    assert (turn.start, turn.end, turn.speaker, turn.text) == (571, 574, "A", "Bridge closed.")
    request = seen[0]
    assert request.headers["authorization"] == "Bearer k"
    assert request.url.path == "/v1/asr/transcribe" and request.url.params["sessionId"]
    body = request.content.decode("latin-1")
    assert '"mode": "DIARIZATION"' in body and '"audioEncoding": "WAV"' in body
    assert 'name="audio"; filename="audio.wav"' in body


def test_voice_transcriber_retries_a_dropped_connection_then_reports_failures():
    calls = []

    def flaky(request):
        calls.append(1)
        if len(calls) == 1:
            raise httpx.RemoteProtocolError("Server disconnected", request=request)
        return httpx.Response(200, json={"turns": []})

    transcriber = MetaVoiceTranscriber(settings_for_voice(), transport=httpx.MockTransport(flaky))
    transcriber.sleep = lambda seconds: None
    assert transcriber.transcribe(b"wav") == [] and len(calls) == 2
    for status, code in [(413, "audio_too_large"), (400, "http_400")]:
        failing = MetaVoiceTranscriber(
            settings_for_voice(),
            transport=httpx.MockTransport(lambda request, s=status: httpx.Response(s)),
        )
        with pytest.raises(TranscriptionFailure, match=code):
            failing.transcribe(b"wav")


def test_on_screen_statements_must_match_the_shown_text():
    description = VideoDescription(
        content_type="news_report",
        on_screen_text=[
            ScreenTextOutput(at="00:03", text="Flood closes the old bridge"),
            ScreenTextOutput(at="00:09", text="VOA"),
        ],
        claim_text=["Flood closes the old bridge", "The mayor resigned today", "VOA"],
        observations=["A flooded street"],
        context_cues=[],
        key_moments=["00:04 - flooded bridge"],
        caption_checks=[],
        speech_heard=True,
    )
    speech = [SpeechTurn(start=1, end=3, text="The bridge is closed.")]
    analysis = to_video_analysis(description, speech, 12.34)
    assert analysis.claim_text == ["Flood closes the old bridge"]
    assert [(t.at, t.text) for t in analysis.on_screen_text][0] == (
        3,
        "Flood closes the old bridge",
    )
    assert analysis.speech == speech and analysis.duration_seconds == 12.3
    assert "1 on-screen statement" in analysis.note
    # A few words the video model did not hear are noise; a longer transcript is kept.
    quiet = description.model_copy(update={"speech_heard": False})
    noise = [SpeechTurn(start=27, end=47, text="So")]
    assert to_video_analysis(quiet, noise, 50).speech == []
    assert "no speech was heard" in to_video_analysis(quiet, noise, 50).note
    long = [SpeechTurn(start=0, end=9, text="one two three four five six seven eight nine")]
    assert to_video_analysis(quiet, long, 50).speech == long


class Analyzer:
    def __init__(self, moments=(1.0, 1.2)):
        self.moments = list(moments)
        self.calls = []

    def analyze_video(self, data, caption, speech, duration):
        self.calls.append((caption, speech))
        return (
            MediaAnalysis(status="analyzed", content_type="video", speech=speech),
            self.moments,
            None,
        )


class Transcriber:
    model_id = "muse-voice-transcribe-1.0"

    def transcribe(self, audio, offset=0.0):
        return [SpeechTurn(start=offset + 0.5, end=offset + 2, speaker="A", text="It flooded.")]


def match(url, kind, day=None):
    from datetime import date

    return ImageMatch(page_url=url, match=kind, published_on=date(2018, 9, day) if day else None)


def test_pipeline_transcribes_reads_and_merges_frame_matches(clip, tmp_path, monkeypatch):
    monkeypatch.setattr(video, "MIN_FRAME_GAP_SECONDS", 1.5)
    origins = iter(
        [
            MediaOrigin(status="matches_found", matches=[match("https://b.example", "similar")]),
            MediaOrigin(
                status="matches_found",
                matches=[
                    match("https://a.example", "full", 16),
                    match("https://b.example", "full"),
                ],
            ),
        ]
    )
    searched = []

    def search(jpeg):
        searched.append(jpeg)
        return next(origins)

    analyzer = Analyzer()
    result = pipeline.analyze_video(clip, "Caption", analyzer, Transcriber(), search, tmp_path)
    # The transcript reaches the video model as context.
    assert analyzer.calls[0][1][0].text == "It flooded."
    # Moments closer than the minimum gap give one model frame; the scene frame is the change.
    assert [(f.chosen_by, round(f.at)) for f in result.frames] == [("model", 1), ("scene", 3)]
    assert all((tmp_path / f.storage_name).is_file() for f in result.frames)
    # The first frame's match is kept with its frame time; same-image matches come first.
    assert [(m.page_url, m.match, m.frame_at) for m in result.origin.matches] == [
        ("https://a.example", "full", result.frames[1].at),
        ("https://b.example", "similar", result.frames[0].at),
    ]
    assert [u.task for u in result.usage] == ["speech_transcription"]


def test_pipeline_limits_and_missing_providers(clip, tmp_path, monkeypatch):
    analyzer = Analyzer()
    monkeypatch.setattr(pipeline, "MAX_VIDEO_BYTES", 10)
    skipped = pipeline.analyze_video(clip, "", analyzer, Transcriber(), None, tmp_path)
    assert skipped.analysis.status == "not_analyzed" and "50 MB" in skipped.analysis.note
    assert analyzer.calls == []
    monkeypatch.setattr(pipeline, "MAX_VIDEO_BYTES", 50_000_000)
    plain = pipeline.analyze_video(clip, "", analyzer, None, None, tmp_path)
    assert "no transcription provider" in plain.analysis.note
    assert plain.origin.status == "not_checked" and plain.frames == []


def test_speech_and_on_screen_statements_join_the_analyzed_text():
    finding = SimpleNamespace(
        kind="video",
        analysis=MediaAnalysis(
            status="analyzed",
            claim_text=["Flood closes the old bridge"],
            speech=[SpeechTurn(start=65, end=72.4, text="The bridge is closed.")],
        ),
    )
    assert compose_analyzed_text("Is it true?", [finding]) == (
        "[Text the user sent with the attached media]\nIs it true?"
        "\n\n[Text read from video 1]\nFlood closes the old bridge"
        "\n\n[Speech in video 1, 1:05-1:12]\nThe bridge is closed."
    )


def test_node_searches_frames_and_the_report_serves_them(clip, tmp_path, settings):
    from fastapi.testclient import TestClient

    from clear_context.main import create_app

    class Search:
        name = "test"

        def search(self, data, mime_type):
            return MediaOrigin(status="no_matches", provider="test")

    runtime = SimpleNamespace(
        context=SimpleNamespace(
            media_analyzer=Analyzer(moments=[1.0]),
            transcriber=Transcriber(),
            reverse_image=Search(),
            fact_checks=None,
            media_dir=tmp_path,
        )
    )
    item = {
        "id": uuid4(),
        "kind": "video",
        "mime_type": "video/mp4",
        "filename": "clip.mp4",
        "path": str(clip),
    }
    result = analyze_media({"text": "", "media": [item]}, runtime)
    [finding] = result["media_findings"]
    assert len(finding.frames) == 2 and finding.origin.status == "no_matches"
    assert "[Speech in video 1, 0:00-0:02]\nIt flooded." in result["analyzed_text"]
    assert finding.prior_checks.status == "not_checked"

    # Preview mode accepts a video without text and serves only frames the report lists.
    media_settings = settings.model_copy(update={"media_dir": tmp_path / "media"})
    with TestClient(create_app(media_settings)) as client:
        created = client.post(
            "/api/investigations/upload",
            files=[("files", ("clip.mp4", clip.read_bytes(), "video/mp4"))],
        )
        assert created.status_code == 202
        report = client.get(created.headers["location"] + "/report").json()
        [media] = report["media"]
        assert media["analysis"]["status"] == "not_analyzed" and media["frames"] == []
        assert client.get(f"/api/media/{media['id']}/frames/0").status_code == 404
        assert json.dumps(report).count("Preview mode: videos are not sent to a model.") == 1


def test_report_keeps_frames_and_serves_them(clip, settings):
    from fastapi.testclient import TestClient

    from clear_context.main import create_app

    class Search:
        name = "test"

        def search(self, data, mime_type):
            return MediaOrigin(status="no_matches", provider="test")

        def close(self):
            pass

    with TestClient(create_app(settings)) as client:
        runtime = client.app.state.service.runtime
        runtime.media_analyzer = Analyzer(moments=[1.0])
        runtime.transcriber = Transcriber()
        runtime.reverse_image = Search()
        created = client.post(
            "/api/investigations/upload",
            files=[("files", ("clip.mp4", clip.read_bytes(), "video/mp4"))],
        )
        report = client.get(created.headers["location"] + "/report").json()
        [media] = report["media"]
        assert [frame["chosen_by"] for frame in media["frames"]] == ["model", "scene"]
        frame = client.get(f"/api/media/{media['id']}/frames/1")
        assert frame.status_code == 200 and frame.content.startswith(b"\xff\xd8")
        assert frame.headers["content-type"] == "image/jpeg"
        assert client.get(f"/api/media/{media['id']}/frames/2").status_code == 404
        assert media["analysis"]["speech"][0]["text"] == "It flooded."


def test_frames_skip_the_opening_and_closing_seconds(tmp_path, monkeypatch):
    long_clip = make_video(tmp_path / "long.mp4", seconds=20, audio=False)
    monkeypatch.setattr(video, "MIN_FRAME_GAP_SECONDS", 1.0)
    # A logo at 0:01 and a moment at 0:19 are inside the 3 s margins; 0:10 is kept.
    chosen = pipeline.choose_frames(long_clip, [1.0, 19.0, 10.0], 20.0)
    model = [round(at) for at, by, _ in chosen if by == "model"]
    assert model == [10]
    assert all(3 <= at <= 17 for at, _, _ in chosen)
    assert video.edge_seconds(6.0) == pytest.approx(0.9)


def test_social_page_dates_are_shown_but_not_used_as_publication_dates():
    from clear_context.providers.reverse_image import parse_lens_matches

    items = [
        {"link": "https://www.google.com/goto?url=x", "source": "Facebook", "date": "Oct 15, 2013"},
        {"link": "https://m.facebook.com/page", "date": "Aug 22, 2014"},
        {"link": "https://x.com/u/status/1", "date": "Mar 1, 2020"},
        {"link": "https://news.example/a", "source": "News", "date": "Sep 15, 2018"},
    ]
    matches = parse_lens_matches(items, "full")
    assert [m.published_on is None for m in matches] == [True, True, True, False]
    assert matches[0].date_text == "Oct 15, 2013"
