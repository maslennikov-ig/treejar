from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest


def test_admin_audit_payload_masks_nested_sensitive_values() -> None:
    from src.services.admin_audit import MASKED_VALUE, mask_admin_audit_payload

    payload = {
        "api_key": "secret-api-key",
        "plain": "visible",
        "nested": {
            "accessToken": "secret-token",
            "safe": "kept",
        },
        "items": [
            {"password": "secret-password"},
            {"name": "Noor"},
        ],
    }

    masked = mask_admin_audit_payload(payload)

    assert masked["api_key"] == MASKED_VALUE
    assert masked["plain"] == "visible"
    assert masked["nested"]["accessToken"] == MASKED_VALUE
    assert masked["nested"]["safe"] == "kept"
    assert masked["items"][0]["password"] == MASKED_VALUE
    assert masked["items"][1]["name"] == "Noor"
    assert payload["api_key"] == "secret-api-key"


@pytest.mark.asyncio
async def test_log_admin_action_creates_masked_row_without_commit() -> None:
    from src.models.admin_action_audit import AdminActionAudit
    from src.services.admin_audit import MASKED_VALUE, log_admin_action

    class FakeRequest:
        class URL:
            path = "/api/v1/admin/crm/conversations/123"

        url = URL()

    class FakeDB:
        def __init__(self) -> None:
            self.added: list[Any] = []
            self.flushed = False

        def add(self, row: Any) -> None:
            self.added.append(row)

        async def flush(self) -> None:
            self.flushed = True

    db = FakeDB()
    conversation_id = uuid.uuid4()

    row = await log_admin_action(
        db,
        action="conversation.update",
        entity_type="conversation",
        entity_id=conversation_id,
        before={"status": "active", "authorization": "Bearer old"},
        after={"status": "closed", "api_token": "new-token"},
        request=FakeRequest(),
        metadata={"session_token": "admin-session"},
    )

    assert isinstance(row, AdminActionAudit)
    assert db.added == [row]
    assert db.flushed is True
    assert row.actor == "admin"
    assert row.action == "conversation.update"
    assert row.entity_type == "conversation"
    assert row.entity_id == str(conversation_id)
    assert row.request_path == "/api/v1/admin/crm/conversations/123"
    assert row.before == {"status": "active", "authorization": MASKED_VALUE}
    assert row.after == {"status": "closed", "api_token": MASKED_VALUE}
    assert row.metadata_ == {"session_token": MASKED_VALUE}


def test_admin_action_audit_read_maps_metadata_alias() -> None:
    from src.models.admin_action_audit import AdminActionAudit
    from src.schemas.admin import AdminActionAuditRead

    created_at = datetime(2026, 5, 7, 12, 0, 0)
    row = AdminActionAudit(
        id=uuid.uuid4(),
        actor="admin",
        action="knowledge_base.update",
        entity_type="knowledge_base",
        entity_id="kb-1",
        request_path="/api/v1/admin/knowledge-base/kb-1",
        before={"content": "old"},
        after={"content": "new"},
        metadata_={"reason": "manual edit"},
        created_at=created_at,
    )

    payload = AdminActionAuditRead.model_validate(row)

    assert payload.metadata == {"reason": "manual edit"}
    assert payload.model_dump()["metadata"] == {"reason": "manual edit"}
