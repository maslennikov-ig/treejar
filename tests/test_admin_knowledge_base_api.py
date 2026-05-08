from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient

from src.schemas.common import PaginatedResponse


@pytest.mark.asyncio
async def test_admin_knowledge_base_requires_admin_session(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/admin/knowledge-base/entries")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_knowledge_base_list_endpoint(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_knowledge_base
    from src.schemas.admin import AdminKnowledgeBaseRead

    entry_id = uuid.uuid4()

    async def fake_list_entries(**kwargs: Any) -> PaginatedResponse:
        assert kwargs["search"] == "delivery"
        assert kwargs["language"] == "en"
        return PaginatedResponse(
            items=[
                AdminKnowledgeBaseRead(
                    id=entry_id,
                    source="manual",
                    title="Delivery time",
                    content="Delivery takes 3-5 business days.",
                    language="en",
                    category="faq",
                    has_embedding=True,
                    is_auto_generated=False,
                    original_question=None,
                    manager_draft=None,
                    created_at=datetime(2026, 5, 7, 12, 0, 0),
                    updated_at=None,
                    deleted_at=None,
                    deleted_by=None,
                )
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

    monkeypatch.setattr(
        admin_knowledge_base, "list_admin_kb_entries", fake_list_entries
    )

    response = await admin_client.get(
        "/api/v1/admin/knowledge-base/entries?search=delivery&language=en"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["title"] == "Delivery time"


@pytest.mark.asyncio
async def test_create_admin_knowledge_base_entry_indexes_and_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.schemas.admin import AdminKnowledgeBaseWrite
    from src.services import admin_knowledge_base

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
            row.created_at = datetime(2026, 5, 7, 12, 0, 0)

    class FakeEmbeddingEngine:
        async def embed_async(self, text: str) -> list[float]:
            assert "Delivery" in text
            return [0.1] * 1024

    audit_calls: list[dict[str, Any]] = []

    async def fake_log_admin_action(*_: object, **kwargs: Any) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(admin_knowledge_base, "EmbeddingEngine", FakeEmbeddingEngine)
    monkeypatch.setattr(admin_knowledge_base, "log_admin_action", fake_log_admin_action)

    entry = await admin_knowledge_base.create_admin_kb_entry(
        db=FakeDB(),
        body=AdminKnowledgeBaseWrite(
            source="manual",
            title="Delivery time",
            content="Delivery takes 3-5 business days.",
            language="en",
            category="faq",
        ),
        request=None,
    )

    assert entry.title == "Delivery time"
    assert entry.has_embedding is True
    assert audit_calls[0]["action"] == "knowledge_base.create"
    assert audit_calls[0]["after"]["title"] == "Delivery time"


@pytest.mark.asyncio
async def test_admin_knowledge_base_preview_reports_guard_and_duplicate_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.schemas.admin import AdminKnowledgeBaseWrite
    from src.services import admin_knowledge_base

    class FakeEmbeddingEngine:
        async def embed_async(self, text: str) -> list[float]:
            assert "guarantee" in text.lower()
            return [0.2] * 1024

    class FakeResult:
        def first(self) -> object:
            class Nearest:
                distance = 0.05

            return Nearest()

    class FakeDB:
        async def execute(self, _stmt: object) -> FakeResult:
            return FakeResult()

    monkeypatch.setattr(admin_knowledge_base, "EmbeddingEngine", FakeEmbeddingEngine)

    preview = await admin_knowledge_base.preview_admin_kb_entry(
        db=FakeDB(),
        body=AdminKnowledgeBaseWrite(
            source="manual",
            title="Refunds",
            content="We always guarantee a refund with no questions asked.",
            language="en",
            category="faq",
        ),
    )

    assert preview.embedding_ready is True
    assert preview.duplicate is True
    assert preview.duplicate_similarity == pytest.approx(0.95)
    assert "absolute_claim" in preview.unsafe_reasons


@pytest.mark.asyncio
async def test_admin_knowledge_base_candidates_endpoint(
    admin_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.api.v1 import admin_knowledge_base
    from src.schemas.admin import AdminKnowledgeBaseCandidate

    candidate_id = uuid.uuid4()

    async def fake_candidates(**kwargs: Any) -> PaginatedResponse:
        assert kwargs["status"] == "needs_confirmation"
        return PaginatedResponse(
            items=[
                AdminKnowledgeBaseCandidate(
                    id=candidate_id,
                    question="What is delivery time?",
                    answer="Delivery takes 3-5 business days.",
                    language="en",
                    confidence=0.95,
                    status="needs_confirmation",
                    guard_reasons=[],
                    duplicate_similarity=None,
                    original_question="What is delivery time?",
                    manager_draft="3-5 days",
                    customer_message="3-5 business days",
                    metadata={},
                    created_at=datetime(2026, 5, 7, 12, 0, 0),
                    updated_at=None,
                )
            ],
            total=1,
            page=1,
            page_size=20,
            pages=1,
        )

    monkeypatch.setattr(
        admin_knowledge_base,
        "list_admin_kb_candidates",
        fake_candidates,
    )

    response = await admin_client.get(
        "/api/v1/admin/knowledge-base/candidates?status=needs_confirmation"
    )

    assert response.status_code == 200
    assert response.json()["items"][0]["question"] == "What is delivery time?"
