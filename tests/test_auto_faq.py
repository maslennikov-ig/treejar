"""Tests for the auto-FAQ service."""

from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_base_candidate import KnowledgeBaseCandidate
from src.services.auto_faq import (
    _nearest_duplicate_similarity,
    review_auto_faq_candidate,
)
from src.services.auto_faq_types import AutoFAQCandidate


@pytest.fixture
def mock_db() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_embedding_engine() -> MagicMock:
    engine = MagicMock()
    engine.embed_async = AsyncMock(return_value=[0.1] * 1024)
    return engine


@pytest.mark.asyncio
@pytest.mark.unit
async def test_nearest_duplicate_similarity_filters_soft_deleted_kb_rows(
    mock_db: AsyncMock,
) -> None:
    """Deduplication query must ignore soft-deleted knowledge_base rows (AD-37)."""
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.execute.return_value = mock_result

    similarity = await _nearest_duplicate_similarity(mock_db, [0.1] * 1024)

    assert similarity is None
    stmt = mock_db.execute.await_args.args[0]
    compiled_sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "knowledge_base.deleted_at IS NULL" in compiled_sql


@pytest.mark.asyncio
@pytest.mark.unit
async def test_review_auto_faq_candidate_returns_needs_confirmation_and_persists_when_requested(
    mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Passing candidate returns needs_confirmation and optionally persists KnowledgeBaseCandidate."""
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.execute.return_value = mock_result

    candidate = AutoFAQCandidate(
        question="What is the delivery time?",
        answer="Delivery takes 3-5 business days within the UAE.",
        confidence=0.9,
    )
    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft="3-5 days UAE",
        customer_message="Delivery takes 3-5 business days within the UAE.",
        embedding_engine=mock_embedding_engine,
        persist_candidate=True,
        source_metadata={"escalation_id": "esc-1"},
    )

    assert result.status == "needs_confirmation"
    assert result.candidate == candidate
    assert result.entry is None
    assert result.guard_reasons == ()
    mock_db.add.assert_called_once()
    persisted = mock_db.add.call_args.args[0]
    assert isinstance(persisted, KnowledgeBaseCandidate)
    assert persisted.status == "needs_confirmation"
    assert persisted.metadata_ == {"escalation_id": "esc-1"}
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_review_auto_faq_candidate_does_not_persist_by_default(
    mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Without persist_candidate=True, review_auto_faq_candidate does not write rows."""
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.execute.return_value = mock_result

    candidate = AutoFAQCandidate(
        question="What is the delivery time?",
        answer="Delivery takes 3-5 business days within the UAE.",
        confidence=0.9,
    )
    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft="3-5 days UAE",
        customer_message="Delivery takes 3-5 business days within the UAE.",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "needs_confirmation"
    assert result.candidate is not None
    assert result.entry is None
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_review_auto_faq_candidate_duplicate_rejected(
    mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Candidates with active KB similarity >= 0.92 are marked duplicate."""
    mock_nearest = MagicMock()
    mock_nearest.distance = 0.05  # similarity = 1 - 0.05 = 0.95 >= 0.92
    mock_result = MagicMock()
    mock_result.first.return_value = mock_nearest
    mock_db.execute.return_value = mock_result

    candidate = AutoFAQCandidate(
        question="What is delivery time?",
        answer="Delivery takes 3-5 business days.",
        confidence=0.9,
    )
    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft="3-5 days",
        customer_message="Delivery takes 3-5 business days.",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "duplicate"
    assert result.duplicate_similarity == pytest.approx(0.95)
    assert result.entry is None
    assert result.guard_reasons == ()
    mock_db.add.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_review_auto_faq_candidate_similar_but_not_duplicate(
    mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Candidates with active KB similarity < 0.92 proceed to needs_confirmation."""
    mock_nearest = MagicMock()
    mock_nearest.distance = 0.15  # similarity = 1 - 0.15 = 0.85 < 0.92
    mock_result = MagicMock()
    mock_result.first.return_value = mock_nearest
    mock_db.execute.return_value = mock_result

    candidate = AutoFAQCandidate(
        question="How do I return a product?",
        answer="You can return any product within 14 days.",
        confidence=0.9,
    )
    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft="14 days return",
        customer_message="You can return any product within 14 days.",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "needs_confirmation"
    assert result.duplicate_similarity == pytest.approx(0.85)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_review_auto_faq_candidate_rejects_low_confidence(
    mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    candidate = AutoFAQCandidate(
        question="What is the delivery time?",
        answer="Delivery takes 3-5 business days.",
        confidence=0.5,
    )

    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft="3-5 days",
        customer_message="Delivery takes 3-5 business days.",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "low_confidence"
    assert result.guard_reasons == ("low_confidence",)
    mock_embedding_engine.embed_async.assert_not_awaited()
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_review_auto_faq_candidate_rejects_unsafe_candidate(
    mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    candidate = AutoFAQCandidate(
        question="Can customers get guaranteed refunds?",
        answer="Treejar always guarantees a full refund with no questions asked.",
        confidence=0.95,
    )

    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft="always guaranteed refund",
        customer_message="We always guarantee a refund.",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "blocked_unsafe"
    assert "absolute_claim" in result.guard_reasons
    mock_embedding_engine.embed_async.assert_not_awaited()
    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
@pytest.mark.parametrize(
    ("question", "adapted_answer", "manager_draft", "expected_reasons"),
    [
        (
            "Can you deliver next week?",
            "Yes, we can deliver tomorrow to Dubai Marina.",
            "Tomorrow delivery to Dubai Marina confirmed",
            ("time_specific_promise", "project_specific_logistics"),
        ),
        (
            "Can you do better pricing?",
            "We can offer a 10% discount for this order.",
            "10% discount for this order",
            ("one_off_offer", "customer_specific_commitment"),
        ),
        (
            "Who will contact me?",
            "Ahmed will call you back today.",
            "Ahmed will call today",
            ("time_specific_promise", "callback_commitment"),
        ),
    ],
)
async def test_review_auto_faq_candidate_blocks_context_specific_global_save(
    mock_db: AsyncMock,
    mock_embedding_engine: MagicMock,
    question: str,
    adapted_answer: str,
    manager_draft: str,
    expected_reasons: Sequence[str],
) -> None:
    """Context-specific manager replies must be blocked from global FAQ candidates."""
    candidate = AutoFAQCandidate(
        question=question,
        answer=adapted_answer,
        confidence=0.95,
    )
    result = await review_auto_faq_candidate(
        mock_db,
        candidate,
        manager_draft=manager_draft,
        customer_message=adapted_answer,
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "blocked_context_specific"
    assert result.entry is None
    assert set(expected_reasons).issubset(set(result.guard_reasons))
    mock_embedding_engine.embed_async.assert_not_awaited()
    mock_db.execute.assert_not_awaited()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()
