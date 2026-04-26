from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


class OutboundMessageAudit(UUIDMixin, TimestampMixin, Base):
    """Durable audit row for outbound provider side effects."""

    __tablename__ = "outbound_message_audits"

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "crm_message_id",
            name="uq_outbound_message_audits_provider_crm_message_id",
        ),
        UniqueConstraint(
            "provider",
            "provider_message_id",
            name="uq_outbound_message_audits_provider_message_id",
        ),
        Index("ix_outbound_message_audits_conversation_id", "conversation_id"),
        Index("ix_outbound_message_audits_status", "status"),
        Index("ix_outbound_message_audits_source", "source"),
    )

    provider: Mapped[str] = mapped_column(String(50), default="wazzup")
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id"),
    )
    chat_id: Mapped[str] = mapped_column(String(255))
    outbound_chat_id: Mapped[str | None] = mapped_column(String(255), default=None)
    message_type: Mapped[str] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text, default=None)
    caption: Mapped[str | None] = mapped_column(Text, default=None)
    content_uri: Mapped[str | None] = mapped_column(Text, default=None)
    file_name: Mapped[str | None] = mapped_column(String(255), default=None)
    content_type: Mapped[str | None] = mapped_column(String(255), default=None)
    file_size: Mapped[int | None] = mapped_column(default=None)
    provider_message_id: Mapped[str | None] = mapped_column(String(255), default=None)
    crm_message_id: Mapped[str | None] = mapped_column(String(255), default=None)
    source: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(50), default="pending")
    status_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    error_details: Mapped[dict[str, Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)

    conversation: Mapped[Conversation] = relationship()
