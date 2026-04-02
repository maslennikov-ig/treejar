"""Tests for bot silencing and manual takeover (Components 2 & 3).

Verifies:
- Bot stays silent when escalation is active (pending/in_progress/resolved)
- Manager message with no escalation triggers manual_takeover
- Messages saved with correct roles (user/manager)
- _determine_role helper function
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.webhook import WazzupIncomingMessage
from src.services.chat import _determine_role, process_incoming_batch

# ---------------------------------------------------------------------------
# _determine_role tests
# ---------------------------------------------------------------------------


def test_determine_role_client() -> None:
    msg = WazzupIncomingMessage(
        messageId="m1", chatId="123", authorType="client", timestamp=0
    )
    assert _determine_role(msg) == "user"


def test_determine_role_manager() -> None:
    msg = WazzupIncomingMessage(
        messageId="m2", chatId="123", authorType="manager", timestamp=0
    )
    assert _determine_role(msg) == "manager"


def test_determine_role_none() -> None:
    msg = WazzupIncomingMessage(messageId="m3", chatId="123", timestamp=0)
    assert _determine_role(msg) == "user"


# ---------------------------------------------------------------------------
# Helper mocks
# ---------------------------------------------------------------------------


class MockResult:
    """Mock SQLAlchemy result object."""

    def __init__(self, val: Any) -> None:
        self.val = val

    def scalar_one_or_none(self) -> Any:
        return self.val

    def scalars(self) -> Any:
        return self

    def first(self) -> Any:
        return self.val

    def all(self) -> Any:
        if isinstance(self.val, list):
            return self.val
        return [self.val] if self.val is not None else []


def _make_mock_conv(
    escalation_status: str = "none",
    conv_id: str = "conv-uuid-123",
) -> MagicMock:
    mock_conv = MagicMock()
    mock_conv.id = conv_id
    mock_conv.phone = "1234567890"
    mock_conv.escalation_status = escalation_status
    return mock_conv


# ---------------------------------------------------------------------------
# Bot silencing tests (Component 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_bot_silent_when_escalated(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Bot should NOT call LLM when escalation is active."""
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    # Conversation with active escalation
    mock_conv = _make_mock_conv(escalation_status="pending")

    mock_session.execute.side_effect = [
        MockResult(None),  # bot_enabled check
        MockResult(mock_conv),  # conv lookup
        MockResult([]),  # msg dedup check
    ]

    # Client message during escalation
    msg = WazzupIncomingMessage(
        messageId="msg-esc-1",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Are you there?",
        channelId="ch1",
        timestamp=1704067200,
        authorType="client",
    )
    mock_redis = AsyncMock()
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    ctx = {"redis": mock_redis}
    with patch("src.services.chat.settings.wazzup_channel_id", "ch1"):
        await process_incoming_batch(ctx, "1234567890")

    # Messages should be saved (commit called)
    mock_session.commit.assert_awaited()
    # LLM should NOT be called
    mock_process_message.assert_not_awaited()


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_bot_silent_during_manual_takeover(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Bot should NOT call LLM when manual_takeover is active."""
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    mock_conv = _make_mock_conv(escalation_status="manual_takeover")

    mock_session.execute.side_effect = [
        MockResult(None),
        MockResult(mock_conv),
        MockResult([]),
    ]

    msg = WazzupIncomingMessage(
        messageId="msg-mt-1",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Client follow-up",
        channelId="ch1",
        timestamp=1704067200,
        authorType="client",
    )
    mock_redis = AsyncMock()
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "ch1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    mock_session.commit.assert_awaited()
    mock_process_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Manual takeover tests (Component 3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_manual_takeover_triggered(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Manager message + escalation_status=none → manual_takeover."""
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    mock_conv = _make_mock_conv(escalation_status="none")

    mock_session.execute.side_effect = [
        MockResult(None),
        MockResult(mock_conv),
        MockResult([]),
    ]

    msg = WazzupIncomingMessage(
        messageId="msg-mgr-1",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="I'll take over here",
        channelId="ch1",
        timestamp=1704067200,
        authorType="manager",
        isEcho=True,
        authorName="Israullah",
    )
    mock_redis = AsyncMock()
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "ch1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    # escalation_status should be set to manual_takeover
    assert mock_conv.escalation_status == "manual_takeover"
    # Messages saved
    mock_session.commit.assert_awaited()
    # LLM NOT called (because escalation is now active)
    mock_process_message.assert_not_awaited()


# ---------------------------------------------------------------------------
# Manager role saving test
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.services.chat.async_session_factory")
@patch("src.services.chat.process_message")
@patch("src.services.chat.WazzupProvider")
@patch("src.services.chat.ZohoCRMClient")
@patch("src.services.chat.ZohoInventoryClient")
@patch("src.services.chat.EmbeddingEngine")
async def test_manager_message_saved_with_correct_role(
    mock_embedding_cls: MagicMock,
    mock_zoho_inv_cls: MagicMock,
    mock_zoho_crm_cls: MagicMock,
    mock_wazzup_cls: MagicMock,
    mock_process_message: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Manager messages should be saved with role='manager'."""
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__.return_value = mock_session

    mock_conv = _make_mock_conv(escalation_status="pending")

    mock_session.execute.side_effect = [
        MockResult(None),
        MockResult(mock_conv),
        MockResult([]),
    ]

    msg = WazzupIncomingMessage(
        messageId="msg-mgr-role",
        chatId="1234567890",
        chatType="whatsapp",
        type="text",
        text="Hi, I'm your manager",
        channelId="ch1",
        timestamp=1704067200,
        authorType="manager",
        isEcho=True,
    )
    mock_redis = AsyncMock()
    mock_redis.lpop.side_effect = [msg.model_dump_json(), None]

    with patch("src.services.chat.settings.wazzup_channel_id", "ch1"):
        await process_incoming_batch({"redis": mock_redis}, "1234567890")

    # Check that db.add was called with a Message having role='manager'
    add_calls = mock_session.add.call_args_list
    from src.models.message import Message

    manager_msgs = [
        call.args[0]
        for call in add_calls
        if isinstance(call.args[0], Message) and call.args[0].role == "manager"
    ]
    assert len(manager_msgs) == 1
    assert manager_msgs[0].content == "Hi, I'm your manager"
