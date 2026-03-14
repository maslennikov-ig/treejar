"""Tests for audio message handling in the webhook and chat pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from src.core.config import settings
from src.integrations.messaging.wazzup import WazzupProvider
from src.models.message import Message
from src.schemas.webhook import WazzupIncomingMessage, WazzupMedia


class TestVoxtralConfig:
    def test_voxtral_model_setting_exists(self) -> None:
        """Test that voxtral_model config setting exists and has correct default."""
        assert hasattr(settings, "voxtral_model")
        assert settings.voxtral_model == "mistralai/voxtral-small-24b-2507"

    def test_main_model_unchanged(self) -> None:
        """Test that main LLM model was NOT changed to voxtral."""
        assert settings.openrouter_model_main == "z-ai/glm-5"


class TestMessageModelAudioFields:
    def test_message_supports_audio_url(self) -> None:
        """Test that Message model has audio_url field."""
        msg = Message(
            conversation_id="00000000-0000-0000-0000-000000000001",
            role="user",
            content="transcribed text",
            audio_url="https://cdn.wazzup24.com/files/test.ogg",
        )
        assert msg.audio_url == "https://cdn.wazzup24.com/files/test.ogg"

    def test_message_supports_transcription(self) -> None:
        """Test that Message model has transcription field."""
        msg = Message(
            conversation_id="00000000-0000-0000-0000-000000000001",
            role="user",
            content="transcribed text",
            transcription="transcribed text",
        )
        assert msg.transcription == "transcribed text"

    def test_message_audio_fields_default_none(self) -> None:
        """Test that audio fields default to None."""
        msg = Message(
            conversation_id="00000000-0000-0000-0000-000000000001",
            role="user",
            content="normal text",
        )
        assert msg.audio_url is None
        assert msg.transcription is None


class TestWazzupDownloadMedia:
    def test_provider_has_download_media(self) -> None:
        """Test that WazzupProvider has download_media method."""
        provider = WazzupProvider()
        assert hasattr(provider, "download_media")
        assert callable(provider.download_media)

    async def test_download_media_returns_bytes(self) -> None:
        """Test download_media returns raw bytes."""
        with patch("src.integrations.messaging.wazzup.httpx.AsyncClient") as mock_cls:
            mock_dl_client = AsyncMock()
            mock_response = AsyncMock()
            mock_response.content = b"fake_audio_data"
            mock_response.raise_for_status = AsyncMock()
            mock_dl_client.get.return_value = mock_response
            mock_dl_client.__aenter__ = AsyncMock(return_value=mock_dl_client)
            mock_dl_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_dl_client

            provider = WazzupProvider()
            result = await provider.download_media("https://cdn.wazzup24.com/audio.ogg")

        assert result == b"fake_audio_data"


class TestAudioWebhookSchema:
    def test_audio_message_schema_parsed(self) -> None:
        """Test that audio webhook payload is correctly parsed."""
        msg = WazzupIncomingMessage(
            messageId="audio-001",
            chatId="971551220665",
            type="audio",
            status="inbound",
            dateTime="2026-03-14T09:00:00.000",
            authorType="client",
            media=WazzupMedia(
                url="https://cdn.wazzup24.com/files/test.ogg",
                mimeType="audio/ogg",
            ),
        )
        assert msg.type == "audio"
        assert msg.media is not None
        assert msg.media.url == "https://cdn.wazzup24.com/files/test.ogg"
        assert msg.media.mimeType == "audio/ogg"

    def test_voice_message_type_supported(self) -> None:
        """Test that 'voice' type messages are also supported."""
        msg = WazzupIncomingMessage(
            messageId="voice-001",
            chatId="971551220665",
            type="voice",
            status="inbound",
            media=WazzupMedia(url="https://cdn.wazzup24.com/voice.ogg"),
        )
        assert msg.type == "voice"
        assert msg.type in ("audio", "voice")
