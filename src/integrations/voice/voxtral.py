"""Audio transcription via OpenRouter API (OpenAI SDK).

Uses `openai/gpt-audio-mini` to transcribe audio messages
(English, Arabic, Russian, and 100+ other languages).

NOTE: Uses the OpenAI Python SDK (`AsyncOpenAI`) pointed at OpenRouter,
matching the proven pattern from igor-bot.  Raw httpx was previously used
but gpt-audio-mini silently ignored the `input_audio` block.
"""

from __future__ import annotations

import base64
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from openai import AsyncOpenAI

from src.core.config import settings
from src.llm.safety import PATH_VOICE_TRANSCRIPTION, policy_for_path

logger = logging.getLogger(__name__)

# Prompt instructs the model to return raw transcription only
_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio exactly as spoken in its original language. "
    "Return ONLY the transcription text, nothing else. "
    "Do not add any commentary, formatting, or markdown."
)

# Maximum audio file size (25 MB) to prevent DoS via large files
MAX_AUDIO_SIZE = 25 * 1024 * 1024

# Lazy-initialized client (created on first call)
_client: AsyncOpenAI | None = None


@dataclass(frozen=True, slots=True)
class VoiceTranscriptionResult:
    text: str
    model: str
    tokens_in: int | None = None
    tokens_out: int | None = None
    total_tokens: int | None = None
    cost: float | None = None


def _get_client() -> AsyncOpenAI:
    """Get or create the OpenAI SDK client pointed at OpenRouter."""
    global _client  # noqa: PLW0603
    if _client is None:
        policy = policy_for_path(PATH_VOICE_TRANSCRIPTION)
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=policy.timeout_seconds,
            max_retries=0,
        )
    return _client


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
    if value is None:
        return None
    return int(value)


def _coerce_float(value: int | float | None) -> float | None:
    if value is None:
        return None
    return float(value)


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "mp3",
    client: object = None,  # kept for backward compat, ignored
) -> str:
    """Transcribe audio bytes and return only the text for legacy callers."""
    result = await transcribe_audio_with_metadata(
        audio_bytes,
        audio_format=audio_format,
        client=client,
    )
    return result.text


async def transcribe_audio_with_metadata(
    audio_bytes: bytes,
    audio_format: str = "mp3",
    client: object = None,  # kept for backward compat, ignored
) -> VoiceTranscriptionResult:
    """Transcribe audio bytes using gpt-audio-mini via OpenRouter.

    Args:
        audio_bytes: Raw audio file content.
        audio_format: Audio format hint (mp3, ogg, wav, etc.).
        client: DEPRECATED — ignored, uses internal OpenAI SDK client.

    Returns:
        Transcription text plus provider usage/cost metadata when available.

    Raises:
        ValueError: If the response cannot be parsed or audio is too large.
    """
    _ = client

    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise ValueError(
            f"Audio file too large: {len(audio_bytes)} bytes "
            f"(max {MAX_AUDIO_SIZE} bytes / {MAX_AUDIO_SIZE // 1024 // 1024} MB)"
        )

    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

    messages: list[dict[str, object]] = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _TRANSCRIPTION_PROMPT},
                {
                    "type": "input_audio",
                    "input_audio": {
                        "data": b64_audio,
                        "format": audio_format,
                    },
                },
            ],
        }
    ]

    start = time.monotonic()

    openai_client = _get_client()
    policy = policy_for_path(PATH_VOICE_TRANSCRIPTION)
    request_client = openai_client.with_options(
        timeout=policy.timeout_seconds,
        max_retries=0,
    )

    response = await request_client.chat.completions.create(
        model=settings.voxtral_model,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.0,
        max_tokens=policy.max_tokens,
        extra_body={"usage": {"include": True}},
    )

    elapsed = time.monotonic() - start

    text = response.choices[0].message.content
    if text is None:
        logger.error(
            "Voice transcription returned None content from model %s. "
            "Full response choices: %s",
            settings.voxtral_model,
            response.choices,
        )
        raise ValueError("Failed to parse transcription response (None content)")

    usage = getattr(response, "usage", None)
    tokens_in = _coerce_int(_usage_number(usage, "prompt_tokens", "input_tokens"))
    tokens_out = _coerce_int(_usage_number(usage, "completion_tokens", "output_tokens"))
    total_tokens = _coerce_int(_usage_number(usage, "total_tokens"))
    cost = _coerce_float(_usage_number(usage, "cost", "cost_usd"))
    response_model = str(getattr(response, "model", None) or settings.voxtral_model)

    # Log provider and model for debugging
    logger.info(
        "Voxtral transcription complete: model=%s, audio_size=%d bytes, format=%s, "
        "duration=%.2fs, result_length=%d chars, total_tokens=%s, cost=%s",
        response_model,
        len(audio_bytes),
        audio_format,
        elapsed,
        len(text),
        total_tokens,
        cost,
    )

    return VoiceTranscriptionResult(
        text=text.strip(),
        model=response_model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_tokens=total_tokens,
        cost=cost,
    )
