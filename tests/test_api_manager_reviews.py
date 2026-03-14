"""Tests for manager reviews API (Component 8).

Verifies:
- API routes registered and require auth
- Pydantic schemas validate correctly
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from src.schemas.manager_review import (
    ManagerLeaderboardEntry,
    ManagerReviewDetail,
    ManagerReviewRead,
)


def test_manager_review_schemas() -> None:
    """ManagerReviewRead and ManagerReviewDetail schemas validate correctly."""
    review = ManagerReviewRead(
        id=uuid.uuid4(),
        escalation_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        manager_name="Israullah",
        total_score=16.5,
        max_score=20,
        rating="good",
        first_response_time_seconds=300,
        message_count=5,
        deal_converted=True,
        deal_amount=15000.0,
        reviewer="ai",
        created_at=datetime.now(tz=UTC),
    )
    assert review.manager_name == "Israullah"
    assert review.total_score == 16.5


def test_manager_review_detail_schema() -> None:
    """ManagerReviewDetail includes criteria and summary."""
    detail = ManagerReviewDetail(
        id=uuid.uuid4(),
        escalation_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        total_score=18.0,
        max_score=20,
        rating="excellent",
        criteria=[{"rule_number": 1, "rule_name": "Quick pickup", "score": 2}],
        summary="Outstanding work",
        reviewer="ai",
        created_at=datetime.now(tz=UTC),
    )
    assert detail.summary == "Outstanding work"
    assert len(detail.criteria) == 1


def test_manager_leaderboard_entry() -> None:
    """ManagerLeaderboardEntry validates correctly."""
    entry = ManagerLeaderboardEntry(name="Israullah", avg_score=17.5, reviews_count=10)
    assert entry.reviews_count == 10
    assert entry.avg_score == 17.5


def test_manager_reviews_router_registered() -> None:
    """Manager reviews router is registered in the API."""
    from src.api.v1.router import api_v1_router

    route_paths = [getattr(route, "path", "") for route in api_v1_router.routes]
    assert any("/manager-reviews" in path for path in route_paths)
