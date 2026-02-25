from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import String, Text, UniqueConstraint, func
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
