from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation
    from src.models.escalation import Escalation


class ManagerReview(UUIDMixin, Base):
    """Quality assessment of a manager's post-escalation conversation.

    Stores both LLM-judged quality scores (10 criteria, 0-20 scale) and
    quantitative business metrics (response time, conversion, etc.).
    """

    __tablename__ = "manager_reviews"

    escalation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("escalations.id"),
        unique=True,  # One review per escalation
        index=True,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
        index=True,
    )
    manager_name: Mapped[str | None] = mapped_column(String, default=None)

    # LLM Judge scores
    total_score: Mapped[float] = mapped_column(Numeric(4, 1))
    max_score: Mapped[int] = mapped_column(Integer, default=20)
    rating: Mapped[str] = mapped_column(String)  # excellent/good/satisfactory/poor
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON)
    summary: Mapped[str | None] = mapped_column(Text, default=None)

    # Quantitative metrics
    first_response_time_seconds: Mapped[int | None] = mapped_column(
        Integer, default=None
    )
    message_count: Mapped[int | None] = mapped_column(Integer, default=None)
    deal_converted: Mapped[bool] = mapped_column(Boolean, default=False)
    deal_amount: Mapped[float | None] = mapped_column(
        Numeric(12, 2), default=None
    )

    reviewer: Mapped[str] = mapped_column(String, default="ai")
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        back_populates="manager_reviews",
    )
    escalation: Mapped[Escalation] = relationship(
        back_populates="manager_review",
    )
