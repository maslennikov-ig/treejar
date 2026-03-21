"""Voxtral audio transcription via OpenRouter API.

Uses `mistralai/voxtral-small-24b-2507` to transcribe audio messages
(English, Arabic, and 100+ other languages).
"""

from __future__ import annotations

import base64
import logging
import time

import httpx

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


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "mp3",
    client: httpx.AsyncClient | None = None,
) -> str:
    """Transcribe audio bytes using Voxtral via OpenRouter.

    Args:
        audio_bytes: Raw audio file content.
        audio_format: Audio format hint (mp3, ogg, wav, etc.).
        client: Optional reusable httpx.AsyncClient. If not provided,
                a temporary one is created for this call.

    Returns:
        Transcribed text string.

    Raises:
        httpx.HTTPStatusError: If the API returns an error status.
        ValueError: If the response cannot be parsed or audio is too large.
    """
    if len(audio_bytes) > MAX_AUDIO_SIZE:
        raise ValueError(
            f"Audio file too large: {len(audio_bytes)} bytes "
            f"(max {MAX_AUDIO_SIZE} bytes / {MAX_AUDIO_SIZE // 1024 // 1024} MB)"
        )

    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

    payload: dict[str, object] = {
        "model": settings.voxtral_model,
        "messages": [
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
        ],
        # Pin to OpenAI provider to avoid routing to providers
        # that don't support input_audio
        "provider": {
            "order": ["OpenAI"],
            "allow_fallbacks": False,
        },
    }

    start = time.monotonic()

    if client is not None:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()
    else:
        async with httpx.AsyncClient(timeout=60.0) as tmp_client:
            response = await tmp_client.post(
                f"{settings.openrouter_base_url}/chat/completions",
                json=payload,
                headers={
                    "Authorization": f"Bearer {settings.openrouter_api_key}",
                    "Content-Type": "application/json",
                },
            )
            response.raise_for_status()

    elapsed = time.monotonic() - start
    data = response.json()

    # Log provider and model for debugging routing issues
    logger.info(
        "OpenRouter audio response: model=%s, provider=%s, status=%d",
        data.get("model", "?"),
        data.get("provider", "?"),
        response.status_code,
    )

    try:
        text: str = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Voxtral response structure: %s", data)
        raise ValueError("Failed to parse Voxtral transcription response") from exc

    # CR-V-12: Structured metrics logging
    logger.info(
        "Voxtral transcription complete: audio_size=%d bytes, format=%s, "
        "duration=%.2fs, result_length=%d chars",
        len(audio_bytes),
        audio_format,
        elapsed,
        len(text),
    )

    return text.strip()
