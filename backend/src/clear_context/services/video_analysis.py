"""Check one video: speech, what is seen, and where its frames appeared online.

Speech comes from Voice Transcribe, which kept wording in testing where a video model changed
it. The video model then reads the frames with that transcript as context and names the moments
whose frames are searched, together with one frame chosen by visual change.
"""

from dataclasses import dataclass, field
from pathlib import Path

from clear_context.domain.investigation import (
    ImageMatch,
    MediaAnalysis,
    MediaOrigin,
    ModelUsage,
    SpeechTurn,
    VideoFrame,
)
from clear_context.providers.meta_voice import TranscriptionFailure
from clear_context.services import media as media_service
from clear_context.services import video

# Meta accepts up to 50 MB of inline video; larger files need its Files API (not used yet).
MAX_VIDEO_BYTES = 50_000_000
MAX_VIDEO_SECONDS = 600
MODEL_FRAMES = 2
SCENE_FRAMES = 1


@dataclass
class VideoResult:
    analysis: MediaAnalysis
    origin: MediaOrigin
    frames: list[VideoFrame] = field(default_factory=list)
    usage: list[ModelUsage] = field(default_factory=list)


def not_checked(reason: str) -> MediaOrigin:
    return MediaOrigin(status="not_checked", reason=reason)


def transcribe(transcriber, path: Path, has_audio: bool) -> tuple[list[SpeechTurn], str | None]:
    """Speech turns, and a note when speech could not be transcribed."""
    if not has_audio:
        return [], "The video has no audio track."
    if transcriber is None:
        return [], "Speech was not transcribed: no transcription provider is configured."
    turns = []
    try:
        for offset, chunk in video.audio_chunks(path):
            turns += transcriber.transcribe(chunk, offset)
    except (TranscriptionFailure, video.VideoUnreadable) as error:
        code = getattr(error, "code", None) or str(error)
        return turns, f"Speech transcription did not complete ({code})."
    return turns, None


def merge_origins(searched: list[tuple[float, MediaOrigin]]) -> MediaOrigin:
    """One origin for the video: matches of every frame, same image first, earliest first."""
    if not searched:
        return not_checked("No frames were searched.")
    matches: dict[str, ImageMatch] = {}
    for at, origin in searched:
        for match in origin.matches:
            if match.page_url not in matches:
                matches[match.page_url] = match.model_copy(update={"frame_at": round(at, 1)})
    ordered = sorted(
        matches.values(),
        key=lambda m: (m.match == "similar", m.published_on is None, m.published_on),
    )
    statuses = {origin.status for _, origin in searched}
    status = (
        "matches_found"
        if ordered
        else "failed"
        if statuses == {"failed"}
        else "not_checked"
        if statuses == {"not_checked"}
        else "no_matches"
    )
    reasons = sorted({origin.reason for _, origin in searched if origin.reason})
    return MediaOrigin(
        status=status,
        provider=next((origin.provider for _, origin in searched if origin.provider), None),
        reason=" ".join(reasons) or None,
        matches=ordered,
    )


def choose_frames(
    path: Path, moments: list[float], duration: float
) -> list[tuple[float, str, bytes]]:
    margin = video.edge_seconds(duration)
    inside = [at for at in moments if margin <= at <= duration - margin]
    picked = []
    for at, data in video.frames_at(path, inside[:MODEL_FRAMES]):
        if all(abs(at - other) >= video.MIN_FRAME_GAP_SECONDS for other, _, _ in picked):
            picked.append((at, "model", data))
    avoid = [at for at, _, _ in picked]
    picked += [(at, "scene", data) for at, data in video.scene_frames(path, SCENE_FRAMES, avoid)]
    return sorted(picked)


def analyze_video(
    path: Path,
    caption: str,
    analyzer,
    transcriber,
    search_frame,
    media_dir: Path | None,
) -> VideoResult:
    """search_frame(jpeg bytes) returns the MediaOrigin of one frame."""
    data_size = path.stat().st_size
    try:
        info = video.probe(path)
    except video.VideoUnreadable as error:
        return VideoResult(
            MediaAnalysis(
                status="failed",
                content_type="video",
                note=f"The video could not be read ({error}).",
            ),
            not_checked("The video could not be read."),
        )
    if data_size > MAX_VIDEO_BYTES or info.duration_seconds > MAX_VIDEO_SECONDS:
        return VideoResult(
            MediaAnalysis(
                status="not_analyzed",
                content_type="video",
                duration_seconds=round(info.duration_seconds, 1),
                note="Videos are analyzed up to 50 MB and 10 minutes; this one is larger.",
            ),
            not_checked("The video was not analyzed, so its frames were not searched."),
        )
    usage: list[ModelUsage] = []
    speech, speech_note = transcribe(transcriber, path, info.has_audio)
    if transcriber is not None and info.has_audio:
        usage.append(
            ModelUsage(
                task="speech_transcription",
                model_id=transcriber.model_id,
            )
        )
    analysis, moments, record = analyzer.analyze_video(
        path.read_bytes(), caption, speech, info.duration_seconds
    )
    if record:
        usage.append(record)
    if speech_note:
        analysis = analysis.model_copy(
            update={"note": " ".join(filter(None, [analysis.note, speech_note]))}
        )
    if analysis.status == "not_analyzed" or search_frame is None or media_dir is None:
        reason = (
            "Preview mode: video frames are not searched."
            if analysis.status == "not_analyzed"
            else "No reverse image search provider is configured."
        )
        return VideoResult(analysis, not_checked(reason), usage=usage)
    frames, searched = [], []
    try:
        chosen = choose_frames(path, moments, info.duration_seconds)
    except video.VideoUnreadable:
        chosen = []
    for at, chosen_by, jpeg in chosen:
        stored = media_service.store(media_dir, "frame.jpg", "image", "image/jpeg", jpeg)
        frames.append(
            VideoFrame(at=round(at, 1), chosen_by=chosen_by, storage_name=stored.storage_name)
        )
        searched.append((at, search_frame(jpeg)))
    return VideoResult(analysis, merge_origins(searched), frames, usage)
