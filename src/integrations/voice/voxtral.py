"""Audio transcription through OpenRouter's dedicated STT endpoint."""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

import httpx

from src.core.config import settings
from src.llm.safety import PATH_VOICE_TRANSCRIPTION, policy_for_path

logger = logging.getLogger(__name__)

MAX_AUDIO_SIZE = 25 * 1024 * 1024

_SUPPORTED_FORMATS = frozenset(
    {"aac", "flac", "m4a", "mp3", "ogg", "wav", "webm"}
)
_MIME_FORMATS = {
    "audio/aac": "aac",
    "audio/flac": "flac",
    "audio/mp3": "mp3",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "audio/x-aac": "aac",
    "audio/x-flac": "flac",
    "audio/x-m4a": "m4a",
    "audio/x-wav": "wav",
    "application/ogg": "ogg",
    "video/webm": "webm",
}


@dataclass(frozen=True, slots=True)
class VoiceTranscriptionResult:
    text: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    total_tokens: int | None = None
    cost: float | None = None
    duration_seconds: float | None = None
    request_duration_seconds: float = 0.0
    generation_id: str | None = None


def _magic_audio_format(audio_bytes: bytes) -> str | None:
    if audio_bytes.startswith(b"fLaC"):
        return "flac"
    if audio_bytes.startswith(b"OggS"):
        return "ogg"
    if (
        len(audio_bytes) >= 12
        and audio_bytes.startswith(b"RIFF")
        and audio_bytes[8:12] == b"WAVE"
    ):
        return "wav"
    if audio_bytes.startswith(b"\x1aE\xdf\xa3"):
        return "webm"
    if len(audio_bytes) >= 12 and audio_bytes[4:8] == b"ftyp":
        return "m4a"
    if (
        len(audio_bytes) >= 2
        and audio_bytes[0] == 0xFF
        and audio_bytes[1] & 0xF6 == 0xF0
    ):
        return "aac"
    if audio_bytes.startswith(b"ID3") or (
        len(audio_bytes) >= 2
        and audio_bytes[0] == 0xFF
        and audio_bytes[1] & 0xE0 == 0xE0
    ):
        return "mp3"
    return None


def detect_audio_format(
    audio_bytes: bytes,
    *,
    mime_type: str | None,
) -> str:
    """Return a supported STT format, rejecting unknown or conflicting hints."""
    normalized_mime = (mime_type or "").split(";", 1)[0].strip().lower()
    mime_format = _MIME_FORMATS.get(normalized_mime)
    magic_format = _magic_audio_format(audio_bytes)

    if mime_format and magic_format and mime_format != magic_format:
        raise ValueError(
            f"Audio MIME format {mime_format} does not match file format {magic_format}"
        )
    detected = magic_format or mime_format
    if detected is None:
        raise ValueError("Unsupported audio format")
    return detected


def _usage_value(container: Any, key: str) -> Any:
    if container is None:
        return None
    if isinstance(container, Mapping):
        return container.get(key)
    value = getattr(container, key, None)
    if value is not None:
        return value
    model_extra = getattr(container, "model_extra", None)
    if isinstance(model_extra, Mapping):
        return model_extra.get(key)
    return None


def _usage_number(container: Any, *keys: str) -> int | float | None:
    for key in keys:
        value = _usage_value(container, key)
        if isinstance(value, int | float):
            return value
    return None


def _coerce_int(value: int | float | None) -> int | None:
    return None if value is None else int(value)


def _coerce_float(value: int | float | None) -> float | None:
    return None if value is None else float(value)


def _transcription_url() -> str:
    return f"{settings.openrouter_base_url.rstrip('/')}/audio/transcriptions"


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str | None = None,
    client: object = None,
) -> str:
    """Transcribe audio bytes and return only text for legacy callers."""
    result = await transcribe_audio_with_metadata(
        audio_bytes,
        audio_format=audio_format,
        client=client,
    )
    return result.text


async def transcribe_audio_with_metadata(
    audio_bytes: bytes,
    audio_format: str | None = None,
    client: object = None,
) -> VoiceTranscriptionResult:
    """Transcribe bytes through `/audio/transcriptions` without a text prompt."""
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise ValueError(
            f"Audio file too large: {len(audio_bytes)} bytes "
            f"(max {MAX_AUDIO_SIZE} bytes / {MAX_AUDIO_SIZE // 1024 // 1024} MB)"
        )
    if audio_format is None:
        raise ValueError("Audio format is required")
    normalized_format = audio_format.strip().lower()
    if normalized_format not in _SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported audio format: {audio_format}")

    if client is not None and callable(getattr(client, "post", None)):
        return await _transcribe_with_client(
            cast(httpx.AsyncClient, client),
            audio_bytes=audio_bytes,
            audio_format=normalized_format,
        )

    async with httpx.AsyncClient() as internal_client:
        return await _transcribe_with_client(
            internal_client,
            audio_bytes=audio_bytes,
            audio_format=normalized_format,
        )


async def _transcribe_with_client(
    client: httpx.AsyncClient,
    *,
    audio_bytes: bytes,
    audio_format: str,
) -> VoiceTranscriptionResult:
    policy = policy_for_path(PATH_VOICE_TRANSCRIPTION)
    request_payload = {
        "model": settings.voice_transcription_model,
        "input_audio": {
            "data": base64.b64encode(audio_bytes).decode("ascii"),
            "format": audio_format,
        },
    }
    start = time.monotonic()
    response = await client.post(
        _transcription_url(),
        headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
        json=request_payload,
        timeout=policy.timeout_seconds,
    )
    request_duration_seconds = time.monotonic() - start
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, Mapping):
        raise ValueError("Failed to parse transcription response")

    text = payload.get("text")
    if not isinstance(text, str):
        raise ValueError("Failed to parse transcription response")

    usage = payload.get("usage")
    tokens_in = _coerce_int(_usage_number(usage, "input_tokens", "prompt_tokens"))
    tokens_out = _coerce_int(
        _usage_number(usage, "output_tokens", "completion_tokens")
    )
    total_tokens = _coerce_int(_usage_number(usage, "total_tokens"))
    cost = _coerce_float(_usage_number(usage, "cost", "cost_usd"))
    duration_seconds = _coerce_float(_usage_number(usage, "seconds", "duration"))
    response_model = str(payload.get("model") or settings.voice_transcription_model)
    generation_id = response.headers.get("X-Generation-Id") or None

    logger.info(
        "Voice transcription complete: model=%s audio_size=%d format=%s "
        "request_duration_seconds=%.3f audio_duration_seconds=%s "
        "total_tokens=%s cost=%s generation_id=%s",
        response_model,
        len(audio_bytes),
        audio_format,
        request_duration_seconds,
        duration_seconds,
        total_tokens,
        cost,
        generation_id,
    )
    return VoiceTranscriptionResult(
        text=text.strip(),
        model=response_model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_tokens=total_tokens,
        cost=cost,
        duration_seconds=duration_seconds,
        request_duration_seconds=request_duration_seconds,
        generation_id=generation_id,
    )
