"""Tests for ManagerReview model (Component 4).

Verifies model creation, field types, and relationship definitions.
"""
from __future__ import annotations

import uuid

from src.models.manager_review import ManagerReview


def test_manager_review_fields() -> None:
    """ManagerReview model has all expected fields."""
    review = ManagerReview(
        escalation_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        manager_name="Israullah",
        total_score=16.5,
        max_score=20,
        rating="good",
        criteria=[
            {"rule_number": 1, "rule_name": "Quick pickup", "score": 2, "comment": "Good"},
        ],
        summary="Good performance overall",
        first_response_time_seconds=300,
        message_count=5,
        deal_converted=True,
        deal_amount=15000.00,
        reviewer="ai",
    )

    assert review.manager_name == "Israullah"
    assert review.total_score == 16.5
    assert review.max_score == 20
    assert review.rating == "good"
    assert review.first_response_time_seconds == 300
    assert review.message_count == 5
    assert review.deal_converted is True
    assert review.deal_amount == 15000.00
    assert review.reviewer == "ai"


def test_manager_review_table_name() -> None:
    """Table name should be manager_reviews."""
    assert ManagerReview.__tablename__ == "manager_reviews"


def test_manager_review_defaults() -> None:
    """Nullable fields default to None at Python level."""
    review = ManagerReview(
        escalation_id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        total_score=10.0,
        max_score=20,
        rating="satisfactory",
        criteria=[],
        deal_converted=False,
        reviewer="ai",
    )

    assert review.manager_name is None
    assert review.first_response_time_seconds is None
    assert review.message_count is None
    assert review.deal_amount is None
    assert review.summary is None


def test_escalation_status_manual_takeover() -> None:
    """EscalationStatus enum includes manual_takeover."""
    from src.schemas.common import EscalationStatus

    assert EscalationStatus.MANUAL_TAKEOVER.value == "manual_takeover"
    assert "manual_takeover" in [e.value for e in EscalationStatus]


def test_webhook_schema_new_fields() -> None:
    """WazzupIncomingMessage has authorId and authorName fields."""
    from src.schemas.webhook import WazzupIncomingMessage

    msg = WazzupIncomingMessage(
        messageId="test",
        chatId="123",
        authorType="manager",
        isEcho=True,
        authorId="mgr-001",
        authorName="Israullah",
        timestamp=0,
    )

    assert msg.authorId == "mgr-001"
    assert msg.authorName == "Israullah"
    assert msg.authorType == "manager"
    assert msg.isEcho is True
