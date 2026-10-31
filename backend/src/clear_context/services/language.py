"""Detect the language of the user's input for system-written report text.

langdetect answers most inputs locally. Short or low-confidence text goes to one minimal
model call; any failure there keeps the local guess, so detection never fails a report.
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from langdetect import DetectorFactory, LangDetectException, detect_langs

from clear_context.domain.investigation import ModelUsage
from clear_context.providers.meta_structured import ModelResponseFailure

# Deterministic results for the same text.
DetectorFactory.seed = 0

PROMPT_VERSION = "language_detection_v1"
LANGUAGE_CODE = re.compile(r"^[a-z]{2}$")
LETTERS = re.compile(r"[^\W\d_]", re.UNICODE)
# Short texts get confidently wrong local guesses ("ok" -> Slovak).
MIN_LETTERS = 20
MIN_CONFIDENCE = 0.90


@dataclass(frozen=True)
class LanguageDecision:
    code: str | None
    confidence: float
    method: str  # langdetect, model or unresolved
    usage: ModelUsage | None = None


def detect_locally(text: str) -> tuple[str | None, float]:
    try:
        best = detect_langs(text)[0]
    except (LangDetectException, IndexError):
        return None, 0.0
    # langdetect reports regional Chinese variants as zh-cn / zh-tw.
    return best.lang.split("-")[0], best.prob


def needs_model(text: str, confidence: float) -> bool:
    return len(LETTERS.findall(text)) < MIN_LETTERS or confidence < MIN_CONFIDENCE


def build_request(text: str, model: str, prompts_path: Path) -> dict:
    catalog = yaml.safe_load(prompts_path.read_text(encoding="utf-8-sig"))
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": catalog["experiments"][PROMPT_VERSION]["system"]},
            {"role": "user", "content": json.dumps({"text": text[:2000]}, ensure_ascii=False)},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "language_detection",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {"language": {"type": "string"}},
                    "required": ["language"],
                    "additionalProperties": False,
                },
            },
        },
        "reasoning_effort": "minimal",
        "max_completion_tokens": 256,
        "store": False,
        "stream": False,
    }


def parse_response(body: dict) -> str | None:
    try:
        value = json.loads(body["choices"][0]["message"]["content"])["language"]
    except (KeyError, IndexError, TypeError, ValueError):
        return None
    code = value.strip().lower() if isinstance(value, str) else ""
    return code if LANGUAGE_CODE.match(code) else None


async def detect_language(text: str, provider=None, model: str = "", prompts_path=None):
    """Return the input language; uses the model only when the local guess is weak."""
    code, confidence = detect_locally(text)
    if not needs_model(text, confidence) or provider is None:
        return LanguageDecision(code, confidence, "langdetect" if code else "unresolved")
    try:
        body = await provider.complete(build_request(text, model, prompts_path), 30)
    except (ModelResponseFailure, OSError, ValueError):
        return LanguageDecision(code, confidence, "langdetect" if code else "unresolved")
    if not isinstance(body, dict):
        return LanguageDecision(code, confidence, "langdetect" if code else "unresolved")
    usage = body.get("usage") or {}
    record = ModelUsage(
        task="language_detection",
        model_id=model,
        prompt_version=PROMPT_VERSION,
        input_tokens=usage.get("prompt_tokens"),
        output_tokens=usage.get("completion_tokens"),
    )
    answer = parse_response(body)
    if answer is None:
        # A broken answer keeps the local guess; the call is still recorded.
        return LanguageDecision(code, confidence, "langdetect" if code else "unresolved", record)
    return LanguageDecision(answer, 1.0, "model", record)
