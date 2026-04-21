from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin

LLM_ATTEMPT_STATUSES = (
    "pending",
    "success",
    "no_action",
    "failed_retryable",
    "failed_final",
    "budget_blocked",
    "needs_manual_review",
)


class LLMAttempt(UUIDMixin, TimestampMixin, Base):
    """Durable LLM attempt/cache state for background jobs."""

    __tablename__ = "llm_attempts"
    __table_args__ = (
        UniqueConstraint(
            "path",
            "entity_type",
            "entity_id",
            "entity_updated_at",
            "prompt_version",
            name="uq_llm_attempts_logical_key",
        ),
        CheckConstraint(
            "status in ("
            + ", ".join(f"'{status}'" for status in LLM_ATTEMPT_STATUSES)
            + ")",
            name="ck_llm_attempts_status",
        ),
        Index("ix_llm_attempts_status_next_retry_at", "status", "next_retry_at"),
        Index("ix_llm_attempts_entity", "entity_type", "entity_id"),
    )

    path: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    prompt_version: Mapped[str] = mapped_column(String(100), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    settings_hash: Mapped[str | None] = mapped_column(String(64), default=None)

    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        nullable=False,
        index=True,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )

    model: Mapped[str | None] = mapped_column(String(200), default=None)
    provider: Mapped[str | None] = mapped_column(String(100), default=None)
    budget_cents: Mapped[int | None] = mapped_column(Integer, default=None)
    cost_estimate: Mapped[float | None] = mapped_column(Numeric(12, 6), default=None)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6), default=None)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    cached_tokens: Mapped[int | None] = mapped_column(Integer, default=None)
    cache_write_tokens: Mapped[int | None] = mapped_column(Integer, default=None)

    result_json: Mapped[dict[str, Any] | list[Any] | None] = mapped_column(
        JSON,
        default=None,
    )
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
