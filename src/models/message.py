from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class Message(UUIDMixin, Base):
    """A single message within a conversation."""

    __tablename__ = "messages"

    __table_args__ = (
        Index(
            "ix_messages_wazzup_message_id",
            "wazzup_message_id",
            unique=True,
            postgresql_where=text("wazzup_message_id IS NOT NULL"),
        ),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
    )
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    message_type: Mapped[str] = mapped_column(String, default="text")
    wazzup_message_id: Mapped[str | None] = mapped_column(String, default=None)
    tokens_in: Mapped[int | None] = mapped_column(default=None)
    tokens_out: Mapped[int | None] = mapped_column(default=None)
    cost: Mapped[float | None] = mapped_column(Numeric(10, 6), default=None)
    model: Mapped[str | None] = mapped_column(String, default=None)
    audio_url: Mapped[str | None] = mapped_column(String, default=None)
    transcription: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )

    # Relationships
    conversation: Mapped[Conversation] = relationship(
        back_populates="messages",
    )


def _normalize_message_datetime(value: datetime) -> datetime:
    """Normalize datetimes to naive UTC for timestamp-without-time-zone columns."""
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def message_created_at_now(*, sequence: int = 0) -> datetime:
    """Generate a stable naive UTC timestamp for locally-created messages."""
    base = datetime.now(UTC).replace(tzinfo=None)
    return base + timedelta(microseconds=sequence)


def message_created_at_from_wazzup(
    *,
    date_time: str | None,
    timestamp: int | None,
    sequence: int = 0,
) -> datetime:
    """Convert Wazzup message time into a stable naive UTC timestamp."""
    if date_time:
        normalized = date_time.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        base = _normalize_message_datetime(
            parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        )
    elif timestamp is not None:
        base = datetime.fromtimestamp(timestamp, tz=UTC).replace(tzinfo=None)
    else:
        base = datetime.now(UTC).replace(tzinfo=None)

    return base + timedelta(microseconds=sequence)
