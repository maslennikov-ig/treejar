"""Tests for the auto-FAQ service."""

import uuid
from collections.abc import Sequence
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.auto_faq import save_to_faq


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock(spec=AsyncSession)
    return db


@pytest.fixture
def mock_embedding_engine() -> MagicMock:
    engine = MagicMock()
    engine.embed_async = AsyncMock(return_value=[0.1] * 1024)
    return engine


async def _mock_normalize(question: str, answer: str) -> tuple[str, str]:
    """Passthrough mock — treats input as already English."""
    return question, answer


@pytest.mark.asyncio
@pytest.mark.unit
@patch("src.services.auto_faq._normalize_to_english", side_effect=_mock_normalize)
async def test_save_to_faq_success(
    mock_normalize: AsyncMock, mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Test that a new FAQ entry is created when no duplicate exists."""
    # Mock: no existing entries (nearest returns None)
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_db.execute.return_value = mock_result

    # Mock refresh to set id
    async def _refresh(obj: object) -> None:
        obj.id = uuid.uuid4()  # type: ignore[attr-defined]

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    result = await save_to_faq(
        db=mock_db,
        question="What is the delivery time?",
        adapted_answer="Delivery takes 3-5 business days within the UAE.",
        manager_draft="3-5 days UAE",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "saved"
    assert result.entry is not None
    assert result.entry.source == "auto_faq"
    assert result.entry.language == "en"
    assert result.entry.is_auto_generated is True
    assert result.entry.original_question == "What is the delivery time?"
    assert result.entry.manager_draft == "3-5 days UAE"
    assert result.guard_reasons == ()
    mock_db.add.assert_called_once()
    mock_db.commit.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.unit
@patch("src.services.auto_faq._normalize_to_english", side_effect=_mock_normalize)
async def test_save_to_faq_duplicate_rejected(
    mock_normalize: AsyncMock, mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Test that duplicates (similarity > 0.92) are rejected."""
    # Mock: nearest entry with very small distance (high similarity)
    mock_nearest = MagicMock()
    mock_nearest.distance = 0.05  # similarity = 1 - 0.05 = 0.95 > 0.92
    mock_result = MagicMock()
    mock_result.first.return_value = mock_nearest
    mock_db.execute.return_value = mock_result

    result = await save_to_faq(
        db=mock_db,
        question="What is delivery time?",
        adapted_answer="Delivery takes 3-5 business days.",
        manager_draft="3-5 days",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "duplicate"
    assert result.entry is None
    assert result.guard_reasons == ()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
@patch("src.services.auto_faq._normalize_to_english", side_effect=_mock_normalize)
async def test_save_to_faq_similar_but_not_duplicate(
    mock_normalize: AsyncMock, mock_db: AsyncMock, mock_embedding_engine: MagicMock
) -> None:
    """Test that entries with similarity <= 0.92 are saved."""
    # Mock: nearest entry with distance indicating low similarity
    mock_nearest = MagicMock()
    mock_nearest.distance = 0.15  # similarity = 1 - 0.15 = 0.85 < 0.92
    mock_result = MagicMock()
    mock_result.first.return_value = mock_nearest
    mock_db.execute.return_value = mock_result

    async def _refresh(obj: object) -> None:
        obj.id = uuid.uuid4()  # type: ignore[attr-defined]

    mock_db.refresh = AsyncMock(side_effect=_refresh)

    result = await save_to_faq(
        db=mock_db,
        question="How do I return a product?",
        adapted_answer="You can return any product within 14 days.",
        manager_draft="14 days return",
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "saved"
    assert result.entry is not None
    assert result.entry.source == "auto_faq"
    assert result.entry.language == "en"
    mock_db.add.assert_called_once()


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
@patch("src.services.auto_faq._normalize_to_english", side_effect=_mock_normalize)
async def test_save_to_faq_blocks_context_specific_global_save(
    mock_normalize: AsyncMock,
    mock_db: AsyncMock,
    mock_embedding_engine: MagicMock,
    question: str,
    adapted_answer: str,
    manager_draft: str,
    expected_reasons: Sequence[str],
) -> None:
    """Context-specific manager replies must downgrade faq_global to private-only."""
    result = await save_to_faq(
        db=mock_db,
        question=question,
        adapted_answer=adapted_answer,
        manager_draft=manager_draft,
        embedding_engine=mock_embedding_engine,
    )

    assert result.status == "blocked_context_specific"
    assert result.entry is None
    assert set(expected_reasons).issubset(set(result.guard_reasons))
    mock_embedding_engine.embed_async.assert_not_awaited()
    mock_db.execute.assert_not_awaited()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_awaited()
