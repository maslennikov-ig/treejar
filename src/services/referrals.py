"""Referral system business logic.

Handles code generation, validation, application, and statistics.
"""

from __future__ import annotations

import logging
import secrets
import string
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.referral import Referral

logger = logging.getLogger(__name__)

# Code format: NOOR-XXXXX (5 uppercase alphanumeric)
CODE_PREFIX = "NOOR-"
CODE_LENGTH = 5
CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_code() -> str:
    """Generate a unique referral code (NOOR-XXXXX)."""
    suffix = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
    return f"{CODE_PREFIX}{suffix}"


class ReferralStats(BaseModel):
    """Referral statistics for a customer."""

    total_codes: int = 0
    active_codes: int = 0
    used_codes: int = 0
    expired_codes: int = 0


class ReferralResult(BaseModel):
    """Result of code generation or application."""

    success: bool
    code: str
    message: str
    discount_percent: float | None = None


async def generate_code(
    db: AsyncSession,
    phone: str,
) -> ReferralResult:
    """Generate a unique referral code for a customer.

    Uses DB UNIQUE constraint as the source of truth for uniqueness.
    Retries on IntegrityError (collision).

    Args:
        db: Database session.
        phone: Referrer's phone number.

    Returns:
        ReferralResult with the generated code.
    """
    for attempt in range(10):
        code = _generate_code()
        referral = Referral(
            code=code,
            referrer_phone=phone,
        )
        db.add(referral)
        try:
            await db.flush()
            return ReferralResult(
                success=True,
                code=code,
                message=f"Your referral code is {code}. Share it with friends for a 10% discount!",
                discount_percent=referral.referee_discount_percent,
            )
        except IntegrityError:
            await db.rollback()
            logger.warning(
                "Referral code collision on attempt %d: %s", attempt + 1, code
            )
            continue

    return ReferralResult(
        success=False,
        code="",
        message="Failed to generate unique code after 10 attempts",
    )


async def apply_code(
    db: AsyncSession,
    code: str,
    referee_phone: str,
) -> ReferralResult:
    """Apply a referral code for a new customer.

    Validates:
    - Code exists
    - Code is not expired
    - Code is not already used
    - Referrer is not the same as referee

    Args:
        db: Database session.
        code: The referral code to apply.
        referee_phone: Phone of the customer applying the code.

    Returns:
        ReferralResult with the outcome.
    """
    stmt = select(Referral).where(Referral.code == code.upper())
    result = await db.execute(stmt)
    referral = result.scalar_one_or_none()

    if not referral:
        return ReferralResult(
            success=False,
            code=code,
            message="Invalid referral code.",
        )

    if referral.status == "used":
        return ReferralResult(
            success=False,
            code=code,
            message="This referral code has already been used.",
        )

    if referral.status == "expired" or referral.expires_at < datetime.now(tz=UTC):
        return ReferralResult(
            success=False,
            code=code,
            message="This referral code has expired.",
        )

    if referral.referrer_phone == referee_phone:
        return ReferralResult(
            success=False,
            code=code,
            message="You cannot use your own referral code.",
        )

    # Apply the code
    referral.referee_phone = referee_phone
    referral.status = "used"
    referral.used_at = datetime.now(tz=UTC)
    await db.flush()

    return ReferralResult(
        success=True,
        code=code,
        message=f"Referral code applied! You get a {referral.referee_discount_percent}% discount.",
        discount_percent=referral.referee_discount_percent,
    )


async def get_referral_stats(
    db: AsyncSession,
    phone: str,
) -> ReferralStats:
    """Get referral statistics for a customer.

    Args:
        db: Database session.
        phone: Customer's phone number.

    Returns:
        ReferralStats with breakdown by status.
    """
    stmt = (
        select(Referral.status, func.count(Referral.id))
        .where(Referral.referrer_phone == phone)
        .group_by(Referral.status)
    )
    result = await db.execute(stmt)
    status_counts = {row[0]: row[1] for row in result.all()}

    return ReferralStats(
        total_codes=sum(status_counts.values()),
        active_codes=status_counts.get("active", 0),
        used_codes=status_counts.get("used", 0),
        expired_codes=status_counts.get("expired", 0),
    )
