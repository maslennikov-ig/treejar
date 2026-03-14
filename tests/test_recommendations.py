"""Tests for product recommendations service (TDD)."""

from __future__ import annotations

# =============================================================================
# RecommendationItem tests
# =============================================================================


def test_recommendation_item_structure() -> None:
    """RecommendationItem should accept all fields."""
    from uuid import uuid4

    from src.services.recommendations import RecommendationItem

    item = RecommendationItem(
        id=uuid4(),
        name="Executive Desk",
        price=1500.0,
        stock=10,
        similarity_score=0.95,
        recommendation_type="similar",
    )
    assert item.price == 1500.0
    assert item.similarity_score == 0.95


def test_recommendation_item_defaults() -> None:
    """RecommendationItem should have default type 'similar'."""
    from uuid import uuid4

    from src.services.recommendations import RecommendationItem

    item = RecommendationItem(id=uuid4(), name="Chair", price=500.0, stock=5)
    assert item.recommendation_type == "similar"
    assert item.similarity_score is None
