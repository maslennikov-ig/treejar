from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class BotBehaviorRule(UUIDMixin, Base):
    """Admin-approved behavior instruction selected before LLM response."""

    __tablename__ = "bot_behavior_rules"
    __table_args__ = (
        Index("ix_bot_behavior_rules_status", "status"),
        Index("ix_bot_behavior_rules_type", "type"),
        Index("ix_bot_behavior_rules_context", "stage", "language", "segment"),
        Index("ix_bot_behavior_rules_priority", "priority"),
        Index("ix_bot_behavior_rules_archived_at", "archived_at"),
    )

    title: Mapped[str] = mapped_column(String(240), nullable=False)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    scope: Mapped[str] = mapped_column(String(80), default="global", nullable=False)
    stage: Mapped[str | None] = mapped_column(String(80), default=None)
    language: Mapped[str | None] = mapped_column(String(8), default=None)
    segment: Mapped[str | None] = mapped_column(String(120), default=None)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_examples: Mapped[list[str]] = mapped_column(JSON, default=list)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024), nullable=True, default=None
    )
    created_by: Mapped[str] = mapped_column(
        String(120), default="admin", nullable=False
    )
    updated_by: Mapped[str] = mapped_column(
        String(120), default="admin", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        default=None,
    )
