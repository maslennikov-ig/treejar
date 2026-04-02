from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from scripts.escalation_guard import maybe_suppress_external_escalation_alerts

from src.integrations.notifications.escalation import notify_manager_escalation
from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.schemas.common import EscalationStatus, EscalationType, SalesStage


@pytest.mark.asyncio
async def test_helper_suppresses_telegram_but_preserves_escalation_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ALLOW_REAL_ESCALATIONS", raising=False)

    conversation = Conversation(
        id=uuid4(),
        phone="+971500000000",
        sales_stage=SalesStage.GREETING.value,
        escalation_status=EscalationStatus.NONE.value,
        language="en",
    )
    db = AsyncMock()
    db.add = MagicMock()

    with maybe_suppress_external_escalation_alerts() as mocks:
        await notify_manager_escalation(
            conversation=conversation,
            reason="Customer requested a manager",
            recent_messages=["user: let me speak to your manager"],
            db=db,
            escalation_type=EscalationType.HUMAN_REQUESTED,
        )

    assert mocks is not None
    assert conversation.escalation_status == EscalationStatus.PENDING.value
    db.add.assert_called_once()
    saved_escalation = db.add.call_args.args[0]
    assert isinstance(saved_escalation, Escalation)
    assert saved_escalation.conversation_id == conversation.id
    assert saved_escalation.reason == "Customer requested a manager"
    assert saved_escalation.status == EscalationStatus.PENDING.value
    db.commit.assert_awaited_once()
    mocks.send_message_with_inline_keyboard.assert_awaited_once()
    mocks.send_document.assert_not_awaited()
