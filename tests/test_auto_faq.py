"""Tests for the auto-FAQ service."""

import uuid
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

    assert result is not None
    assert result.source == "auto_faq"
    assert result.language == "en"
    assert result.is_auto_generated is True
    assert result.original_question == "What is the delivery time?"
    assert result.manager_draft == "3-5 days UAE"
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

    assert result is None
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

    assert result is not None
    assert result.source == "auto_faq"
    assert result.language == "en"
    mock_db.add.assert_called_once()
