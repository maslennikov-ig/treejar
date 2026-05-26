"""API endpoints for the referral system."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.services.referrals import (
    ReferralPolicyResponse,
    ReferralResult,
    ReferralStats,
    apply_code,
    build_referral_policy_response,
    generate_code,
    get_referral_policy_config,
    get_referral_stats,
)

router = APIRouter()


class GenerateRequest(BaseModel):
    """Request body for code generation."""

    phone: str = Field(pattern=r"^\+\d{10,15}$")


class ApplyRequest(BaseModel):
    """Request body for code application."""

    code: str = Field(min_length=10, max_length=10)
    referee_phone: str = Field(pattern=r"^\+\d{10,15}$")


@router.post("/generate", response_model=ReferralResult)
async def generate_referral_code(
    request: GenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> ReferralResult:
    """Generate a new referral code for a customer."""
    policy = await get_referral_policy_config(db)
    result = await generate_code(db, request.phone, policy=policy)
    if result.success:
        await db.commit()
    return result


@router.post("/apply", response_model=ReferralResult)
async def apply_referral_code(
    request: ApplyRequest,
    db: AsyncSession = Depends(get_db),
) -> ReferralResult:
    """Apply a referral code for a new customer."""
    policy = await get_referral_policy_config(db)
    result = await apply_code(
        db,
        request.code,
        request.referee_phone,
        policy=policy,
    )
    if result.success:
        await db.commit()
    return result


@router.get("/policy", response_model=ReferralPolicyResponse)
async def referral_policy(
    db: AsyncSession = Depends(get_db),
) -> ReferralPolicyResponse:
    """Get current referral launch policy status."""
    return build_referral_policy_response(await get_referral_policy_config(db))


@router.get("/{phone}/stats", response_model=ReferralStats)
async def referral_stats(
    phone: str,
    db: AsyncSession = Depends(get_db),
) -> ReferralStats:
    """Get referral statistics for a customer."""
    return await get_referral_stats(db, phone)
