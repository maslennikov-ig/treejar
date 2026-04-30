"""Tests for Voxtral audio transcription service (OpenAI SDK version).

Tests cover:
  - Successful transcription (English, Arabic)
  - Whitespace stripping
  - Error handling (bad response, API errors)
  - Base64 encoding in payload
  - Size limit enforcement (MAX_AUDIO_SIZE)
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.integrations.voice.voxtral import MAX_AUDIO_SIZE, transcribe_audio


def _make_mock_response(
    content: str | None,
    *,
    usage: object | None = None,
    model: str = "openai/gpt-audio-mini",
) -> MagicMock:
    """Create a mock OpenAI ChatCompletion response."""
    mock_msg = MagicMock()
    mock_msg.content = content

    mock_choice = MagicMock()
    mock_choice.message = mock_msg

    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]
    mock_resp.model = model
    mock_resp.usage = usage
    return mock_resp


def _patch_openai_client(mock_response: MagicMock) -> tuple[Any, MagicMock]:
    """Patch _get_client to return a mock AsyncOpenAI client.

    Returns (patcher, mock_client) so tests can inspect call args.
    """
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    mock_client.with_options = MagicMock(return_value=mock_client)

    return patch(
        "src.integrations.voice.voxtral._get_client",
        return_value=mock_client,
    ), mock_client


class TestTranscribeAudio:
    async def test_transcribe_english_audio(self) -> None:
        """Test successful English audio transcription."""
        resp = _make_mock_response("Hello, I would like to order 10 office chairs")
        patcher, mock_client = _patch_openai_client(resp)

        with patcher:
            result = await transcribe_audio(b"fake_audio_bytes", audio_format="mp3")

        assert result == "Hello, I would like to order 10 office chairs"

        # Verify API call was made
        mock_client.chat.completions.create.assert_awaited_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "openai/gpt-audio-mini"

        # Verify message structure contains input_audio
        messages = call_kwargs["messages"]
        assert len(messages) == 1
        content = messages[0]["content"]
        assert content[1]["type"] == "input_audio"

    async def test_transcribe_arabic_audio(self) -> None:
        """Test Arabic audio transcription."""
        resp = _make_mock_response("مرحبا، أريد طلب عشرة كراسي مكتب")
        patcher, _ = _patch_openai_client(resp)

        with patcher:
            result = await transcribe_audio(b"fake_arabic_audio", audio_format="ogg")

        assert result == "مرحبا، أريد طلب عشرة كراسي مكتب"

    async def test_transcribe_strips_whitespace(self) -> None:
        """Test that transcription output is stripped."""
        resp = _make_mock_response("  hello  \n")
        patcher, _ = _patch_openai_client(resp)

        with patcher:
            result = await transcribe_audio(b"audio", audio_format="mp3")

        assert result == "hello"

    async def test_transcribe_none_content_raises_value_error(self) -> None:
        """Test that None content raises ValueError."""
        resp = _make_mock_response(None)
        patcher, _ = _patch_openai_client(resp)

        with patcher, pytest.raises(ValueError, match="Failed to parse"):
            await transcribe_audio(b"audio")

    async def test_base64_encoding_in_payload(self) -> None:
        """Test that audio bytes are correctly base64-encoded in the payload."""
        test_audio = b"test_audio_content"
        expected_b64 = base64.b64encode(test_audio).decode("ascii")

        resp = _make_mock_response("test")
        patcher, mock_client = _patch_openai_client(resp)

        with patcher:
            await transcribe_audio(test_audio, audio_format="wav")

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        audio_content = messages[0]["content"][1]
        assert audio_content["input_audio"]["data"] == expected_b64
        assert audio_content["input_audio"]["format"] == "wav"

    async def test_rejects_oversized_audio(self) -> None:
        """CR-V-02: Test that audio exceeding MAX_AUDIO_SIZE is rejected."""
        huge_audio = b"x" * (MAX_AUDIO_SIZE + 1)
        with pytest.raises(ValueError, match="Audio file too large"):
            await transcribe_audio(huge_audio)

    async def test_accepts_audio_at_limit(self) -> None:
        """Test that audio exactly at MAX_AUDIO_SIZE is accepted."""
        limit_audio = b"x" * MAX_AUDIO_SIZE
        resp = _make_mock_response("ok")
        patcher, _ = _patch_openai_client(resp)

        with patcher:
            result = await transcribe_audio(limit_audio)

        assert result == "ok"

    async def test_client_param_is_ignored(self) -> None:
        """Test that the deprecated client parameter is ignored (uses internal SDK)."""
        resp = _make_mock_response("hello")
        patcher, mock_client = _patch_openai_client(resp)

        external_client = AsyncMock()

        with patcher:
            result = await transcribe_audio(b"audio", client=external_client)

        assert result == "hello"
        # Internal SDK client used, not external
        mock_client.chat.completions.create.assert_awaited_once()
        # External client should NOT have been called
        external_client.post.assert_not_called()

    async def test_applies_provider_side_limits_timeout_and_usage_request(
        self,
    ) -> None:
        """Voice transcription uses bounded non-core provider request settings."""
        from src.llm.safety import PATH_VOICE_TRANSCRIPTION, policy_for_path

        resp = _make_mock_response("bounded transcription")
        patcher, mock_client = _patch_openai_client(resp)

        with patcher:
            result = await transcribe_audio(b"audio", audio_format="ogg")

        assert result == "bounded transcription"
        policy = policy_for_path(PATH_VOICE_TRANSCRIPTION)
        mock_client.with_options.assert_called_once_with(
            timeout=policy.timeout_seconds,
            max_retries=0,
        )
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "openai/gpt-audio-mini"
        assert call_kwargs["max_tokens"] == policy.max_tokens
        assert call_kwargs["temperature"] == 0.0
        assert call_kwargs["extra_body"] == {"usage": {"include": True}}

    async def test_transcribe_audio_with_metadata_returns_usage_and_cost(
        self,
    ) -> None:
        """OpenRouter/OpenAI-compatible usage is normalized for DB audit fields."""
        from src.integrations.voice.voxtral import transcribe_audio_with_metadata

        usage = SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=8,
            total_tokens=128,
            cost=0.00042,
        )
        resp = _make_mock_response(
            "I need two office chairs",
            usage=usage,
            model="openai/gpt-audio-mini",
        )
        patcher, _ = _patch_openai_client(resp)

        with patcher:
            result = await transcribe_audio_with_metadata(
                b"audio",
                audio_format="ogg",
            )

        assert result.text == "I need two office chairs"
        assert result.model == "openai/gpt-audio-mini"
        assert result.tokens_in == 120
        assert result.tokens_out == 8
        assert result.total_tokens == 128
        assert result.cost == 0.00042
