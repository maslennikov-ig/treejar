from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class QualityReview(UUIDMixin, Base):
    """Quality assessment of a conversation."""

    __tablename__ = "quality_reviews"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
    )
    total_score: Mapped[float] = mapped_column(Numeric(4, 1))
    max_score: Mapped[int] = mapped_column(Integer, default=30)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSON)
    rating: Mapped[str] = mapped_column(String)
    summary: Mapped[str | None] = mapped_column(Text, default=None)
    reviewer: Mapped[str] = mapped_column(String, default="ai")
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        back_populates="quality_reviews",
    )
