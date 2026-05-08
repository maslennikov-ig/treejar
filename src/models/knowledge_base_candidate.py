from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class KnowledgeBaseCandidate(UUIDMixin, TimestampMixin, Base):
    """Pending auto-FAQ candidate awaiting admin approval or rejection."""

    __tablename__ = "knowledge_base_candidates"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(8), default="en", nullable=False)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), default=None)
    status: Mapped[str] = mapped_column(
        String(50),
        default="needs_confirmation",
        nullable=False,
        index=True,
    )
    guard_reasons: Mapped[list[str]] = mapped_column(JSON, default=list)
    duplicate_similarity: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        default=None,
    )
    original_question: Mapped[str | None] = mapped_column(Text, default=None)
    manager_draft: Mapped[str | None] = mapped_column(Text, default=None)
    customer_message: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        default=None,
    )
