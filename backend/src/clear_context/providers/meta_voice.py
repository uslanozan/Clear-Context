"""Speech to text with Muse Voice Transcribe (https://dev.meta.ai/docs/speech-to-text)."""

import json
import time
import uuid

import httpx

from clear_context.core.retry import retry_delay, should_retry_error, should_retry_status
from clear_context.core.settings import Settings
from clear_context.domain.investigation import SpeechTurn

TRANSCRIBE_URL = "https://api.meta.ai/v1/asr/transcribe"
MODEL_ID = "muse-voice-transcribe-1.0"
# Turns with fewer characters per second are background noise the model put words to; in
# testing, wind noise came back as one character over twenty seconds. Speech runs at 10-20.
MIN_CHARS_PER_SECOND = 0.5


class TranscriptionFailure(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def keep_turn(turn: SpeechTurn) -> bool:
    seconds = max(turn.end - turn.start, 0.001)
    return len(turn.text.strip()) / seconds >= MIN_CHARS_PER_SECOND


class MetaVoiceTranscriber:
    model_id = MODEL_ID

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport
        self.sleep = time.sleep

    def transcribe(self, audio: bytes, offset: float = 0.0) -> list[SpeechTurn]:
        """Transcribe one WAV file; turn times are shifted by offset seconds."""
        options = {"mode": "DIARIZATION", "model": MODEL_ID, "audioEncoding": "WAV"}
        attempt = 0
        while True:
            try:
                with httpx.Client(
                    transport=self.transport,
                    timeout=self.settings.meta_timeout_seconds,
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    response = client.post(
                        TRANSCRIBE_URL,
                        params={"sessionId": f"cc-{uuid.uuid4().hex[:16]}"},
                        headers={
                            "Authorization": "Bearer "
                            + self.settings.meta_api_key.get_secret_value()
                        },
                        files={
                            "request": (None, json.dumps(options), "application/json"),
                            "audio": ("audio.wav", audio, "audio/wav"),
                        },
                    )
            except httpx.HTTPError as error:
                if should_retry_error(error, attempt, paid=True):
                    self.sleep(retry_delay(attempt))
                    attempt += 1
                    continue
                raise TranscriptionFailure("transport_error") from None
            if should_retry_status(response.status_code, attempt):
                self.sleep(retry_delay(attempt, response))
                attempt += 1
                continue
            break
        if response.status_code == 413:
            raise TranscriptionFailure("audio_too_large")
        if not response.is_success:
            raise TranscriptionFailure(f"http_{response.status_code}")
        try:
            turns = response.json()["turns"]
            parsed = [
                SpeechTurn(
                    start=offset + turn["startMs"] / 1000,
                    end=offset + turn["endMs"] / 1000,
                    speaker=turn.get("speaker"),
                    text=turn["transcript"].strip(),
                )
                for turn in turns
                if str(turn.get("transcript", "")).strip()
            ]
        except (ValueError, KeyError, TypeError):
            raise TranscriptionFailure("invalid_response") from None
        return [turn for turn in parsed if keep_turn(turn)]
