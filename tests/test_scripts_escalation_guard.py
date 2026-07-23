from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from scripts.escalation_guard import (
    ManifestValidationError,
    _manifest_digest,
    apply_manifest_in_transaction,
    apply_reconciliation_manifest,
    audit_pending_escalations,
    build_reconciliation_manifest,
    load_reconciliation_manifest,
    maybe_suppress_external_escalation_alerts,
)

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
        metadata_={"inbound_channel_phone": "+971551220665"},
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


def _pending_pair(
    *,
    conversation_status: str,
    conversation_escalation_status: str,
    age_days: int,
    phone: str = "+971500000000",
) -> tuple[Escalation, Conversation]:
    now = datetime(2026, 7, 23, tzinfo=UTC)
    conversation = Conversation(
        id=uuid4(),
        phone=phone,
        sales_stage=SalesStage.GREETING.value,
        status=conversation_status,
        escalation_status=conversation_escalation_status,
        language="en",
        metadata_={},
    )
    escalation = Escalation(
        id=uuid4(),
        conversation_id=conversation.id,
        reason="redacted from manifest",
        status=EscalationStatus.PENDING.value,
        created_at=now - timedelta(days=age_days),
    )
    return escalation, conversation


def test_manifest_contains_every_classification_but_only_exact_safe_actions() -> None:
    now = datetime(2026, 7, 23, tzinfo=UTC)
    active_pending = _pending_pair(
        conversation_status="active",
        conversation_escalation_status="pending",
        age_days=45,
    )
    stale_none = _pending_pair(
        conversation_status="active",
        conversation_escalation_status="none",
        age_days=45,
    )
    closed_resolved = _pending_pair(
        conversation_status="closed",
        conversation_escalation_status="resolved",
        age_days=8,
    )
    manual_takeover = _pending_pair(
        conversation_status="active",
        conversation_escalation_status="manual_takeover",
        age_days=45,
    )

    manifest = build_reconciliation_manifest(
        [active_pending, stale_none, closed_resolved, manual_takeover],
        now=now,
        stale_after_days=30,
    )

    assert manifest["schema_version"] == "treejar-escalation-reconciliation/v1"
    assert manifest["summary"]["total_pending"] == 4
    assert len(manifest["records"]) == 4
    assert {action["escalation_id"] for action in manifest["actions"]} == {
        str(stale_none[0].id),
        str(closed_resolved[0].id),
    }
    encoded_manifest = json.dumps(manifest)
    assert "phone" not in encoded_manifest
    assert "redacted from manifest" not in encoded_manifest


def test_archived_manifest_detects_tampering(tmp_path: Path) -> None:
    pair = _pending_pair(
        conversation_status="closed",
        conversation_escalation_status="resolved",
        age_days=45,
    )
    manifest = build_reconciliation_manifest(
        [pair],
        now=datetime(2026, 7, 23, tzinfo=UTC),
        stale_after_days=30,
    )
    manifest["actions"][0]["conversation_id"] = str(uuid4())
    path = tmp_path / "audit.json"
    path.write_text(json.dumps(manifest))

    with pytest.raises(ManifestValidationError, match="digest"):
        load_reconciliation_manifest(path)


def test_apply_rejects_symlinked_manifest(tmp_path: Path) -> None:
    pair = _pending_pair(
        conversation_status="closed",
        conversation_escalation_status="resolved",
        age_days=45,
    )
    manifest = build_reconciliation_manifest(
        [pair],
        now=datetime(2026, 7, 23, tzinfo=UTC),
        stale_after_days=30,
    )
    target = tmp_path / "approved-target.json"
    target.write_text(json.dumps(manifest))
    link = tmp_path / "approved.json"
    link.symlink_to(target)

    with pytest.raises(ManifestValidationError, match="regular file"):
        load_reconciliation_manifest(link)


@pytest.mark.asyncio
async def test_audit_is_select_only() -> None:
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    db.execute.return_value = result

    rows = await audit_pending_escalations(db)

    assert rows == []
    db.execute.assert_awaited_once()
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()
    db.add.assert_not_called()


class _SessionContext:
    def __init__(self, db: AsyncMock) -> None:
        self.db = db

    async def __aenter__(self) -> AsyncMock:
        return self.db

    async def __aexit__(self, *args: object) -> None:
        return None


@pytest.mark.asyncio
async def test_exact_manifest_apply_is_idempotent() -> None:
    escalation, conversation = _pending_pair(
        conversation_status="closed",
        conversation_escalation_status="resolved",
        age_days=45,
    )
    manifest = build_reconciliation_manifest(
        [(escalation, conversation)],
        now=datetime(2026, 7, 23, tzinfo=UTC),
        stale_after_days=30,
    )
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(escalation, conversation)]
    db.execute.return_value = result

    def session_factory() -> _SessionContext:
        return _SessionContext(db)

    first = await apply_manifest_in_transaction(session_factory, manifest)
    second = await apply_manifest_in_transaction(session_factory, manifest)

    assert first["changed_escalation_ids"] == [str(escalation.id)]
    assert second["changed_escalation_ids"] == []
    assert second["already_applied_escalation_ids"] == [str(escalation.id)]
    assert db.commit.await_count == 2
    db.rollback.assert_not_awaited()


@pytest.mark.asyncio
async def test_manifest_precondition_failure_rolls_back_whole_transaction() -> None:
    escalation, conversation = _pending_pair(
        conversation_status="closed",
        conversation_escalation_status="resolved",
        age_days=45,
    )
    manifest = build_reconciliation_manifest(
        [(escalation, conversation)],
        now=datetime(2026, 7, 23, tzinfo=UTC),
        stale_after_days=30,
    )
    conversation.status = "active"
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(escalation, conversation)]
    db.execute.return_value = result

    def session_factory() -> _SessionContext:
        return _SessionContext(db)

    with pytest.raises(ManifestValidationError, match="precondition"):
        await apply_manifest_in_transaction(session_factory, manifest)

    db.commit.assert_not_awaited()
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_rejects_fabricated_action_for_human_owned_pending_row() -> None:
    escalation, conversation = _pending_pair(
        conversation_status="active",
        conversation_escalation_status=EscalationStatus.PENDING.value,
        age_days=45,
    )
    manifest = build_reconciliation_manifest(
        [(escalation, conversation)],
        now=datetime(2026, 7, 23, tzinfo=UTC),
        stale_after_days=30,
    )
    expected = {
        "escalation_status": EscalationStatus.PENDING.value,
        "conversation_status": "active",
        "conversation_escalation_status": EscalationStatus.PENDING.value,
    }
    manifest["actions"] = [
        {
            "escalation_id": str(escalation.id),
            "conversation_id": str(conversation.id),
            "expected": expected,
            "target": {
                **expected,
                "escalation_status": EscalationStatus.RESOLVED.value,
            },
        }
    ]
    manifest["digest"] = _manifest_digest(manifest)
    db = AsyncMock()
    result = MagicMock()
    result.all.return_value = [(escalation, conversation)]
    db.execute.return_value = result

    with pytest.raises(ManifestValidationError, match="not safe to resolve"):
        await apply_reconciliation_manifest(db, manifest)

    assert escalation.status == EscalationStatus.PENDING.value
