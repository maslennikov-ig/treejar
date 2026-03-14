from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class Feedback(UUIDMixin, Base):
    """Post-sale customer feedback."""

    __tablename__ = "feedbacks"
    __table_args__ = (
        CheckConstraint("rating_overall BETWEEN 1 AND 5", name="ck_feedbacks_rating_overall"),
        CheckConstraint("rating_delivery BETWEEN 1 AND 5", name="ck_feedbacks_rating_delivery"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
        unique=True,  # one feedback per conversation
        index=True,
    )
    deal_id: Mapped[str | None] = mapped_column(String, default=None)
    rating_overall: Mapped[int] = mapped_column(Integer)  # 1-5
    rating_delivery: Mapped[int] = mapped_column(Integer)  # 1-5
    recommend: Mapped[bool] = mapped_column(Boolean)
    comment: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        back_populates="feedbacks",
    )
