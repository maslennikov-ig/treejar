"""Voxtral audio transcription via OpenRouter API.

Uses `mistralai/voxtral-small-24b-2507` to transcribe audio messages
(English, Arabic, and 100+ other languages).
"""

from __future__ import annotations

import base64
import logging

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

# Prompt instructs the model to return raw transcription only
_TRANSCRIPTION_PROMPT = (
    "Transcribe this audio exactly as spoken in its original language. "
    "Return ONLY the transcription text, nothing else. "
    "Do not add any commentary, formatting, or markdown."
)


async def transcribe_audio(
    audio_bytes: bytes,
    audio_format: str = "mp3",
) -> str:
    """Transcribe audio bytes using Voxtral via OpenRouter.

    Args:
        audio_bytes: Raw audio file content.
        audio_format: Audio format hint (mp3, ogg, wav, etc.).

    Returns:
        Transcribed text string.

    Raises:
        httpx.HTTPStatusError: If the API returns an error status.
        ValueError: If the response cannot be parsed.
    """
    b64_audio = base64.b64encode(audio_bytes).decode("ascii")

    payload = {
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
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            json=payload,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type": "application/json",
            },
        )
        response.raise_for_status()

    data = response.json()

    try:
        text: str = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        logger.error("Unexpected Voxtral response structure: %s", data)
        raise ValueError("Failed to parse Voxtral transcription response") from exc

    return text.strip()
