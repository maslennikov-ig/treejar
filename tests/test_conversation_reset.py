from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.conversation import Conversation
from src.models.escalation import Escalation


class _ScalarResult:
    def __init__(self, values: list[object] | None = None, scalar: int | None = None):
        self._values = values or []
        self._scalar = scalar

    def scalars(self) -> _ScalarResult:
        return self

    def all(self) -> list[object]:
        return self._values

    def scalar_one(self) -> int:
        assert self._scalar is not None
        return self._scalar


def _conversation(
    *,
    phone: str,
    updated_at: datetime,
    escalation_status: str = "pending",
    metadata: dict | None = None,
) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        phone=phone,
        language="en",
        sales_stage="solution",
        status="active",
        escalation_status=escalation_status,
        customer_name="Existing Customer",
        zoho_contact_id="z-contact",
        zoho_deal_id="z-deal",
        metadata_=metadata or {"kept": "old-state"},
        created_at=updated_at - timedelta(hours=1),
        updated_at=updated_at,
    )


@pytest.mark.asyncio
async def test_preview_counts_exact_phone_variants_without_mutation() -> None:
    from src.services.conversation_reset import build_reset_preview

    now = datetime.now(UTC)
    latest = _conversation(phone="+79262810921", updated_at=now)
    older = _conversation(phone="79262810921", updated_at=now - timedelta(minutes=5))
    db = AsyncMock()
    db.execute.side_effect = [
        _ScalarResult([latest, older]),
        _ScalarResult(scalar=7),
        _ScalarResult(scalar=2),
    ]

    preview = await build_reset_preview(db, "+7 926 281-09-21")

    assert preview.phone == "+79262810921"
    assert preview.conversation_count == 2
    assert preview.latest_conversation_id == latest.id
    assert preview.message_count == 7
    assert preview.pending_escalation_count == 2
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_archives_conversations_and_creates_blank_active_conversation() -> (
    None
):
    from src.services.conversation_reset import execute_conversation_reset

    now = datetime.now(UTC)
    latest = _conversation(phone="+79262810921", updated_at=now)
    older = _conversation(phone="79262810921", updated_at=now - timedelta(minutes=5))
    pending = Escalation(
        id=uuid.uuid4(),
        conversation_id=latest.id,
        reason="net 30",
        status="pending",
    )
    in_progress = Escalation(
        id=uuid.uuid4(),
        conversation_id=older.id,
        reason="manager",
        status="in_progress",
    )
    db = AsyncMock()
    db.add = MagicMock()
    db.execute.side_effect = [
        _ScalarResult([latest, older]),
        _ScalarResult([pending, in_progress]),
    ]

    result = await execute_conversation_reset(
        db,
        "+7 926 281-09-21",
        requested_by_telegram_user_id=12345,
    )

    assert result.archived_count == 2
    assert result.new_conversation.phone == "+79262810921"
    assert result.new_conversation.sales_stage == "greeting"
    assert result.new_conversation.status == "active"
    assert result.new_conversation.escalation_status == "none"
    assert result.new_conversation.customer_name is None
    assert result.new_conversation.zoho_contact_id is None
    assert result.new_conversation.zoho_deal_id is None
    assert result.new_conversation.metadata_["reset_source"] == "telegram"
    assert result.new_conversation.metadata_["reset_from_conversation_ids"] == [
        str(latest.id),
        str(older.id),
    ]
    assert latest.phone.startswith("+79262810921#archived-")
    assert older.phone.startswith("79262810921#archived-")
    assert latest.status == "closed"
    assert older.status == "closed"
    assert latest.escalation_status == "resolved"
    assert older.escalation_status == "resolved"
    assert latest.metadata_["original_phone"] == "+79262810921"
    assert older.metadata_["original_phone"] == "79262810921"
    assert latest.metadata_["reset_by_telegram_user_id"] == 12345
    assert pending.status == "resolved"
    assert in_progress.status == "resolved"
    db.add.assert_called_once_with(result.new_conversation)
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_is_noop_when_no_conversations_exist() -> None:
    from src.services.conversation_reset import execute_conversation_reset

    db = AsyncMock()
    db.execute.return_value = _ScalarResult([])

    result = await execute_conversation_reset(
        db,
        "+79262810921",
        requested_by_telegram_user_id=12345,
    )

    assert result.archived_count == 0
    assert result.new_conversation is None
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
