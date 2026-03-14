"""API schemas for manager reviews (Component 8)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ManagerReviewRead(BaseModel):
    """Compact manager review for list view."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    escalation_id: uuid.UUID
    conversation_id: uuid.UUID
    manager_name: str | None = None
    total_score: float
    max_score: int
    rating: str
    first_response_time_seconds: int | None = None
    message_count: int | None = None
    deal_converted: bool = False
    deal_amount: float | None = None
    reviewer: str
    created_at: datetime


class ManagerReviewDetail(ManagerReviewRead):
    """Full manager review with criteria details."""

    criteria: list[dict[str, Any]] = []
    summary: str | None = None


class ManagerLeaderboardEntry(BaseModel):
    """Leaderboard entry for a manager."""

    name: str
    avg_score: float
    reviews_count: int
