"""Describe uploaded images with a Muse multimodal model: visible text, observations, cues."""

import asyncio
import base64
import json
from hashlib import sha256
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from clear_context.core.settings import ModelSelection, Settings
from clear_context.domain.investigation import (
    CaptionCheck,
    MediaAnalysis,
    ModelUsage,
    ScreenText,
    SpeechTurn,
)
from clear_context.providers.meta_structured import MetaStructuredProvider, ModelResponseFailure
from clear_context.services.video import moment_seconds

PROMPT_VERSION = "media_analysis_v2"
VIDEO_PROMPT_VERSION = "video_analysis_v2"
# A one-minute video took 25-75 s in testing; the general Meta timeout is shorter.
VIDEO_TIMEOUT_SECONDS = 240
# Frames sampled per second of video.
VIDEO_FPS = 1.0


class CaptionCheckOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    caption_detail: str = Field(min_length=1, max_length=300)
    assessment: Literal["consistent", "inconsistent", "cannot_tell"]
    visible_basis: list[str] = Field(max_length=6)


class MediaDescription(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content_type: Literal["photo", "post_screenshot", "text_screenshot", "graphic", "other"]
    visible_text: str = Field(max_length=20000)
    claim_text: list[str] = Field(max_length=12)
    observations: list[str] = Field(max_length=12)
    context_cues: list[str] = Field(max_length=12)
    caption_checks: list[CaptionCheckOutput] = Field(max_length=8)


class ScreenTextOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    at: str = Field(max_length=10)
    text: str = Field(min_length=1, max_length=2000)


class VideoDescription(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content_type: Literal["footage", "news_report", "speech", "screen_recording", "other"]
    on_screen_text: list[ScreenTextOutput] = Field(max_length=40)
    claim_text: list[str] = Field(max_length=12)
    observations: list[str] = Field(max_length=12)
    context_cues: list[str] = Field(max_length=12)
    key_moments: list[str] = Field(max_length=3)
    caption_checks: list[CaptionCheckOutput] = Field(max_length=8)


def clock(seconds: float) -> str:
    seconds = int(seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def is_statement(part: str) -> bool:
    """A statement has at least two words and some letters; a bare date or code is a detail."""
    return len(part.split()) >= 2 and any(ch.isalpha() for ch in part)


def to_analysis(description: MediaDescription) -> MediaAnalysis:
    """Keep only claim text copied verbatim from the transcription; drop the rest with a note.

    Bare dates, numbers and single words are dropped silently: the model sometimes marks
    a date stamp such as "1996" as a statement.
    """
    candidates = [part for part in description.claim_text if is_statement(part)]
    claim_text = [part for part in candidates if part in description.visible_text]
    dropped = len(candidates) - len(claim_text)
    return MediaAnalysis(
        status="analyzed",
        content_type=description.content_type,
        visible_text=description.visible_text,
        claim_text=claim_text,
        observations=description.observations,
        context_cues=description.context_cues,
        caption_checks=[
            CaptionCheck(**check.model_dump())
            for check in description.caption_checks
            if check.caption_detail.strip()
        ],
        note=(
            f"{dropped} statement part(s) did not match the transcription and were not used."
            if dropped
            else None
        ),
    )


def to_video_analysis(
    description: VideoDescription, speech: list[SpeechTurn], duration: float
) -> MediaAnalysis:
    """Keep on-screen statements copied verbatim from the on-screen text, as for images."""
    on_screen = [
        ScreenText(at=moment_seconds(item.at), text=item.text.strip())
        for item in description.on_screen_text
        if item.text.strip()
    ]
    shown = "\n".join(item.text for item in on_screen)
    candidates = [part for part in description.claim_text if is_statement(part)]
    claim_text = [part for part in candidates if part in shown]
    dropped = len(candidates) - len(claim_text)
    return MediaAnalysis(
        status="analyzed",
        content_type="video",
        visible_text=shown,
        claim_text=claim_text,
        observations=description.observations,
        context_cues=description.context_cues,
        caption_checks=[
            CaptionCheck(**check.model_dump())
            for check in description.caption_checks
            if check.caption_detail.strip()
        ],
        speech=speech,
        on_screen_text=on_screen,
        duration_seconds=round(duration, 1),
        note=(
            f"{dropped} on-screen statement(s) did not match the on-screen text and were not used."
            if dropped
            else None
        ),
    )


class MockMediaAnalyzer:
    """Preview mode makes no model calls, so nothing is claimed about the image."""

    def analyze_image(self, data: bytes, mime_type: str, caption: str):
        return MediaAnalysis(
            status="not_analyzed", note="Preview mode: images are not sent to a model."
        ), None

    def analyze_video(self, data: bytes, caption: str, speech, duration: float):
        return (
            MediaAnalysis(
                status="not_analyzed",
                content_type="video",
                note="Preview mode: videos are not sent to a model.",
            ),
            [],
            None,
        )


class MetaMediaAnalyzer:
    def __init__(self, settings: Settings, model: ModelSelection, prompts_path: Path):
        self.settings = settings
        self.model = model
        catalog = yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
        self.system = catalog["experiments"][PROMPT_VERSION]["system"]
        self.video_system = catalog["experiments"][VIDEO_PROMPT_VERSION]["system"]

    def build_request(self, data: bytes, mime_type: str, caption: str) -> dict:
        image_url = f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"
        context = {"caption": caption or None}
        return {
            "model": self.model.api_model_id,
            "messages": [
                {"role": "system", "content": self.system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": json.dumps(context, ensure_ascii=False)},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ],
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "media_description",
                    "strict": True,
                    "schema": MediaDescription.model_json_schema(),
                },
            },
            "reasoning_effort": "low",
            "max_completion_tokens": 8192,
            "store": False,
            "stream": False,
        }

    def analyze_image(self, data: bytes, mime_type: str, caption: str):
        request = self.build_request(data, mime_type, caption)
        provider = MetaStructuredProvider(self.settings)
        try:
            body = asyncio.run(provider.complete(request, self.settings.meta_timeout_seconds))
            description = MediaDescription.model_validate_json(
                body["choices"][0]["message"]["content"]
            )
        except (ModelResponseFailure, ValidationError, KeyError, IndexError, TypeError) as error:
            code = getattr(error, "code", "invalid_model_response")
            return MediaAnalysis(
                status="failed", note=f"Image analysis did not complete ({code})."
            ), None
        usage = body.get("usage") or {}
        record = ModelUsage(
            task="media_analysis",
            model_id=self.model.api_model_id,
            prompt_version=PROMPT_VERSION,
            prompt_sha256=sha256(self.system.encode("utf-8")).hexdigest(),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
        return to_analysis(description), record

    def build_video_request(self, data: bytes, caption: str, speech: list[SpeechTurn]) -> dict:
        context = {
            "caption": caption or None,
            "transcript": [
                {
                    "start": clock(turn.start),
                    "end": clock(turn.end),
                    "speaker": turn.speaker,
                    "text": turn.text,
                }
                for turn in speech
            ],
        }
        video_url = "data:video/mp4;base64," + base64.b64encode(data).decode("ascii")
        return {
            "model": self.model.api_model_id,
            "messages": [
                {"role": "system", "content": self.video_system},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": json.dumps(context, ensure_ascii=False)},
                        {"type": "video_url", "video_url": {"url": video_url, "fps": VIDEO_FPS}},
                    ],
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "video_description",
                    "strict": True,
                    "schema": VideoDescription.model_json_schema(),
                },
            },
            "reasoning_effort": "low",
            "max_completion_tokens": 16384,
            "store": False,
            "stream": False,
        }

    def analyze_video(self, data: bytes, caption: str, speech: list[SpeechTurn], duration: float):
        """Read a video with its transcript; returns (analysis, key moments, usage record)."""
        request = self.build_video_request(data, caption, speech)
        provider = MetaStructuredProvider(self.settings)
        try:
            body = asyncio.run(provider.complete(request, VIDEO_TIMEOUT_SECONDS))
            description = VideoDescription.model_validate_json(
                body["choices"][0]["message"]["content"]
            )
        except (ModelResponseFailure, ValidationError, KeyError, IndexError, TypeError) as error:
            code = getattr(error, "code", "invalid_model_response")
            failed = MediaAnalysis(
                status="failed",
                content_type="video",
                speech=speech,
                duration_seconds=round(duration, 1),
                note=f"Video analysis did not complete ({code}).",
            )
            return failed, [], None
        usage = body.get("usage") or {}
        record = ModelUsage(
            task="video_analysis",
            model_id=self.model.api_model_id,
            prompt_version=VIDEO_PROMPT_VERSION,
            prompt_sha256=sha256(self.video_system.encode("utf-8")).hexdigest(),
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )
        moments = [moment_seconds(moment) for moment in description.key_moments]
        moments = [m for m in moments if m is not None and 0 <= m <= duration]
        return to_video_analysis(description, speech, duration), moments, record
