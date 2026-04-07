"""Tests for B5: escalation fallback response to client.

Covers:
  - _handle_escalation_fallback sends a fallback message to the client
  - Fallback is saved as an assistant message in DB
  - Manager re-notification with cooldown (5 min)
  - Language-specific fallback (EN/AR)
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


@pytest.mark.asyncio
async def test_escalation_fallback_sends_message_en() -> None:
    """Client receives English fallback when escalation is active."""
    from src.services.chat import _handle_escalation_fallback

    conv = MagicMock()
    conv.id = uuid4()
    conv.phone = "+971501234567"
    conv.language = "en"

    mock_wazzup = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None])
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("src.integrations.notifications.telegram.TelegramClient") as mock_tg:
        mock_tg_instance = MagicMock()
        mock_tg_instance.send_message = AsyncMock()
        mock_tg.return_value = mock_tg_instance

        await _handle_escalation_fallback(
            conv=conv,
            combined_text="Hello, are you there?",
            wazzup=mock_wazzup,
            redis=mock_redis,
            db=mock_db,
        )

    # Fallback sent to client
    mock_wazzup.send_text.assert_called_once()
    call_kwargs = mock_wazzup.send_text.call_args[1]
    assert call_kwargs["chat_id"] == "+971501234567"
    assert "manager" in call_kwargs["text"].lower()

    # Saved to DB
    mock_db.add.assert_called_once()
    saved_msg = mock_db.add.call_args[0][0]
    assert saved_msg.role == "assistant"
    assert saved_msg.model == "fallback"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_escalation_fallback_sends_message_ar() -> None:
    """Client receives Arabic fallback when language is AR."""
    from src.services.chat import _handle_escalation_fallback

    conv = MagicMock()
    conv.id = uuid4()
    conv.phone = "79262810921"
    conv.language = "ar"

    mock_wazzup = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, None])
    mock_redis.setex = AsyncMock()
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("src.integrations.notifications.telegram.TelegramClient") as mock_tg:
        mock_tg_instance = MagicMock()
        mock_tg_instance.send_message = AsyncMock()
        mock_tg.return_value = mock_tg_instance

        await _handle_escalation_fallback(
            conv=conv,
            combined_text="مرحبا",
            wazzup=mock_wazzup,
            redis=mock_redis,
            db=mock_db,
        )

    call_kwargs = mock_wazzup.send_text.call_args[1]
    assert "المدير" in call_kwargs["text"]  # Arabic word for manager


@pytest.mark.asyncio
async def test_escalation_renotify_cooldown() -> None:
    """Manager is NOT re-notified within cooldown window."""
    from src.services.chat import _handle_escalation_fallback

    conv = MagicMock()
    conv.id = uuid4()
    conv.phone = "+971501234567"
    conv.language = "en"

    mock_wazzup = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=[None, "1"])  # repeat miss, cooldown hit
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("src.integrations.notifications.telegram.TelegramClient") as mock_tg:
        mock_tg_instance = MagicMock()
        mock_tg_instance.send_message = AsyncMock()
        mock_tg.return_value = mock_tg_instance

        await _handle_escalation_fallback(
            conv=conv,
            combined_text="Still waiting",
            wazzup=mock_wazzup,
            redis=mock_redis,
            db=mock_db,
        )

    # Client STILL gets a response
    mock_wazzup.send_text.assert_called_once()

    # But manager is NOT re-notified (cooldown active)
    mock_tg_instance.send_message.assert_not_called()
    mock_redis.setex.assert_called_once()


@pytest.mark.asyncio
async def test_escalation_fallback_skips_duplicate_repeat_message() -> None:
    """Repeated identical client text should not trigger a new fallback or Telegram ping."""
    from src.services.chat import _handle_escalation_fallback

    conv = MagicMock()
    conv.id = uuid4()
    conv.phone = "+971501234567"
    conv.language = "en"

    mock_wazzup = AsyncMock()
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value="1")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.commit = AsyncMock()

    with patch("src.integrations.notifications.telegram.TelegramClient") as mock_tg:
        mock_tg_instance = MagicMock()
        mock_tg_instance.send_message = AsyncMock()
        mock_tg.return_value = mock_tg_instance

        await _handle_escalation_fallback(
            conv=conv,
            combined_text="Still waiting",
            wazzup=mock_wazzup,
            redis=mock_redis,
            db=mock_db,
        )

    mock_wazzup.send_text.assert_not_called()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()
    mock_tg_instance.send_message.assert_not_called()
    mock_redis.setex.assert_not_called()
