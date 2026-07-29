"""Focused tests for OpenRouter speech-to-text integration."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.integrations.voice import voxtral
from src.integrations.voice.voxtral import (
    MAX_AUDIO_SIZE,
    transcribe_audio,
    transcribe_audio_with_metadata,
)


def _response(
    payload: dict[str, object],
    *,
    status_code: int = 200,
) -> httpx.Response:
    request = httpx.Request(
        "POST",
        "https://openrouter.ai/api/v1/audio/transcriptions",
    )
    return httpx.Response(status_code, request=request, json=payload)


class TestAudioFormatDetection:
    @pytest.mark.parametrize(
        ("audio_bytes", "mime_type", "expected"),
        [
            (b"fLaC\x00\x00\x00\x22", None, "flac"),
            (b"OggS\x00\x02", "audio/ogg; codecs=opus", "ogg"),
            (b"RIFF\x24\x00\x00\x00WAVEfmt ", "audio/x-wav", "wav"),
            (b"\x1aE\xdf\xa3\x93B\x82\x88webm", "audio/webm", "webm"),
            (b"ID3\x04\x00\x00", "audio/mpeg", "mp3"),
            (b"\xff\xf1P\x80", "audio/aac", "aac"),
            (b"\x00\x00\x00\x18ftypM4A ", "audio/mp4", "m4a"),
        ],
    )
    def test_detects_supported_format_from_mime_and_magic(
        self,
        audio_bytes: bytes,
        mime_type: str | None,
        expected: str,
    ) -> None:
        assert voxtral.detect_audio_format(audio_bytes, mime_type=mime_type) == expected

    def test_rejects_unknown_format_instead_of_defaulting_to_mp3(self) -> None:
        with pytest.raises(ValueError, match="Unsupported audio format"):
            voxtral.detect_audio_format(
                b"not-an-audio-file",
                mime_type="application/octet-stream",
            )

    def test_rejects_conflicting_mime_and_magic(self) -> None:
        with pytest.raises(ValueError, match="does not match"):
            voxtral.detect_audio_format(
                b"fLaC\x00\x00\x00\x22",
                mime_type="audio/mpeg",
            )


class TestTranscribeAudio:
    async def test_uses_dedicated_stt_endpoint_without_transcription_prompt(
        self,
    ) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _response({"text": "  Hello from audio  "})

        result = await transcribe_audio(
            b"OggS\x00\x02audio",
            audio_format="ogg",
            client=client,
        )

        assert result == "Hello from audio"
        client.post.assert_awaited_once()
        request = client.post.await_args
        assert request.args[0] == "https://openrouter.ai/api/v1/audio/transcriptions"
        assert request.kwargs["json"] == {
            "model": "openai/gpt-4o-mini-transcribe",
            "input_audio": {
                "data": base64.b64encode(b"OggS\x00\x02audio").decode("ascii"),
                "format": "ogg",
            },
        }
        assert "prompt" not in request.kwargs["json"]

    async def test_accepts_arabic_transcription(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _response(
            {"text": "مرحبا، أريد طلب عشرة كراسي مكتب"}
        )

        result = await transcribe_audio(
            b"fLaC\x00\x00\x00\x22audio",
            audio_format="flac",
            client=client,
        )

        assert result == "مرحبا، أريد طلب عشرة كراسي مكتب"

    async def test_rejects_missing_transcription_text(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _response({"usage": {"seconds": 1.0}})

        with pytest.raises(ValueError, match="Failed to parse"):
            await transcribe_audio(
                b"RIFF\x24\x00\x00\x00WAVEfmt ",
                audio_format="wav",
                client=client,
            )

    async def test_rejects_oversized_audio_before_provider_call(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        with pytest.raises(ValueError, match="Audio file too large"):
            await transcribe_audio(
                b"x" * (MAX_AUDIO_SIZE + 1),
                audio_format="mp3",
                client=client,
            )

        client.post.assert_not_awaited()

    async def test_rejects_missing_format_instead_of_assuming_mp3(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)

        with pytest.raises(ValueError, match="Audio format is required"):
            await transcribe_audio(b"unknown", client=client)

        client.post.assert_not_awaited()

    async def test_applies_bounded_request_policy(self) -> None:
        from src.llm.safety import PATH_VOICE_TRANSCRIPTION, policy_for_path

        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _response({"text": "bounded transcription"})

        await transcribe_audio(
            b"OggS\x00\x02audio",
            audio_format="ogg",
            client=client,
        )

        policy = policy_for_path(PATH_VOICE_TRANSCRIPTION)
        assert client.post.await_args.kwargs["timeout"] == policy.timeout_seconds

    async def test_returns_usage_cost_and_duration_metadata(self) -> None:
        client = AsyncMock(spec=httpx.AsyncClient)
        client.post.return_value = _response(
            {
                "text": "I need two office chairs",
                "model": "openai/gpt-4o-mini-transcribe",
                "usage": {
                    "seconds": 9.2,
                    "input_tokens": 83,
                    "output_tokens": 30,
                    "total_tokens": 113,
                    "cost": 0.000508,
                },
            }
        )

        result = await transcribe_audio_with_metadata(
            b"OggS\x00\x02audio",
            audio_format="ogg",
            client=client,
        )

        assert result.text == "I need two office chairs"
        assert result.model == "openai/gpt-4o-mini-transcribe"
        assert result.tokens_in == 83
        assert result.tokens_out == 30
        assert result.total_tokens == 113
        assert result.cost == 0.000508
        assert result.duration_seconds == 9.2
        assert result.request_duration_seconds >= 0

    async def test_creates_and_closes_internal_client_for_legacy_callers(
        self,
    ) -> None:
        internal_client = AsyncMock(spec=httpx.AsyncClient)
        internal_client.post.return_value = _response({"text": "hello"})
        context = AsyncMock()
        context.__aenter__.return_value = internal_client
        context.__aexit__.return_value = False

        with patch(
            "src.integrations.voice.voxtral.httpx.AsyncClient",
            return_value=context,
        ):
            result = await transcribe_audio(
                b"OggS\x00\x02audio",
                audio_format="ogg",
            )

        assert result == "hello"
        context.__aexit__.assert_awaited_once()


def test_normalizes_mapping_and_object_usage_values() -> None:
    """The provider may expose usage as JSON or an SDK-style object."""
    from src.integrations.voice.voxtral import _usage_number

    assert _usage_number({"input_tokens": 7}, "input_tokens") == 7
    assert _usage_number(SimpleNamespace(cost=0.001), "cost") == 0.001
