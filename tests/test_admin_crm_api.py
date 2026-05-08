from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient

from src.schemas.common import PaginatedResponse


@pytest.mark.asyncio
async def test_admin_crm_requires_admin_session(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/crm/customers")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_crm_customers_endpoint_returns_client_cards(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_crm
    from src.schemas.admin import AdminCustomerListItem

    customer_id = uuid.uuid4()

    async def fake_list_customers(**kwargs: Any) -> PaginatedResponse:
        assert kwargs["search"] == "971"
        assert kwargs["status"] == "active"
        assert kwargs["page"] == 1
        assert kwargs["page_size"] == 25
        return PaginatedResponse(
            items=[
                AdminCustomerListItem(
                    phone="+971555000111",
                    customer_name="Noor Client",
                    latest_conversation_id=customer_id,
                    latest_message_at=datetime(2026, 5, 7, 12, 0, 0),
                    latest_message_preview="Здравствуйте",
                    conversation_count=2,
                    status="active",
                    sales_stage="qualifying",
                    language="en",
                    escalation_status="none",
                    deal_status="pending",
                    zoho_contact_id="z-contact",
                    zoho_deal_id="z-deal",
                    segment="horeca",
                    updated_at=datetime(2026, 5, 7, 12, 1, 0),
                )
            ],
            total=1,
            page=1,
            page_size=25,
            pages=1,
        )

    monkeypatch.setattr(admin_crm, "list_admin_customers", fake_list_customers)

    response = await admin_client.get(
        "/api/v1/admin/crm/customers?search=971&status=active&page_size=25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["phone"] == "+971555000111"
    assert payload["items"][0]["customer_name"] == "Noor Client"
    assert payload["items"][0]["conversation_count"] == 2
    assert payload["total"] == 1


@pytest.mark.asyncio
async def test_admin_crm_conversation_detail_returns_timeline(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_crm
    from src.schemas.admin import AdminConversationDetail, AdminTimelineMessage

    conversation_id = uuid.uuid4()
    message_id = uuid.uuid4()

    async def fake_detail(**kwargs: Any) -> AdminConversationDetail:
        assert kwargs["conversation_id"] == conversation_id
        return AdminConversationDetail(
            id=conversation_id,
            phone="+971555000111",
            customer_name="Noor Client",
            language="en",
            sales_stage="qualifying",
            status="active",
            escalation_status="none",
            deal_status="pending",
            deal_amount=1200.0,
            zoho_contact_id="z-contact",
            zoho_deal_id="z-deal",
            message_count=1,
            last_message_at=datetime(2026, 5, 7, 12, 0, 0),
            last_message_preview="Здравствуйте",
            updated_at=datetime(2026, 5, 7, 12, 1, 0),
            created_at=datetime(2026, 5, 7, 11, 0, 0),
            metadata={"source": "whatsapp"},
            timeline=[
                AdminTimelineMessage(
                    id=message_id,
                    role="user",
                    content="Здравствуйте",
                    message_type="text",
                    created_at=datetime(2026, 5, 7, 12, 0, 0),
                )
            ],
            escalations=[],
            quality_reviews=[],
            manager_reviews=[],
            feedback=[],
            outbound_audits=[],
            applied_bot_rules=[
                {
                    "id": "00000000-0000-0000-0000-000000000001",
                    "title": "Ask name",
                    "type": "hard_rule",
                    "priority": 10,
                    "scope": "stage",
                    "instruction": "Ask how to address the customer.",
                }
            ],
        )

    monkeypatch.setattr(admin_crm, "get_admin_conversation_detail", fake_detail)

    response = await admin_client.get(
        f"/api/v1/admin/crm/conversations/{conversation_id}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == str(conversation_id)
    assert payload["timeline"][0]["id"] == str(message_id)
    assert payload["timeline"][0]["content"] == "Здравствуйте"
    assert payload["applied_bot_rules"][0]["title"] == "Ask name"


@pytest.mark.asyncio
async def test_update_admin_conversation_writes_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.models.conversation import Conversation
    from src.schemas.admin import AdminConversationDetail, AdminConversationUpdate
    from src.services import admin_crm

    conversation_id = uuid.uuid4()
    conversation = Conversation(
        id=conversation_id,
        phone="+971555000111",
        customer_name="Old Name",
        status="active",
        sales_stage="greeting",
        escalation_status="none",
        language="en",
    )

    class FakeDB:
        def __init__(self) -> None:
            self.committed = False
            self.refreshed: object | None = None

        async def get(self, model: object, item_id: uuid.UUID) -> Conversation | None:
            assert item_id == conversation_id
            return conversation

        async def commit(self) -> None:
            self.committed = True

        async def refresh(self, row: object) -> None:
            self.refreshed = row

    audit_calls: list[dict[str, Any]] = []

    async def fake_log_admin_action(*_: object, **kwargs: Any) -> None:
        audit_calls.append(kwargs)

    async def fake_detail(*_: object, **__: object) -> AdminConversationDetail:
        return AdminConversationDetail(
            id=conversation_id,
            phone="+971555000111",
            customer_name="New Name",
            language="en",
            sales_stage="qualifying",
            status="closed",
            escalation_status="none",
            deal_status=None,
            deal_amount=None,
            zoho_contact_id=None,
            zoho_deal_id=None,
            message_count=0,
            created_at=datetime(2026, 5, 7, 11, 0, 0),
            updated_at=datetime(2026, 5, 7, 12, 0, 0),
            timeline=[],
            escalations=[],
            quality_reviews=[],
            manager_reviews=[],
            feedback=[],
            outbound_audits=[],
            applied_bot_rules=[],
        )

    monkeypatch.setattr(admin_crm, "log_admin_action", fake_log_admin_action)
    monkeypatch.setattr(admin_crm, "get_admin_conversation_detail", fake_detail)

    detail = await admin_crm.update_admin_conversation(
        db=FakeDB(),
        conversation_id=conversation_id,
        body=AdminConversationUpdate(
            status="closed",
            sales_stage="qualifying",
            customer_name="New Name",
        ),
        request=None,
    )

    assert detail.status == "closed"
    assert conversation.status == "closed"
    assert conversation.sales_stage == "qualifying"
    assert conversation.customer_name == "New Name"
    assert audit_calls[0]["action"] == "conversation.update"
    assert audit_calls[0]["before"]["status"] == "active"
    assert audit_calls[0]["after"]["status"] == "closed"


@pytest.mark.asyncio
async def test_admin_crm_audit_endpoint_returns_paginated_rows(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_crm
    from src.schemas.admin import AdminActionAuditRead

    audit_id = uuid.uuid4()

    async def fake_audit(**kwargs: Any) -> PaginatedResponse:
        assert kwargs["entity_type"] == "conversation"
        return PaginatedResponse(
            items=[
                AdminActionAuditRead(
                    id=audit_id,
                    actor="admin",
                    action="conversation.update",
                    entity_type="conversation",
                    entity_id="c-1",
                    request_path="/api/v1/admin/crm/conversations/c-1",
                    before={"status": "active"},
                    after={"status": "closed"},
                    metadata={"source": "crm"},
                    created_at=datetime(2026, 5, 7, 12, 0, 0),
                )
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

    monkeypatch.setattr(admin_crm, "list_admin_audit", fake_audit)

    response = await admin_client.get(
        "/api/v1/admin/crm/audit?entity_type=conversation"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["action"] == "conversation.update"
