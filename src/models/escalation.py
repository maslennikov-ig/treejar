from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class Escalation(UUIDMixin, TimestampMixin, Base):
    """An escalation of a conversation to a human agent."""

    __tablename__ = "escalations"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
    )
    reason: Mapped[str] = mapped_column(Text)
    assigned_to: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="pending")
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        back_populates="escalations",
    )
