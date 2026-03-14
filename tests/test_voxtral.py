"""Tests for Voxtral audio transcription service."""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.voice.voxtral import MAX_AUDIO_SIZE, transcribe_audio


def _make_mock_response(json_data: dict) -> MagicMock:
    """Create a mock httpx.Response with synchronous .json()."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()  # sync in httpx
    return mock_resp


def _patch_client(mock_response: MagicMock):
    """Patch httpx.AsyncClient to return mock_response from .post()."""
    mock_client = AsyncMock()
    mock_client.post.return_value = mock_response
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch(
        "src.integrations.voice.voxtral.httpx.AsyncClient",
        return_value=mock_client,
    )


class TestTranscribeAudio:
    async def test_transcribe_english_audio(self) -> None:
        """Test successful English audio transcription."""
        resp = _make_mock_response({
            "choices": [{"message": {"content": "Hello, I would like to order 10 office chairs"}}]
        })
        with _patch_client(resp) as mock_cls:
            result = await transcribe_audio(b"fake_audio_bytes", audio_format="mp3")

        assert result == "Hello, I would like to order 10 office chairs"

        # Verify API payload structure
        mock_client = mock_cls.return_value
        payload = mock_client.post.call_args.kwargs["json"]
        assert payload["model"] == "mistralai/voxtral-small-24b-2507"
        assert payload["messages"][0]["content"][1]["type"] == "input_audio"

    async def test_transcribe_arabic_audio(self) -> None:
        """Test Arabic audio transcription."""
        resp = _make_mock_response({
            "choices": [{"message": {"content": "مرحبا، أريد طلب عشرة كراسي مكتب"}}]
        })
        with _patch_client(resp):
            result = await transcribe_audio(b"fake_arabic_audio", audio_format="ogg")

        assert result == "مرحبا، أريد طلب عشرة كراسي مكتب"

    async def test_transcribe_strips_whitespace(self) -> None:
        """Test that transcription output is stripped."""
        resp = _make_mock_response({
            "choices": [{"message": {"content": "  hello  \n"}}]
        })
        with _patch_client(resp):
            result = await transcribe_audio(b"audio", audio_format="mp3")

        assert result == "hello"

    async def test_transcribe_bad_response_raises_value_error(self) -> None:
        """Test that malformed response raises ValueError."""
        resp = _make_mock_response({"error": "bad request"})
        with _patch_client(resp), pytest.raises(ValueError, match="Failed to parse"):
            await transcribe_audio(b"audio")

    async def test_transcribe_http_error_propagates(self) -> None:
        """Test that HTTP errors propagate."""
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=httpx.Request("POST", "http://test"),
            response=httpx.Response(429),
        )
        with _patch_client(resp), pytest.raises(httpx.HTTPStatusError):
            await transcribe_audio(b"audio")

    async def test_base64_encoding_in_payload(self) -> None:
        """Test that audio bytes are correctly base64-encoded in the payload."""
        test_audio = b"test_audio_content"
        expected_b64 = base64.b64encode(test_audio).decode("ascii")

        resp = _make_mock_response({
            "choices": [{"message": {"content": "test"}}]
        })
        with _patch_client(resp) as mock_cls:
            await transcribe_audio(test_audio, audio_format="wav")

        mock_client = mock_cls.return_value
        payload = mock_client.post.call_args.kwargs["json"]
        audio_content = payload["messages"][0]["content"][1]
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
        resp = _make_mock_response({
            "choices": [{"message": {"content": "ok"}}]
        })
        with _patch_client(resp):
            result = await transcribe_audio(limit_audio)

        assert result == "ok"

    async def test_uses_provided_client(self) -> None:
        """CR-V-03: Test that an externally provided client is used."""
        resp = _make_mock_response({
            "choices": [{"message": {"content": "hello"}}]
        })
        mock_client = AsyncMock()
        mock_client.post.return_value = resp

        result = await transcribe_audio(b"audio", client=mock_client)

        assert result == "hello"
        mock_client.post.assert_called_once()
