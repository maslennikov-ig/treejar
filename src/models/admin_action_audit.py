from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class AdminActionAudit(UUIDMixin, Base):
    """Durable audit row for mutating admin and CRM actions."""

    __tablename__ = "admin_action_audits"
    __table_args__ = (
        Index("ix_admin_action_audits_created_at", "created_at"),
        Index("ix_admin_action_audits_action", "action"),
        Index("ix_admin_action_audits_entity", "entity_type", "entity_id"),
    )

    actor: Mapped[str] = mapped_column(String(120), default="admin", nullable=False)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), default=None)
    request_path: Mapped[str | None] = mapped_column(String(500), default=None)
    before: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    after: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    metadata_: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        "metadata",
        JSON,
        default=None,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
