"""Tests for referral system (TDD)."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# =============================================================================
# Code generation tests
# =============================================================================


def test_generate_code_format() -> None:
    """Generated codes should match NOOR-XXXXX format."""
    from src.services.referrals import _generate_code

    for _ in range(20):
        code = _generate_code()
        assert code.startswith("NOOR-")
        assert len(code) == 10  # NOOR- + 5 chars
        suffix = code[5:]
        assert suffix.isalnum()
        assert suffix.isupper() or suffix.isdigit()


def test_referral_stats_defaults() -> None:
    """ReferralStats should have all zero defaults."""
    from src.services.referrals import ReferralStats

    stats = ReferralStats()
    assert stats.total_codes == 0
    assert stats.active_codes == 0
    assert stats.used_codes == 0
    assert stats.expired_codes == 0


def test_referral_result_model() -> None:
    """ReferralResult should accept all fields."""
    from src.services.referrals import ReferralResult

    result = ReferralResult(
        success=True,
        code="NOOR-ABC12",
        message="Code generated!",
        discount_percent=10.0,
    )
    assert result.success is True
    assert result.code == "NOOR-ABC12"
    assert result.discount_percent == 10.0


# =============================================================================
# Business logic tests (with mock DB)
# =============================================================================


@pytest.mark.asyncio
async def test_generate_code_db() -> None:
    """generate_code should create a Referral record via flush."""
    from src.services.referrals import generate_code

    mock_db = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.flush = AsyncMock()  # No IntegrityError = success

    result = await generate_code(mock_db, "+971501234567")
    assert result.success is True
    assert result.code.startswith("NOOR-")
    mock_db.add.assert_called_once()


@pytest.mark.asyncio
async def test_apply_code_invalid() -> None:
    """apply_code should reject invalid code."""
    from src.services.referrals import apply_code

    mock_db = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    result = await apply_code(mock_db, "NOOR-XXXXX", "+971509876543")
    assert result.success is False
    assert "Invalid" in result.message


@pytest.mark.asyncio
async def test_apply_code_self_referral() -> None:
    """apply_code should reject self-referral."""
    from src.services.referrals import apply_code

    from src.models.referral import Referral

    mock_referral = MagicMock(spec=Referral)
    mock_referral.code = "NOOR-ABC12"
    mock_referral.referrer_phone = "+971501234567"
    mock_referral.status = "active"
    mock_referral.expires_at = datetime.now(tz=UTC) + timedelta(days=30)

    mock_db = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_referral
    mock_db.execute = AsyncMock(return_value=mock_execute_result)

    result = await apply_code(mock_db, "NOOR-ABC12", "+971501234567")
    assert result.success is False
    assert "own" in result.message.lower()


@pytest.mark.asyncio
async def test_apply_code_success() -> None:
    """apply_code should succeed for valid code."""
    from src.services.referrals import apply_code

    from src.models.referral import Referral

    mock_referral = MagicMock(spec=Referral)
    mock_referral.code = "NOOR-ABC12"
    mock_referral.referrer_phone = "+971501234567"
    mock_referral.referee_discount_percent = 10.0
    mock_referral.status = "active"
    mock_referral.expires_at = datetime.now(tz=UTC) + timedelta(days=30)

    mock_db = AsyncMock()
    mock_execute_result = MagicMock()
    mock_execute_result.scalar_one_or_none.return_value = mock_referral
    mock_db.execute = AsyncMock(return_value=mock_execute_result)
    mock_db.flush = AsyncMock()

    result = await apply_code(mock_db, "NOOR-ABC12", "+971509876543")
    assert result.success is True
    assert result.discount_percent == 10.0
    assert mock_referral.status == "used"
