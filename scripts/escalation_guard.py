from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

_SUPPRESSED_TELEGRAM_RESULT = {"ok": True, "result": {"suppressed": True}}


@dataclass
class EscalationAlertMocks:
    send_message_with_inline_keyboard: AsyncMock
    send_document: AsyncMock


@contextmanager
def maybe_suppress_external_escalation_alerts() -> Iterator[
    EscalationAlertMocks | None
]:
    """Suppress Telegram sends while preserving notify_manager_escalation DB behavior."""
    if os.getenv("ALLOW_REAL_ESCALATIONS") == "1":
        yield None
        return

    with ExitStack() as stack:
        send_keyboard = stack.enter_context(
            patch(
                "src.integrations.notifications.escalation.TelegramClient.send_message_with_inline_keyboard",
                new=AsyncMock(return_value=_SUPPRESSED_TELEGRAM_RESULT),
            )
        )
        send_document = stack.enter_context(
            patch(
                "src.integrations.notifications.escalation.TelegramClient.send_document",
                new=AsyncMock(return_value=_SUPPRESSED_TELEGRAM_RESULT),
            )
        )
        yield EscalationAlertMocks(
            send_message_with_inline_keyboard=send_keyboard,
            send_document=send_document,
        )
