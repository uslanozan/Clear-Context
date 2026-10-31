"""Video experiment v1: Muse video reading, Voice Transcribe and frame reverse image search.

Reads local MP4 cases from evals/corpus/local/video/ and writes one JSON record per case and
method to docs/local/experiments/video-v1/results/. Each record keeps the outgoing request
(video and audio data replaced by their size and SHA-256), the raw response, usage and time.
Makes paid calls; run only with an agreed budget.
"""

import argparse
import asyncio
import base64
import hashlib
import io
import json
import time
import uuid
from pathlib import Path

import av
import httpx
import yaml
from clear_context.core.settings import PROJECT_ROOT, Settings
from clear_context.providers.fact_check import build_fact_check_search
from clear_context.providers.meta_structured import (
    MetaStructuredProvider,
    ModelResponseFailure,
)
from clear_context.providers.reverse_image import build_reverse_image_search
from PIL import ImageChops, ImageStat

CORPUS = PROJECT_ROOT / "evals/corpus/local/video"
RESULTS = PROJECT_ROOT / "docs/local/experiments/video-v1/results"
PROMPT = "video_analysis_v1"
TRANSCRIBE_URL = "https://api.meta.ai/v1/asr/transcribe"

# Manually authored captions; v2 has none so that claims come only from the speech.
CAPTIONS = {
    "v1_imamoglu_2019": "İmamoğlu dün akşam seçim zaferini kutladı, işte konuşması",
    "v2_venezuela_2021": "",
    "v3_typhoon_2018": "Dün İzmir'i vuran fırtınada evlerin çatıları uçtu",
    "v4_harvey_2017": "Texas'ta kasırga sonrası sel: Vali 'dramatik sel' uyarısı yaptı",
}

SPEECH = {
    "type": "object",
    "additionalProperties": False,
    "required": ["start", "end", "speaker", "text"],
    "properties": {
        "start": {"type": "string"},
        "end": {"type": "string"},
        "speaker": {"type": "string"},
        "text": {"type": "string"},
    },
}
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "content_type",
        "speech",
        "on_screen_text",
        "claim_text",
        "observations",
        "context_cues",
        "key_moments",
        "caption_checks",
    ],
    "properties": {
        "content_type": {
            "type": "string",
            "enum": ["footage", "news_report", "speech", "screen_recording", "other"],
        },
        "speech": {"type": "array", "items": SPEECH},
        "on_screen_text": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["at", "text"],
                "properties": {"at": {"type": "string"}, "text": {"type": "string"}},
            },
        },
        "claim_text": {"type": "array", "items": {"type": "string"}},
        "observations": {"type": "array", "items": {"type": "string"}},
        "context_cues": {"type": "array", "items": {"type": "string"}},
        "key_moments": {"type": "array", "items": {"type": "string"}},
        "caption_checks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["caption_detail", "assessment", "visible_basis"],
                "properties": {
                    "caption_detail": {"type": "string"},
                    "assessment": {
                        "type": "string",
                        "enum": ["consistent", "inconsistent", "cannot_tell"],
                    },
                    "visible_basis": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    },
}


