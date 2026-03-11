"""API endpoints for the referral system."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.core.database import async_session_factory
from src.services.referrals import (
    ReferralResult,
    ReferralStats,
    apply_code,
    generate_code,
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
async def generate_referral_code(request: GenerateRequest) -> ReferralResult:
    """Generate a new referral code for a customer."""
    async with async_session_factory() as db:
        result = await generate_code(db, request.phone)
        await db.commit()
    return result


@router.post("/apply", response_model=ReferralResult)
async def apply_referral_code(request: ApplyRequest) -> ReferralResult:
    """Apply a referral code for a new customer."""
    async with async_session_factory() as db:
        result = await apply_code(db, request.code, request.referee_phone)
        await db.commit()
    return result


@router.get("/{phone}/stats", response_model=ReferralStats)
async def referral_stats(phone: str) -> ReferralStats:
    """Get referral statistics for a customer."""
    async with async_session_factory() as db:
        return await get_referral_stats(db, phone)
