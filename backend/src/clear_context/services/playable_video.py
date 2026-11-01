"""Browser-playable copies of uploaded videos.

Browsers decode H.264, VP8, VP9 and AV1 video. Other MP4 codecs, such as MPEG-4 Part 2, play
their sound without a picture, so those videos get a WebM copy (VP9 and Opus) made once with
the FFmpeg libraries bundled in PyAV. The original file is never changed or replaced.
"""

import threading
from fractions import Fraction
from pathlib import Path

import av

PLAYABLE_VIDEO = {"h264", "vp8", "vp9", "av1"}
PLAYABLE_AUDIO = {"aac", "mp3", "mp3float", "opus", "vorbis"}
MAX_HEIGHT = 720
MILLISECOND = Fraction(1, 1000)
OPUS_FRAME = 960

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def copy_path(original: Path) -> Path:
    return original.with_name(f"{original.stem}.playable.webm")


def browser_playable(original: Path) -> bool:
    with av.open(str(original)) as container:
        video = container.streams.video
        audio = container.streams.audio
        if not video or video[0].codec_context.name not in PLAYABLE_VIDEO:
            return False
        return not audio or audio[0].codec_context.name in PLAYABLE_AUDIO


def _lock(original: Path) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(original.name, threading.Lock())


def playable(original: Path) -> tuple[Path, str]:
    """The file to serve for playback and its media type; makes the copy on first use."""
    if browser_playable(original):
        return original, "video/mp4"
    target = copy_path(original)
    with _lock(original):
        if not target.is_file():
            partial = target.with_name(f"{target.name}.partial")
            try:
                _transcode(original, partial)
                partial.replace(target)
            finally:
                partial.unlink(missing_ok=True)
    return target, "video/webm"


def _even(value: float) -> int:
    return max(2, int(value) // 2 * 2)


def _transcode(source: Path, target: Path) -> None:
    with av.open(str(source)) as inp, av.open(str(target), "w", format="webm") as out:
        video_in = inp.streams.video[0]
        audio_in = inp.streams.audio[0] if inp.streams.audio else None
        height = min(video_in.codec_context.height, MAX_HEIGHT)
        width = _even(video_in.codec_context.width * height / video_in.codec_context.height)
        height = _even(height)
        rate = video_in.average_rate or Fraction(25)

        video_out = out.add_stream(
            "libvpx-vp9",
            rate=rate,
            options={"deadline": "realtime", "cpu-used": "8", "row-mt": "1", "crf": "34", "b": "0"},
        )
        video_out.width, video_out.height, video_out.pix_fmt = width, height, "yuv420p"
        video_out.time_base = MILLISECOND

        audio_out = resampler = fifo = None
        if audio_in is not None:
            audio_out = out.add_stream("libopus", rate=48000, layout="stereo")
            resampler = av.AudioResampler(format="s16", layout="stereo", rate=48000)
            fifo = av.AudioFifo()

        last_pts = -1
        audio_samples = 0
        streams = [video_in] + ([audio_in] if audio_in is not None else [])
        for frame in inp.decode(*streams):
            if isinstance(frame, av.VideoFrame):
                if frame.time is None:
                    continue
                pts = int(frame.time * 1000)
                # Variable frame rates can repeat a millisecond; the encoder needs increasing pts.
                if pts <= last_pts:
                    continue
                last_pts = pts
                scaled = frame.reformat(width=width, height=height, format="yuv420p")
                scaled.pts, scaled.time_base = pts, MILLISECOND
                out.mux(video_out.encode(scaled))
            elif audio_out is not None:
                for resampled in resampler.resample(frame):
                    # The fifo checks continuity; output audio is retimed by sample count.
                    resampled.pts = None
                    fifo.write(resampled)
                for chunk in fifo.read_many(OPUS_FRAME):
                    chunk.pts, chunk.time_base = audio_samples, Fraction(1, 48000)
                    audio_samples += chunk.samples
                    out.mux(audio_out.encode(chunk))
        out.mux(video_out.encode(None))
        if audio_out is not None:
            out.mux(audio_out.encode(None))
