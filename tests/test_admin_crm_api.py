from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
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
                    latest_message_preview="Hello",
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
            last_message_preview="Hello",
            updated_at=datetime(2026, 5, 7, 12, 1, 0),
            created_at=datetime(2026, 5, 7, 11, 0, 0),
            metadata={"source": "whatsapp"},
            timeline=[
                AdminTimelineMessage(
                    id=message_id,
                    role="user",
                    content="Hello",
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
    assert payload["timeline"][0]["content"] == "Hello"
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
async def test_admin_bot_quality_review_respects_disabled_ai_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.services import admin_crm

    evaluate_mock = AsyncMock(side_effect=AssertionError("LLM should not run"))

    monkeypatch.setattr(
        admin_crm,
        "conversation_already_reviewed",
        AsyncMock(return_value=False),
    )
    monkeypatch.setattr(admin_crm, "evaluate_conversation", evaluate_mock)

    class FakeResult:
        def scalar_one_or_none(self) -> object | None:
            return None

    class FakeDB:
        async def execute(self, _stmt: object) -> FakeResult:
            return FakeResult()

    with pytest.raises(HTTPException) as exc_info:
        await admin_crm.run_admin_bot_quality_review(
            db=FakeDB(),
            conversation_id=uuid.uuid4(),
            request=None,
        )

    assert exc_info.value.status_code == 409
    assert "Bot QA" in str(exc_info.value.detail)
    assert "disabled" in str(exc_info.value.detail)
    evaluate_mock.assert_not_awaited()


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


@pytest.mark.asyncio
async def test_admin_crm_customers_forwards_drilldown_filters(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_crm

    captured: dict[str, Any] = {}

    async def fake_list_customers(**kwargs: Any) -> PaginatedResponse:
        captured.update(kwargs)
        return PaginatedResponse(items=[], total=0, page=1, page_size=20, pages=0)

    monkeypatch.setattr(admin_crm, "list_admin_customers", fake_list_customers)

    response = await admin_client.get(
        "/api/v1/admin/crm/customers?has_deal=true&target_only=false&stage=unknown"
    )

    assert response.status_code == 200
    assert captured["has_deal"] is True
    assert captured["target_only"] is False
    assert captured["stage"] == "unknown"


def test_conversation_filters_support_deal_target_and_unknown_stage() -> None:
    from sqlalchemy.dialects import postgresql

    from src.services.admin_crm import _conversation_filters

    clauses = _conversation_filters(
        search=None,
        status=None,
        stage="unknown",
        language=None,
        escalation=None,
        has_deal=True,
        target_only=True,
    )
    compiled = [
        str(
            clause.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for clause in clauses
    ]
    joined = " | ".join(compiled)
    assert "sales_stage IS NULL" in joined
    assert "zoho_deal_id IS NOT NULL" in joined
    assert "'active', 'completed'" in joined

    any_esc_clauses = _conversation_filters(
        search=None,
        status=None,
        stage=None,
        language=None,
        escalation="any",
    )
    any_esc_sql = " | ".join(
        str(
            clause.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for clause in any_esc_clauses
    )
    assert "escalation_status != 'none'" in any_esc_sql

    open_esc_clauses = _conversation_filters(
        search=None,
        status=None,
        stage=None,
        language=None,
        escalation="open",
    )
    open_esc_sql = " | ".join(
        str(
            clause.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for clause in open_esc_clauses
    )
    assert "'pending', 'in_progress', 'manual_takeover'" in open_esc_sql


@pytest.mark.asyncio
async def test_admin_crm_audit_forwards_actor_and_expands_bot_rule_alias(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.dialects import postgresql

    from src.api.v1 import admin_crm as admin_crm_api
    from src.services import admin_crm as admin_crm_service

    captured_api: dict[str, Any] = {}

    async def fake_audit(**kwargs: Any) -> PaginatedResponse:
        captured_api.update(kwargs)
        return PaginatedResponse(items=[], total=0, page=1, page_size=20, pages=0)

    monkeypatch.setattr(admin_crm_api, "list_admin_audit", fake_audit)

    resp = await admin_client.get(
        "/api/v1/admin/crm/audit?entity_type=bot_behavior_rule&actor=telegram:777"
    )
    assert resp.status_code == 200
    assert captured_api["entity_type"] == "bot_behavior_rule"
    assert captured_api["actor"] == "telegram:777"

    executed_sql: list[str] = []

    class FakeResult:
        def scalar_one(self) -> int:
            return 0

        def scalars(self) -> FakeResult:
            return self

        def all(self) -> list[object]:
            return []

    class FakeAuditDB:
        async def execute(self, stmt: object) -> FakeResult:
            executed_sql.append(
                str(
                    stmt.compile(  # type: ignore[attr-defined]
                        dialect=postgresql.dialect(),
                        compile_kwargs={"literal_binds": True},
                    )
                )
            )
            return FakeResult()

    result = await admin_crm_service.list_admin_audit(
        db=FakeAuditDB(),  # type: ignore[arg-type]
        action=None,
        entity_type="bot_behavior_rule",
        actor="telegram:777",
        page=1,
        page_size=20,
    )
    assert result.total == 0
    assert any(
        "'bot_behavior_rule', 'bot_rule'" in sql and "telegram:777" in sql
        for sql in executed_sql
    )


@pytest.mark.asyncio
async def test_admin_crm_conversation_patch_validates_enums_and_preserves_omitted_fields(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.models.conversation import Conversation
    from src.schemas.admin import AdminConversationDetail
    from src.services import admin_crm

    conversation_id = uuid.uuid4()
    conversation = Conversation(
        id=conversation_id,
        phone="+971555000222",
        customer_name="Legacy Client",
        status="active",
        sales_stage="quoting",
        escalation_status="none",
        deal_status="New Lead",
        language="en",
    )

    class FakeDB:
        async def get(self, _model: object, item_id: uuid.UUID) -> Conversation | None:
            return conversation if item_id == conversation_id else None

        async def commit(self) -> None:
            return None

        async def refresh(self, _row: object) -> None:
            return None

    async def fake_get_db():
        yield FakeDB()

    async def fake_log(*_: object, **__: object) -> None:
        return None

    async def fake_detail(_db: object, _cid: uuid.UUID) -> AdminConversationDetail:
        return AdminConversationDetail(
            id=conversation.id,
            phone=conversation.phone,
            customer_name=conversation.customer_name,
            language=conversation.language,
            sales_stage=conversation.sales_stage,
            status=conversation.status,
            escalation_status=conversation.escalation_status,
            deal_status=conversation.deal_status,
            created_at=datetime(2026, 5, 7, 11, 0, 0),
            updated_at=datetime(2026, 5, 7, 12, 0, 0),
        )

    from src.core.database import get_db
    from src.main import app

    monkeypatch.setattr(admin_crm, "log_admin_action", fake_log)
    monkeypatch.setattr(admin_crm, "get_admin_conversation_detail", fake_detail)
    app.dependency_overrides[get_db] = fake_get_db
    try:
        # 1. Partial PATCH leaves omitted fields (including legacy "New Lead") untouched
        ok_partial = await admin_client.patch(
            f"/api/v1/admin/crm/conversations/{conversation_id}",
            json={"status": "paused"},
        )
        assert ok_partial.status_code == 200
        assert ok_partial.json()["status"] == "paused"
        assert ok_partial.json()["deal_status"] == "New Lead"
        assert conversation.status == "paused"
        assert conversation.deal_status == "New Lead"

        # 2. Invalid enum values on write are rejected with 422
        for bad_payload in (
            {"status": "not-a-status"},
            {"deal_status": "New Lead"},
            {"deal_status": "arbitrary_garbage"},
            {"escalation_status": "unknown_escalation"},
            {"sales_stage": "invalid_stage"},
            {"status": None},
        ):
            bad_resp = await admin_client.patch(
                f"/api/v1/admin/crm/conversations/{conversation_id}",
                json=bad_payload,
            )
            assert bad_resp.status_code == 422, bad_payload

        # 3. Valid DealStatus and empty string clearing deal_status both succeed
        ok_deal = await admin_client.patch(
            f"/api/v1/admin/crm/conversations/{conversation_id}",
            json={"deal_status": "in_progress", "escalation_status": "pending"},
        )
        assert ok_deal.status_code == 200
        assert conversation.deal_status == "in_progress"
        assert conversation.escalation_status == "pending"

        clear_deal = await admin_client.patch(
            f"/api/v1/admin/crm/conversations/{conversation_id}",
            json={"deal_status": "   "},
        )
        assert clear_deal.status_code == 200
        assert conversation.deal_status is None
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.asyncio
async def test_list_admin_escalations_ignores_all_and_empty_status_filters() -> None:
    from sqlalchemy.dialects import postgresql

    from src.services.admin_crm import list_admin_escalations

    executed_sql: list[str] = []

    class FakeResult:
        def scalar_one(self) -> int:
            return 0

        def all(self) -> list[object]:
            return []

    class FakeDB:
        async def execute(self, stmt: object) -> FakeResult:
            executed_sql.append(
                str(
                    stmt.compile(  # type: ignore[attr-defined]
                        dialect=postgresql.dialect(),
                        compile_kwargs={"literal_binds": True},
                    )
                )
            )
            return FakeResult()

    for noop_status in ("all", "ALL", "", "   ", None):
        executed_sql.clear()
        res = await list_admin_escalations(
            db=FakeDB(),  # type: ignore[arg-type]
            status=noop_status,
        )
        assert res.total == 0
        assert all("WHERE" not in sql for sql in executed_sql)

    executed_sql.clear()
    await list_admin_escalations(
        db=FakeDB(),  # type: ignore[arg-type]
        status="OPEN",
    )
    assert any(
        "'pending', 'in_progress', 'manual_takeover'" in sql for sql in executed_sql
    )


@pytest.mark.asyncio
async def test_list_admin_customers_and_conversations_batch_queries_and_avoid_metadata_blob() -> (
    None
):
    """AD-18 / P2-3: customers and conversations paginate in SQL, batch message summaries in 1 query, and skip full metadata blob."""
    from decimal import Decimal
    from types import SimpleNamespace

    from sqlalchemy.dialects import postgresql, sqlite

    from src.services.admin_crm import (
        list_admin_conversations,
        list_admin_customers,
    )

    c1_id = uuid.uuid4()
    c2_id = uuid.uuid4()
    now = datetime(2026, 5, 7, 12, 0, 0)

    customer_rows = [
        SimpleNamespace(
            id=c1_id,
            phone="+971500000001",
            customer_name="Alice",
            status="active",
            sales_stage="qualifying",
            language="en",
            escalation_status="none",
            deal_status="in_progress",
            zoho_contact_id="zc-1",
            zoho_deal_id="zd-1",
            updated_at=now,
            created_at=now,
            segment="b2b",
            conversation_count=3,
            rn=1,
        ),
        SimpleNamespace(
            id=c2_id,
            phone="+971500000002",
            customer_name="Bob",
            status="paused",
            sales_stage="greeting",
            language="ar",
            escalation_status="pending",
            deal_status=None,
            zoho_contact_id=None,
            zoho_deal_id=None,
            updated_at=now,
            created_at=now,
            segment=None,
            conversation_count=1,
            rn=1,
        ),
    ]
    summary_rows = [
        SimpleNamespace(
            conversation_id=c1_id,
            message_count=5,
            created_at=now,
            content="Looking for 10 executive desks",
        )
    ]

    pg_queries: list[str] = []

    class FakeResult:
        def __init__(
            self, scalar: int | None = None, rows: list[Any] | None = None
        ) -> None:
            self._scalar = scalar
            self._rows = rows or []

        def scalar_one(self) -> int:
            assert self._scalar is not None
            return self._scalar

        def all(self) -> list[Any]:
            return list(self._rows)

    class FakeCustomerDB:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, stmt: object) -> FakeResult:
            # Must compile cleanly on both PostgreSQL and SQLite
            pg_sql = str(stmt.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]
            _ = str(stmt.compile(dialect=sqlite.dialect()))  # type: ignore[attr-defined]
            pg_queries.append(pg_sql)
            self.calls += 1
            if self.calls == 1:
                return FakeResult(scalar=12)
            if self.calls == 2:
                return FakeResult(rows=customer_rows)
            return FakeResult(rows=summary_rows)

    cust_db = FakeCustomerDB()
    cust_res = await list_admin_customers(
        db=cust_db,  # type: ignore[arg-type]
        page=2,
        page_size=2,
    )

    assert cust_db.calls == 3  # count + ranked page + 1 batched message summary query
    assert cust_res.total == 12
    assert cust_res.pages == 6
    assert len(cust_res.items) == 2
    assert cust_res.items[0].conversation_count == 3
    assert cust_res.items[0].segment == "b2b"
    assert cust_res.items[0].latest_message_preview == "Looking for 10 executive desks"
    assert cust_res.items[1].latest_message_preview is None
    assert "count(DISTINCT conversations.phone)" in pg_queries[0]
    assert "row_number() OVER (PARTITION BY conversations.phone" in pg_queries[1]
    assert "LIMIT" in pg_queries[1] and "OFFSET" in pg_queries[1]
    assert "conversations.metadata AS" not in pg_queries[1]
    assert "PARTITION BY messages.conversation_id" in pg_queries[2]

    conv_rows = [
        SimpleNamespace(
            id=c1_id,
            phone="+971500000001",
            customer_name="Alice",
            language="en",
            sales_stage="qualifying",
            status="active",
            escalation_status="none",
            deal_status="in_progress",
            deal_amount=Decimal("4500.50"),
            zoho_contact_id="zc-1",
            zoho_deal_id="zd-1",
            created_at=now,
            updated_at=now,
            meta_source="whatsapp",
            meta_segment="b2b",
            meta_utm={"campaign": "spring"},
            meta_order=None,
            meta_order_metadata={"so_number": "SO-101"},
            meta_sale_order=None,
            meta_sale_order_metadata=None,
        ),
        SimpleNamespace(
            id=c2_id,
            phone="+971500000002",
            customer_name="Bob",
            language="ar",
            sales_stage="greeting",
            status="paused",
            escalation_status="pending",
            deal_status=None,
            deal_amount=None,
            zoho_contact_id=None,
            zoho_deal_id=None,
            created_at=now,
            updated_at=now,
            meta_source=None,
            meta_segment=None,
            meta_utm=None,
            meta_order=None,
            meta_order_metadata=None,
            meta_sale_order=None,
            meta_sale_order_metadata=None,
        ),
    ]

    pg_queries.clear()

    class FakeConvDB:
        def __init__(self) -> None:
            self.calls = 0

        async def execute(self, stmt: object) -> FakeResult:
            pg_sql = str(stmt.compile(dialect=postgresql.dialect()))  # type: ignore[attr-defined]
            _ = str(stmt.compile(dialect=sqlite.dialect()))  # type: ignore[attr-defined]
            pg_queries.append(pg_sql)
            self.calls += 1
            if self.calls == 1:
                return FakeResult(scalar=2)
            if self.calls == 2:
                return FakeResult(rows=conv_rows)
            return FakeResult(rows=summary_rows)

    conv_db = FakeConvDB()
    conv_res = await list_admin_conversations(
        db=conv_db,  # type: ignore[arg-type]
        page=1,
        page_size=20,
    )

    assert conv_db.calls == 3  # count + page rows + 1 batched message summary query
    assert len(conv_res.items) == 2
    assert conv_res.items[0].message_count == 5
    assert conv_res.items[0].deal_amount == 4500.50
    assert conv_res.items[0].source == "whatsapp"
    assert conv_res.items[0].segment == "b2b"
    assert conv_res.items[0].utm == {"campaign": "spring"}
    assert conv_res.items[0].order_metadata == {"so_number": "SO-101"}
    assert conv_res.items[0].metadata is None
    assert conv_res.items[1].message_count == 0
    assert "conversations.metadata," not in pg_queries[1]
