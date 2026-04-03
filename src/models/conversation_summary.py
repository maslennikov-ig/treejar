from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class ConversationSummary(UUIDMixin, TimestampMixin, Base):
    """Structured summary for older conversation turns."""

    __tablename__ = "conversation_summaries"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
        unique=True,
    )
    summary_text: Mapped[str] = mapped_column(Text)
    covered_through_message_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    model: Mapped[str] = mapped_column(String)
    version: Mapped[int] = mapped_column(Integer, default=1)

    conversation: Mapped[Conversation] = relationship(
        back_populates="summary",
    )
