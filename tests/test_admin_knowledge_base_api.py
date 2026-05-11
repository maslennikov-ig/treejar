from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import IntegrityError

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


@pytest.mark.asyncio
async def test_approve_admin_kb_candidate_uses_collision_safe_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Approving a candidate should not 500 on an existing auto-FAQ title."""
    from src.models.knowledge_base import KnowledgeBase
    from src.models.knowledge_base_candidate import KnowledgeBaseCandidate
    from src.services import admin_knowledge_base

    candidate_id = uuid.uuid4()
    question = "QA disposable FAQ candidate 2026051110008"
    candidate = KnowledgeBaseCandidate(
        id=candidate_id,
        question=question,
        answer="This is a disposable QA answer.",
        language="en",
        confidence=0.95,
        status="needs_confirmation",
        guard_reasons=[],
        duplicate_similarity=None,
        original_question=question,
        manager_draft="Disposable QA answer",
        customer_message="Disposable QA answer",
        metadata_={"qa_run_id": "2026051110008"},
    )

    class FakeScalarResult:
        def scalar_one_or_none(self) -> object:
            return KnowledgeBase(
                id=uuid.uuid4(),
                source="auto_faq",
                title=question,
                content="Q: duplicate\nA: duplicate",
                language="en",
                category="faq",
            )

    class FakeDB:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.committed = False
            self.refreshed: object | None = None
            self.lookup_count = 0

        async def get(
            self,
            model: object,
            item_id: uuid.UUID,
        ) -> KnowledgeBaseCandidate | None:
            assert model is KnowledgeBaseCandidate
            assert item_id == candidate_id
            return candidate

        async def execute(self, _stmt: object) -> FakeScalarResult:
            self.lookup_count += 1
            if self.lookup_count == 1:
                return FakeScalarResult()

            class EmptyScalarResult:
                def scalar_one_or_none(self) -> object | None:
                    return None

            return EmptyScalarResult()

        def add(self, row: object) -> None:
            self.added.append(row)

        async def commit(self) -> None:
            created_entry = next(
                row for row in self.added if isinstance(row, KnowledgeBase)
            )
            if created_entry.title == question:
                raise IntegrityError(
                    statement="insert knowledge_base",
                    params={},
                    orig=RuntimeError("duplicate key value"),
                )
            self.committed = True

        async def refresh(self, row: object) -> None:
            self.refreshed = row
            row.created_at = datetime(2026, 5, 11, 12, 0, 0)

    class FakeEmbeddingEngine:
        async def embed_async(self, text: str) -> list[float]:
            assert question in text
            return [0.1] * 1024

    audit_calls: list[dict[str, Any]] = []

    async def fake_log_admin_action(*_: object, **kwargs: Any) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(admin_knowledge_base, "EmbeddingEngine", FakeEmbeddingEngine)
    monkeypatch.setattr(admin_knowledge_base, "log_admin_action", fake_log_admin_action)

    entry = await admin_knowledge_base.approve_admin_kb_candidate(
        db=FakeDB(),
        candidate_id=candidate_id,
        request=None,
    )

    assert entry.title.startswith(question)
    assert entry.title != question
    assert candidate.status == "approved"
    assert audit_calls[0]["after"]["candidate_status"] == "approved"


@pytest.mark.asyncio
async def test_reject_admin_kb_candidate_marks_rejected_and_preserves_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.models.knowledge_base_candidate import KnowledgeBaseCandidate
    from src.schemas.admin import AdminKnowledgeBaseCandidateReject
    from src.services import admin_knowledge_base

    candidate_id = uuid.uuid4()
    candidate = KnowledgeBaseCandidate(
        id=candidate_id,
        question="QA disposable FAQ candidate reject",
        answer="Disposable answer",
        language="en",
        confidence=0.9,
        status="needs_confirmation",
        guard_reasons=[],
        duplicate_similarity=None,
        metadata_={"qa_run_id": "reject"},
    )

    class FakeDB:
        committed = False
        refreshed: object | None = None

        async def get(
            self,
            model: object,
            item_id: uuid.UUID,
        ) -> KnowledgeBaseCandidate | None:
            assert model is KnowledgeBaseCandidate
            assert item_id == candidate_id
            return candidate

        async def commit(self) -> None:
            self.committed = True

        async def refresh(self, row: object) -> None:
            self.refreshed = row
            row.created_at = datetime(2026, 5, 11, 12, 0, 0)

    audit_calls: list[dict[str, Any]] = []

    async def fake_log_admin_action(*_: object, **kwargs: Any) -> None:
        audit_calls.append(kwargs)

    monkeypatch.setattr(admin_knowledge_base, "log_admin_action", fake_log_admin_action)
    db = FakeDB()

    result = await admin_knowledge_base.reject_admin_kb_candidate(
        db=db,
        candidate_id=candidate_id,
        body=AdminKnowledgeBaseCandidateReject(reason="qa cleanup"),
        request=None,
    )

    assert result.status == "rejected"
    assert result.metadata == {
        "qa_run_id": "reject",
        "rejection_reason": "qa cleanup",
    }
    assert db.committed is True
    assert audit_calls[0]["action"] == "knowledge_base.candidate_reject"
