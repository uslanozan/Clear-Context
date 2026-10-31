"""Local video decoding: duration, audio for transcription and frames for image search."""

import io
import itertools
import re
import wave
from dataclasses import dataclass
from pathlib import Path

import av
from PIL import ImageChops, ImageStat

# Voice Transcribe accepts at most ten minutes per file; chunks stay below that.
AUDIO_CHUNK_SECONDS = 570
# Frames this close to another chosen frame show the same scene.
MIN_FRAME_GAP_SECONDS = 4.0
MOMENT = re.compile(r"^\s*(\d{1,2}):(\d{2})")


class VideoUnreadable(ValueError):
    pass


@dataclass(frozen=True)
class VideoInfo:
    duration_seconds: float
    has_audio: bool


def probe(path: Path) -> VideoInfo:
    try:
        with av.open(str(path)) as container:
            if not container.streams.video:
                raise VideoUnreadable("no_video_stream")
            duration = container.duration / av.time_base if container.duration else 0.0
            return VideoInfo(float(duration), bool(container.streams.audio))
    except av.FFmpegError as error:
        raise VideoUnreadable("undecodable") from error


def audio_chunks(path: Path, chunk_seconds: int = AUDIO_CHUNK_SECONDS) -> list[tuple[float, bytes]]:
    """The audio track as 16 kHz mono 16-bit WAV files of at most chunk_seconds each.

    Returns (offset in seconds, WAV bytes) pairs, as Voice Transcribe requires that format.
    """
    rate = 16000
    chunks, current, current_samples = [], [], 0
    resampler = av.AudioResampler(format="s16", layout="mono", rate=rate)

    def close_chunk():
        if current_samples:
            offset = sum(len(chunk[1]) for chunk in chunks) / 2 / rate if chunks else 0.0
            chunks.append((offset, b"".join(current)))

    try:
        with av.open(str(path)) as container:
            # None flushes the resampler after the last frame.
            for frame in itertools.chain(container.decode(audio=0), [None]):
                for resampled in resampler.resample(frame):
                    pcm = bytes(resampled.planes[0])[: resampled.samples * 2]
                    current.append(pcm)
                    current_samples += resampled.samples
                    if current_samples >= chunk_seconds * rate:
                        close_chunk()
                        current, current_samples = [], 0
    except av.FFmpegError as error:
        raise VideoUnreadable("audio_undecodable") from error
    close_chunk()
    return [(offset, wav(pcm, rate)) for offset, pcm in chunks]


def wav(pcm: bytes, rate: int) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm)
    return buffer.getvalue()


def moment_seconds(moment: str) -> float | None:
    """Seconds from a mm:ss prefix such as "00:42 - a flooded street"; None if absent."""
    match = MOMENT.match(moment)
    return int(match.group(1)) * 60 + int(match.group(2)) if match else None


def jpeg(image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def frames_at(path: Path, times: list[float]) -> list[tuple[float, bytes]]:
    """The first frame at or after each requested time, in order."""
    wanted = sorted(times)
    picked = []
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            for frame in container.decode(stream):
                if not wanted:
                    break
                at = float(frame.pts * stream.time_base) if frame.pts is not None else 0.0
                if at >= wanted[0]:
                    picked.append((at, jpeg(frame.to_image())))
                    while wanted and wanted[0] <= at:
                        wanted.pop(0)
    except av.FFmpegError as error:
        raise VideoUnreadable("frames_undecodable") from error
    return picked


def scene_frames(path: Path, count: int, avoid: list[float] = ()) -> list[tuple[float, bytes]]:
    """Frames that differ most from the frame sampled before them.

    Frames are sampled twice a second. The first and last second and near-black frames are
    skipped, since they are often title cards or fades; frames near `avoid` are not picked.
    """
    candidates, previous = [], None
    try:
        with av.open(str(path)) as container:
            stream = container.streams.video[0]
            duration = container.duration / av.time_base if container.duration else 0.0
            next_time = 1.0
            for frame in container.decode(stream):
                if frame.pts is None:
                    continue
                at = float(frame.pts * stream.time_base)
                if at < next_time or (duration and at > duration - 1):
                    continue
                next_time = at + 0.5
                image = frame.to_image()
                small = image.convert("L").resize((64, 36))
                if ImageStat.Stat(small).mean[0] < 25:
                    previous = small
                    continue
                if previous is not None:
                    change = ImageStat.Stat(ImageChops.difference(small, previous)).mean[0]
                    candidates.append((change, at, image))
                previous = small
    except av.FFmpegError as error:
        raise VideoUnreadable("frames_undecodable") from error
    picked: list[tuple[float, object]] = []
    taken = list(avoid)
    for _, at, image in sorted(candidates, key=lambda item: -item[0]):
        if len(picked) == count:
            break
        if all(abs(at - other) >= MIN_FRAME_GAP_SECONDS for other in taken):
            picked.append((at, image))
            taken.append(at)
    return sorted((at, jpeg(image)) for at, image in picked)
