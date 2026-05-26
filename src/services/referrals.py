"""Referral system business logic.

Handles code generation, validation, application, and statistics.
"""

from __future__ import annotations

import logging
import secrets
import string
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.referral import Referral
from src.models.system_config import SystemConfig

logger = logging.getLogger(__name__)

# Code format: NOOR-XXXXX (5 uppercase alphanumeric)
CODE_PREFIX = "NOOR-"
CODE_LENGTH = 5
CODE_ALPHABET = string.ascii_uppercase + string.digits
REFERRAL_POLICY_KEY = "referral_policy"
ReferralPolicyStatus = Literal["client_decision_required", "excluded", "approved"]


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


class ReferralPolicyConfig(BaseModel):
    """SystemConfig JSON payload controlling referral launch readiness."""

    model_config = ConfigDict(extra="forbid")

    status: ReferralPolicyStatus = "client_decision_required"
    approved: bool = False
    enabled: bool = False
    confirmation_required: bool = True
    decision_note: str = (
        "Client decision required before referral generation or discounts can launch."
    )
    discount_policy: dict[str, Any] = Field(default_factory=dict)

    @property
    def allows_launch(self) -> bool:
        return self.status == "approved" and self.approved and self.enabled


class ReferralPolicyResponse(BaseModel):
    config: ReferralPolicyConfig
    allows_launch: bool
    message: str


def parse_referral_policy(raw: Any) -> ReferralPolicyConfig:
    if isinstance(raw, ReferralPolicyConfig):
        return raw
    if isinstance(raw, Mapping):
        return ReferralPolicyConfig.model_validate(raw)
    return ReferralPolicyConfig()


async def get_referral_policy_config(db: AsyncSession) -> ReferralPolicyConfig:
    result = await db.execute(
        select(SystemConfig).where(SystemConfig.key == REFERRAL_POLICY_KEY)
    )
    row = result.scalar_one_or_none()
    value = getattr(row, "value", None)
    if value is None:
        return ReferralPolicyConfig()
    try:
        return parse_referral_policy(value)
    except ValidationError:
        logger.warning(
            "Invalid SystemConfig %s; using disabled defaults",
            REFERRAL_POLICY_KEY,
            exc_info=True,
        )
        return ReferralPolicyConfig()


def referral_policy_message(policy: ReferralPolicyConfig) -> str:
    if policy.allows_launch:
        return "Referral policy is approved and enabled."
    if policy.status == "excluded":
        return "Referral program is explicitly excluded from final acceptance until the client reopens it."
    return policy.decision_note


def build_referral_policy_response(
    policy: ReferralPolicyConfig,
) -> ReferralPolicyResponse:
    return ReferralPolicyResponse(
        config=policy,
        allows_launch=policy.allows_launch,
        message=referral_policy_message(policy),
    )


def _policy_block_result(policy: ReferralPolicyConfig) -> ReferralResult:
    return ReferralResult(
        success=False,
        code="",
        message=(
            f"{referral_policy_message(policy)} A manager must confirm the "
            "customer-visible referral rules before any code or discount is applied."
        ),
    )


async def generate_code(
    db: AsyncSession,
    phone: str,
    *,
    policy: ReferralPolicyConfig | None = None,
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
    if policy is not None and not policy.allows_launch:
        return _policy_block_result(policy)

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
    *,
    policy: ReferralPolicyConfig | None = None,
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
    if policy is not None and not policy.allows_launch:
        return _policy_block_result(policy)

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
