"""Referral system model.

Tracks referral codes, their usage, and discount percentages.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base, TimestampMixin, UUIDMixin


class Referral(UUIDMixin, TimestampMixin, Base):
    """A referral code linking two customers."""

    __tablename__ = "referrals"

    code: Mapped[str] = mapped_column(String, unique=True, index=True)
    referrer_phone: Mapped[str] = mapped_column(String, index=True)
    referee_phone: Mapped[str | None] = mapped_column(String, default=None)
    referrer_discount_percent: Mapped[float] = mapped_column(
        Float, default=5.0
    )
    referee_discount_percent: Mapped[float] = mapped_column(
        Float, default=10.0
    )
    status: Mapped[str] = mapped_column(
        String, default="active"
    )  # active, used, expired
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(tz=UTC) + timedelta(days=90),
    )
