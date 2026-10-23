from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

from src.schemas.common import PaginatedResponse


@pytest.mark.asyncio
async def test_admin_bot_rules_requires_admin_session(client: AsyncClient) -> None:
    response = await client.get("/api/v1/admin/bot-rules/rules")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_bot_rules_list_endpoint(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_bot_rules
    from src.schemas.admin import AdminBotRuleRead

    rule_id = uuid.uuid4()

    async def fake_list_rules(**kwargs: Any) -> PaginatedResponse:
        assert kwargs["search"] == "name"
        assert kwargs["status"] == "active"
        assert kwargs["page_size"] == 25
        return PaginatedResponse(
            items=[
                AdminBotRuleRead(
                    id=rule_id,
                    title="Ask for customer name",
                    type="hard_rule",
                    status="active",
                    priority=10,
                    scope="stage",
                    stage="greeting",
                    language="en",
                    segment=None,
                    instruction="If the customer name is unknown, ask how to address them.",
                    trigger_examples=["Hi"],
                    has_embedding=True,
                    created_by="admin",
                    updated_by="admin",
                    created_at=datetime(2026, 5, 8, 12, 0, 0),
                    updated_at=None,
                    archived_at=None,
                )
            ],
            total=1,
            page=1,
            page_size=25,
            pages=1,
        )

    monkeypatch.setattr(admin_bot_rules, "list_admin_bot_rules", fake_list_rules)

    response = await admin_client.get(
        "/api/v1/admin/bot-rules/rules?search=name&status=active&page_size=25"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["title"] == "Ask for customer name"
    assert payload["items"][0]["scope"] == "stage"


@pytest.mark.asyncio
async def test_admin_bot_rules_preview_endpoint(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_bot_rules
    from src.schemas.admin import AdminBotRuleApplied, AdminBotRulePreviewResponse

    rule_id = uuid.uuid4()

    async def fake_preview(**kwargs: Any) -> AdminBotRulePreviewResponse:
        assert kwargs["body"].message == "I need 20 chairs"
        return AdminBotRulePreviewResponse(
            applied_rules=[
                AdminBotRuleApplied(
                    id=rule_id,
                    title="Wholesale upsell",
                    type="upsell_rule",
                    priority=50,
                    scope="segment",
                    instruction="Mention bulk-friendly alternatives.",
                )
            ],
            prompt_block="[BOT OPERATING RULES]\n- Mention bulk-friendly alternatives.",
            rule_count=1,
        )

    monkeypatch.setattr(admin_bot_rules, "preview_admin_bot_rules", fake_preview)

    response = await admin_client.post(
        "/api/v1/admin/bot-rules/preview",
        json={
            "message": "I need 20 chairs",
            "stage": "solution",
            "language": "en",
            "segment": "Wholesale",
        },
    )

    assert response.status_code == 200
    assert response.json()["rule_count"] == 1
    assert "[BOT OPERATING RULES]" in response.json()["prompt_block"]


@pytest.mark.asyncio
async def test_create_admin_bot_rule_indexes_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.schemas.admin import AdminBotRuleWrite
    from src.services import admin_bot_rules

    class FakeDB:
        def __init__(self) -> None:
            self.added: list[Any] = []
            self.committed = False
            self.refreshed: object | None = None

        def add(self, row: object) -> None:
            self.added.append(row)

        async def commit(self) -> None:
            self.committed = True

        async def refresh(self, row: object) -> None:
            self.refreshed = row
            row.id = uuid.uuid4()
            row.created_at = datetime(2026, 5, 8, 12, 0, 0)

    class FakeEmbeddingEngine:
        async def embed_async(self, text: str) -> list[float]:
            assert "Ask for customer name" in text
            return [0.15] * 1024

    audit_calls: list[dict[str, Any]] = []

    async def fake_log_admin_action(*_: object, **kwargs: Any) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(admin_bot_rules, "EmbeddingEngine", FakeEmbeddingEngine)
    monkeypatch.setattr(admin_bot_rules, "log_admin_action", fake_log_admin_action)

    rule = await admin_bot_rules.create_admin_bot_rule(
        db=FakeDB(),
        body=AdminBotRuleWrite(
            title="Ask for customer name",
            type="hard_rule",
            status="active",
            priority=10,
            scope="stage",
            stage="greeting",
            language="en",
            segment=None,
            instruction="If customer_name is unknown, ask how to address them.",
            trigger_examples=["Hello", "Hi"],
        ),
        request=None,
    )

    assert rule.title == "Ask for customer name"
    assert rule.has_embedding is True
    assert audit_calls[0]["action"] == "bot_rule.create"
    assert audit_calls[0]["after"]["title"] == "Ask for customer name"


@pytest.mark.asyncio
async def test_update_admin_bot_rule_can_unarchive_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.models.bot_behavior_rule import BotBehaviorRule
    from src.schemas.admin import AdminBotRuleUpdate
    from src.services import admin_bot_rules

    rule_id = uuid.uuid4()
    archived_rule = BotBehaviorRule(
        id=rule_id,
        title="Archived rule",
        type="hard_rule",
        status="archived",
        priority=10,
        scope="global",
        stage=None,
        language="en",
        segment=None,
        instruction="Do not invent facts.",
        trigger_examples=["test"],
        created_by="admin",
        updated_by="admin",
        created_at=datetime(2026, 5, 8, 12, 0, 0),
        updated_at=datetime(2026, 5, 8, 12, 0, 0),
        archived_at=datetime(2026, 5, 8, 13, 0, 0),
    )

    class FakeDB:
        async def get(self, model: object, key: object) -> object | None:
            assert model is BotBehaviorRule
            assert key == rule_id
            return archived_rule

        async def commit(self) -> None:
            pass

        async def refresh(self, row: object) -> None:
            pass

    monkeypatch.setattr(admin_bot_rules, "log_admin_action", AsyncMock())

    updated = await admin_bot_rules.update_admin_bot_rule(
        db=FakeDB(),  # type: ignore[arg-type]
        rule_id=rule_id,
        body=AdminBotRuleUpdate(status="active"),
        request=None,
    )

    assert updated.status == "active"
    assert updated.archived_at is None
    assert archived_rule.archived_at is None
