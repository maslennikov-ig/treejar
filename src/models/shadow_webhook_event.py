from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class ShadowWebhookEvent(UUIDMixin, TimestampMixin, Base):
    """Passive observe-only copy of a Wazzup webhook message item.

    Used strictly for read-only shift QA monitoring (e.g. Nikita even-day shifts)
    without entering Noor's active inbound queue, worker, LLM, or CRM pipeline.
    """

    __tablename__ = "shadow_webhook_events"
    __table_args__ = (
        Index("ix_shadow_webhook_events_chat_created_at", "chat_id", "created_at"),
        Index("ix_shadow_webhook_events_created_at", "created_at"),
    )

    message_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    source_ip: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_id: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
        default=None,
    )
    chat_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    chat_type: Mapped[str | None] = mapped_column(String(64), default=None)
    is_echo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str | None] = mapped_column(String(64), default=None)
    author_type: Mapped[str | None] = mapped_column(String(64), default=None)
    author_name: Mapped[str | None] = mapped_column(String(255), default=None)
    message_type: Mapped[str | None] = mapped_column(String(64), default=None)
    text: Mapped[str | None] = mapped_column(Text, default=None)
    content_uri: Mapped[str | None] = mapped_column(Text, default=None)
    provider_timestamp: Mapped[str | None] = mapped_column(String(128), default=None)
    raw_message: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
