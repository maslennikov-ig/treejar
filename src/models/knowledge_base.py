from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, UUIDMixin


class KnowledgeBase(UUIDMixin, Base):
    """A knowledge base entry for RAG retrieval."""

    __tablename__ = "knowledge_base"
    __table_args__ = (
        UniqueConstraint("source", "title", name="uq_knowledge_base_source_title"),
    )

    source: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String, default="en")
    category: Mapped[str | None] = mapped_column(String, default=None)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1024), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    deleted_by: Mapped[str | None] = mapped_column(String(120), default=None)

    # Auto-FAQ fields: track entries created from manager responses
    is_auto_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    original_question: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    manager_draft: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
