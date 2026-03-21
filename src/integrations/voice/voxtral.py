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

from openai import AsyncOpenAI

from src.core.config import settings

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


def _get_client() -> AsyncOpenAI:
    """Get or create the OpenAI SDK client pointed at OpenRouter."""
    global _client  # noqa: PLW0603
    if _client is None:
        _client = AsyncOpenAI(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            timeout=90.0,
            max_retries=2,
        )
    return _client


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "mp3",
    client: object = None,  # kept for backward compat, ignored
) -> str:
    """Transcribe audio bytes using gpt-audio-mini via OpenRouter.

    Args:
        audio_bytes: Raw audio file content.
        audio_format: Audio format hint (mp3, ogg, wav, etc.).
        client: DEPRECATED — ignored, uses internal OpenAI SDK client.

    Returns:
        Transcribed text string.

    Raises:
        ValueError: If the response cannot be parsed or audio is too large.
    """
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

    response = await openai_client.chat.completions.create(
        model=settings.voxtral_model,
        messages=messages,  # type: ignore[arg-type]
        temperature=0.0,
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

    # Log provider and model for debugging
    logger.info(
        "Voxtral transcription complete: model=%s, audio_size=%d bytes, format=%s, "
        "duration=%.2fs, result_length=%d chars",
        response.model,
        len(audio_bytes),
        audio_format,
        elapsed,
        len(text),
    )

    return text.strip()
