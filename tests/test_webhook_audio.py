"""Tests for audio message handling in the webhook and chat pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.config import Settings, settings
from src.integrations.messaging.wazzup import WazzupProvider
from src.models.message import Message
from src.schemas.webhook import WazzupIncomingMessage, WazzupMedia


class TestVoxtralConfig:
    def test_voice_transcription_model_has_stt_default(self) -> None:
        assert settings.voice_transcription_model == (
            "openai/gpt-4o-mini-transcribe"
        )

    def test_legacy_voxtral_model_env_is_temporary_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("VOICE_TRANSCRIPTION_MODEL", raising=False)
        monkeypatch.setenv("VOXTRAL_MODEL", "mistralai/voxtral-mini-transcribe")

        legacy = Settings(_env_file=None)

        assert (
            legacy.voice_transcription_model
            == "mistralai/voxtral-mini-transcribe"
        )

    def test_new_voice_model_env_takes_precedence_over_legacy_alias(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv(
            "VOICE_TRANSCRIPTION_MODEL",
            "openai/gpt-4o-mini-transcribe",
        )
        monkeypatch.setenv("VOXTRAL_MODEL", "mistralai/voxtral-mini-transcribe")

        configured = Settings(_env_file=None)

        assert (
            configured.voice_transcription_model
            == "openai/gpt-4o-mini-transcribe"
        )

    def test_default_openrouter_models_use_approved_routes(self) -> None:
        """Test model defaults without reading developer-local environment files."""
        defaults = Settings(_env_file=None)

        assert defaults.openrouter_model_main == "z-ai/glm-5.2"
        assert defaults.openrouter_model_fast == "deepseek/deepseek-v4-flash"


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

    def test_message_admin_exposes_audio_and_cost_fields(self) -> None:
        """SQLAdmin message inspection must show voice audit fields."""
        from src.api.admin.views import MessageAdmin

        assert Message.message_type in MessageAdmin.column_list
        assert Message.audio_url in MessageAdmin.column_list
        assert Message.transcription in MessageAdmin.column_list
        assert Message.tokens_in in MessageAdmin.column_list
        assert Message.tokens_out in MessageAdmin.column_list
        assert Message.cost in MessageAdmin.column_list
        assert Message.model in MessageAdmin.column_list

        assert Message.audio_url in MessageAdmin.column_details_list
        assert Message.transcription in MessageAdmin.column_details_list
        assert Message.cost in MessageAdmin.column_details_list
        assert Message.model in MessageAdmin.column_details_list


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
