from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from src.models.conversation import Conversation


CUSTOMER_ORDER_STATUSES = (
    "active",
    "quoted_snapshot",
    "accepted",
    "closed_refused",
    "closed_no_response",
    "superseded",
)

CUSTOMER_FACT_SCOPES = (
    "persistent_profile",
    "current_order",
    "past_order_reference",
)

CUSTOMER_FACT_CONFIDENCES = ("high", "medium", "low")

CUSTOMER_FACT_STATUSES = (
    "accepted",
    "proposed",
    "conflict",
    "rejected",
    "superseded",
)


def _check_in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    allowed = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{column} in ({allowed})", name=name)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class CustomerProfile(UUIDMixin, TimestampMixin, Base):
    """Durable profile facts keyed by canonical customer identity."""

    __tablename__ = "customer_profiles"
    __table_args__ = (
        UniqueConstraint(
            "canonical_phone",
            name="uq_customer_profiles_canonical_phone",
        ),
    )

    canonical_phone: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), default=None)
    preferred_language: Mapped[str | None] = mapped_column(String(8), default=None)
    primary_email: Mapped[str | None] = mapped_column(String(255), default=None)
    zoho_contact_id: Mapped[str | None] = mapped_column(String(120), default=None)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSON,
        default=None,
    )

    orders: Mapped[list[CustomerOrderMemory]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )
    facts: Mapped[list[CustomerFact]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
    )


class CustomerOrderMemory(UUIDMixin, TimestampMixin, Base):
    """Active or historical order memory for a customer conversation."""

    __tablename__ = "customer_order_memories"
    __table_args__ = (
        _check_in("status", CUSTOMER_ORDER_STATUSES, "ck_customer_order_status"),
        Index(
            "ix_customer_order_memories_profile_status",
            "customer_profile_id",
            "status",
        ),
        Index(
            "ix_customer_order_memories_conversation_status",
            "conversation_id",
            "status",
        ),
    )

    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id"),
        nullable=False,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"),
        default=None,
    )
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )
    quoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    closed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None)
    zoho_salesorder_id: Mapped[str | None] = mapped_column(String(120), default=None)
    zoho_quote_id: Mapped[str | None] = mapped_column(String(120), default=None)
    deal_id: Mapped[str | None] = mapped_column(String(120), default=None)

    profile: Mapped[CustomerProfile] = relationship(back_populates="orders")
    conversation: Mapped[Conversation | None] = relationship()
    facts: Mapped[list[CustomerFact]] = relationship(
        back_populates="order_memory",
        cascade="all, delete-orphan",
    )


class CustomerFact(UUIDMixin, TimestampMixin, Base):
    """Normalized fact tied to a profile and optionally to the active order."""

    __tablename__ = "customer_facts"
    __table_args__ = (
        _check_in("scope", CUSTOMER_FACT_SCOPES, "ck_customer_fact_scope"),
        _check_in(
            "confidence",
            CUSTOMER_FACT_CONFIDENCES,
            "ck_customer_fact_confidence",
        ),
        _check_in("status", CUSTOMER_FACT_STATUSES, "ck_customer_fact_status"),
        Index(
            "ix_customer_facts_profile_scope_key_status",
            "customer_profile_id",
            "scope",
            "key",
            "status",
        ),
        Index("ix_customer_facts_source_message_id", "source_message_id"),
        Index(
            "ix_customer_facts_order_scope_key_status",
            "order_memory_id",
            "scope",
            "key",
            "status",
        ),
    )

    customer_profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("customer_profiles.id"),
        nullable=False,
    )
    order_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("customer_order_memories.id"),
        default=None,
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"),
        default=None,
    )
    scope: Mapped[str] = mapped_column(String(40), nullable=False)
    key: Mapped[str] = mapped_column(String(160), nullable=False)
    value: Mapped[dict[str, Any] | list[Any] | str | int | float | bool | None] = (
        mapped_column(JSON, nullable=True)
    )
    confidence: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="proposed", nullable=False)
    source: Mapped[str] = mapped_column(String(80), nullable=False)
    source_message_id: Mapped[str | None] = mapped_column(String(120), default=None)
    source_excerpt: Mapped[str | None] = mapped_column(Text, default=None)
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=None,
    )

    profile: Mapped[CustomerProfile] = relationship(back_populates="facts")
    order_memory: Mapped[CustomerOrderMemory | None] = relationship(
        back_populates="facts",
    )
    conversation: Mapped[Conversation | None] = relationship()