def digest(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(case: str, method: str, record: dict) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = RESULTS / f"{case}.{method}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(case, method, record.get("status"), record.get("seconds"))


def muse(settings: Settings, case: str, data: bytes, model: str, fps: float) -> None:
    system = yaml.safe_load(
        (PROJECT_ROOT / "config/prompts.yaml").read_text(encoding="utf-8-sig")
    )["experiments"][PROMPT]["system"]
    context = json.dumps({"caption": CAPTIONS[case] or None}, ensure_ascii=False)
    video_url = "data:video/mp4;base64," + base64.b64encode(data).decode("ascii")
    request = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": context},
                    {"type": "video_url", "video_url": {"url": video_url, "fps": fps}},
                ],
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "video_description",
                "strict": True,
                "schema": SCHEMA,
            },
        },
        "reasoning_effort": "low",
        "max_completion_tokens": 16384,
        "store": False,
        "stream": False,
    }
    trace = json.loads(json.dumps(request))
    trace["messages"][1]["content"][1]["video_url"]["url"] = digest(data)
    record = {"method": f"muse:{model}", "prompt": PROMPT, "fps": fps, "request": trace}
    provider = MetaStructuredProvider(settings)
    started = time.monotonic()
    try:
        body = asyncio.run(provider.complete(request, 240))
        record.update(status="ok", response=body, usage=body.get("usage"))
        try:
            record["parsed"] = json.loads(body["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            record["parse_error"] = type(error).__name__
    except ModelResponseFailure as error:
        cause = error.__cause__
        record.update(
            status="failed",
            error=error.code,
            http_status=error.status_code,
            cause=f"{type(cause).__name__}: {str(cause)[:300]}" if cause else None,
        )
    record["seconds"] = round(time.monotonic() - started, 1)
    record["retries"] = provider.retries
    save(case, f"muse_{model.replace('.', '_')}", record)


def wav_16k_mono(path: Path) -> bytes:
    """Decode the audio track to 16 kHz mono 16-bit PCM WAV, as Voice Transcribe requires."""
    out = io.BytesIO()
    with av.open(str(path)) as source, av.open(out, "w", format="wav") as sink:
        stream = sink.add_stream("pcm_s16le", rate=16000, layout="mono")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
        for frame in source.decode(audio=0):
            for resampled in resampler.resample(frame):
                for packet in stream.encode(resampled):
                    sink.mux(packet)
        for resampled in resampler.resample(None):
            for packet in stream.encode(resampled):
                sink.mux(packet)
        for packet in stream.encode(None):
            sink.mux(packet)
    return out.getvalue()


def transcribe(settings: Settings, case: str, path: Path) -> None:
    audio = wav_16k_mono(path)
    options = {
        "mode": "DIARIZATION",
        "model": "muse-voice-transcribe-1.0",
        "audioEncoding": "WAV",
    }
    record = {
        "method": "voice_transcribe",
        "request": {"request": options, "audio": digest(audio)},
    }
    started = time.monotonic()
    response = httpx.post(
        TRANSCRIBE_URL,
        params={"sessionId": f"cc-video-v1-{uuid.uuid4().hex[:12]}"},
        headers={"Authorization": "Bearer " + settings.meta_api_key.get_secret_value()},
        files={
            "request": (None, json.dumps(options), "application/json"),
            "audio": ("audio.wav", audio, "audio/wav"),
        },
        timeout=180,
        follow_redirects=False,
        trust_env=False,
    )
    record["seconds"] = round(time.monotonic() - started, 1)
    record["http_status"] = response.status_code
    try:
        record["response"] = response.json()
        record["status"] = "ok" if response.is_success else "failed"
    except ValueError:
        record.update(status="failed", response_text=response.text[:500])
    save(case, "voice_transcribe", record)


def distinct_frames(path: Path, count: int) -> list[tuple[float, bytes]]:
    """Pick frames that differ most from the previous sampled frame, at least 5 s apart.

    Frames are sampled twice a second; the first and last second and near-black frames are
    skipped, since they are often title cards or fades.
    """
    candidates = []
    previous = None
    with av.open(str(path)) as source:
        stream = source.streams.video[0]
        duration = float(source.duration / av.time_base)
        next_time = 1.0
        for frame in source.decode(stream):
            at = float(frame.pts * stream.time_base)
            if at < next_time or at > duration - 1:
                continue
            next_time = at + 0.5
            image = frame.to_image()
            small = image.convert("L").resize((64, 36))
            if ImageStat.Stat(small).mean[0] < 25:
                continue
            # The first sampled frame has nothing to differ from; it is not preferred.
            change = (
                0
                if previous is None
                else ImageStat.Stat(ImageChops.difference(small, previous)).mean[0]
            )
            previous = small
            candidates.append((change, at, image))
    picked = []
    for change, at, image in sorted(candidates, key=lambda item: -item[0]):
        if all(abs(at - other) >= 5 for other, _ in picked):
            buffer = io.BytesIO()
            image.convert("RGB").save(buffer, format="JPEG", quality=90)
            picked.append((at, buffer.getvalue()))
        if len(picked) == count:
            break
    return sorted(picked)


def model_frames(case: str, path: Path, count: int) -> list[tuple[float, bytes]]:
    """Frames at the key moments Muse Spark 1.3 named for this case (mm:ss prefixes)."""
    record = json.loads(
        (RESULTS / f"{case}.muse_muse-spark-1_3.json").read_text(encoding="utf-8")
    )
    wanted = []
    for moment in record["parsed"]["key_moments"][:count]:
        minutes, seconds = moment.strip()[:5].split(":")
        wanted.append(int(minutes) * 60 + int(seconds))
    picked = []
    with av.open(str(path)) as source:
        stream = source.streams.video[0]
        for frame in source.decode(stream):
            at = float(frame.pts * stream.time_base)
            if wanted and at >= wanted[0]:
                buffer = io.BytesIO()
                frame.to_image().convert("RGB").save(buffer, format="JPEG", quality=90)
                picked.append((at, buffer.getvalue()))
                wanted.pop(0)
    return picked


def frames(settings: Settings, case: str, path: Path, count: int, source: str) -> None:
    lens = build_reverse_image_search(settings)
    fact_checks = build_fact_check_search(settings)
    frames_dir = RESULTS / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    record = {"method": f"frames_{source}_lens_factcheck", "frames": []}
    started = time.monotonic()
    try:
        chosen = (
            distinct_frames(path, count)
            if source == "scene"
            else model_frames(case, path, count)
        )
        for at, jpeg in chosen:
            name = f"{case}_{source}_{at:05.1f}s.jpg"
            (frames_dir / name).write_bytes(jpeg)
            origin = lens.search(jpeg, "image/jpeg")
            prior = fact_checks.lookup(origin, CAPTIONS[case]) if fact_checks else None
            record["frames"].append(
                {
                    "at_seconds": round(at, 1),
                    "file": name,
                    "origin": origin.model_dump(mode="json"),
                    "prior_checks": prior.model_dump(mode="json") if prior else None,
                }
            )
        record["status"] = "ok"
    finally:
        lens.close()
        if fact_checks:
            fact_checks.close()
    record["seconds"] = round(time.monotonic() - started, 1)
    save(case, f"frames_{source}", record)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("method", choices=["muse", "transcribe", "frames"])
    parser.add_argument("--cases", nargs="+", default=sorted(CAPTIONS))
    parser.add_argument("--model", default="muse-spark-1.3")
    parser.add_argument("--fps", type=float, default=1.0)
    parser.add_argument("--frames", type=int, default=2)
    parser.add_argument("--source", choices=["scene", "model"], default="scene")
    args = parser.parse_args()
    settings = Settings()
    for case in args.cases:
        path = CORPUS / f"{case}.mp4"
        if args.method == "muse":
            muse(settings, case, path.read_bytes(), args.model, args.fps)
        elif args.method == "transcribe":
            transcribe(settings, case, path)
        else:
            frames(settings, case, path, args.frames, args.source)


if __name__ == "__main__":
    main()
