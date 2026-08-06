"""A suppressed manager alert must not look like a delivered one (tj-rkh3).

`notify_manager_escalation` commits the escalation row before it tries Telegram,
so an escalation is never lost. What could be lost until 2026-08-06 was the
manager finding out in time, and all three ways of losing it were quiet: channel
gating returned early at info level, an unconfigured client returned `None`, and
any failure was swallowed. From the outside a suppressed alert was
indistinguishable from a sent one, which is exactly what makes a monitoring gap
survive.

These tests pin the one thing that matters operationally: whenever the manager
was not notified, the log says so and says why — and the escalation row is still
committed either way.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.integrations.notifications import escalation as escalation_module
from src.schemas.common import EscalationStatus, EscalationType

_NOT_NOTIFIED = "MANAGER NOT NOTIFIED"


class _FakeSession:
    """Just enough session to record the commit the escalation depends on."""

    def __init__(self) -> None:
        self.added: list[object] = []
        self.commits = 0

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1


@pytest.fixture
def conversation() -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        phone="971501234567",
        escalation_status=None,
        metadata_={},
    )


async def _notify(conversation: SimpleNamespace, db: _FakeSession) -> None:
    await escalation_module.notify_manager_escalation(
        conversation=conversation,  # type: ignore[arg-type]
        reason="Customer asked for a manager",
        recent_messages=["hello"],
        db=db,  # type: ignore[arg-type]
        escalation_type=EscalationType.GENERAL,
    )


@pytest.mark.asyncio
async def test_channel_gating_says_the_manager_was_not_notified(
    conversation: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """The default production configuration takes this path."""
    db = _FakeSession()
    with (
        patch.object(
            escalation_module,
            "should_send_manager_alert_for_conversation_with_db",
            AsyncMock(return_value=False),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await _notify(conversation, db)

    assert _NOT_NOTIFIED in caplog.text
    assert "inbound channel gating" in caplog.text
    # The escalation itself is never lost.
    assert db.commits == 1
    assert conversation.escalation_status == EscalationStatus.PENDING.value


@pytest.mark.asyncio
async def test_an_unconfigured_telegram_says_the_manager_was_not_notified(
    conversation: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """`send_message_with_inline_keyboard` returns None when unconfigured."""
    db = _FakeSession()
    client = MagicMock()
    client.send_message_with_inline_keyboard = AsyncMock(return_value=None)
    with (
        patch.object(
            escalation_module,
            "should_send_manager_alert_for_conversation_with_db",
            AsyncMock(return_value=True),
        ),
        patch.object(escalation_module, "TelegramClient", return_value=client),
        caplog.at_level(logging.WARNING),
    ):
        await _notify(conversation, db)

    assert _NOT_NOTIFIED in caplog.text
    assert "not configured" in caplog.text


@pytest.mark.asyncio
async def test_a_failed_send_says_the_manager_was_not_notified(
    conversation: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    db = _FakeSession()
    client = MagicMock()
    client.send_message_with_inline_keyboard = AsyncMock(
        side_effect=RuntimeError("telegram is down")
    )
    with (
        patch.object(
            escalation_module,
            "should_send_manager_alert_for_conversation_with_db",
            AsyncMock(return_value=True),
        ),
        patch.object(escalation_module, "TelegramClient", return_value=client),
        caplog.at_level(logging.WARNING),
    ):
        await _notify(conversation, db)

    assert _NOT_NOTIFIED in caplog.text
    # A failing Telegram must never break the customer's turn.
    assert db.commits == 1


@pytest.mark.asyncio
async def test_a_delivered_alert_stays_quiet(
    conversation: SimpleNamespace, caplog: pytest.LogCaptureFixture
) -> None:
    """The warning has to mean something, so the happy path must not raise it."""
    db = _FakeSession()
    client = MagicMock()
    client.send_message_with_inline_keyboard = AsyncMock(return_value={"ok": True})
    with (
        patch.object(
            escalation_module,
            "should_send_manager_alert_for_conversation_with_db",
            AsyncMock(return_value=True),
        ),
        patch.object(escalation_module, "TelegramClient", return_value=client),
        caplog.at_level(logging.WARNING),
    ):
        await _notify(conversation, db)

    assert _NOT_NOTIFIED not in caplog.text
    client.send_message_with_inline_keyboard.assert_awaited_once()
