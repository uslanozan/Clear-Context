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
from clear_context.domain.investigation import MediaAnalysis, ModelUsage
from clear_context.providers.meta_structured import MetaStructuredProvider, ModelResponseFailure

PROMPT_VERSION = "media_analysis_v1"


class MediaDescription(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    content_type: Literal["photo", "post_screenshot", "text_screenshot", "graphic", "other"]
    visible_text: str = Field(max_length=20000)
    observations: list[str] = Field(max_length=12)
    context_cues: list[str] = Field(max_length=12)


class MockMediaAnalyzer:
    """Preview mode makes no model calls, so nothing is claimed about the image."""

    def analyze_image(self, data: bytes, mime_type: str, caption: str):
        return MediaAnalysis(
            status="not_analyzed", note="Preview mode: images are not sent to a model."
        ), None


class MetaMediaAnalyzer:
    def __init__(self, settings: Settings, model: ModelSelection, prompts_path: Path):
        self.settings = settings
        self.model = model
        catalog = yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
        self.system = catalog["experiments"][PROMPT_VERSION]["system"]

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
        return MediaAnalysis(status="analyzed", **description.model_dump()), record
