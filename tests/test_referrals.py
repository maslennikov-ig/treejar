"""Tests for referral system (TDD)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

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
    from src.models.referral import Referral
    from src.services.referrals import apply_code

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
    from src.models.referral import Referral
    from src.services.referrals import apply_code

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


def test_referral_policy_defaults_to_client_decision_required() -> None:
    """Default policy must not launch discounts without explicit client approval."""
    from src.services.referrals import ReferralPolicyConfig

    policy = ReferralPolicyConfig()

    assert policy.status == "client_decision_required"
    assert policy.approved is False
    assert policy.enabled is False
    assert policy.allows_launch is False


@pytest.mark.asyncio
async def test_referral_api_generation_blocks_without_approved_policy() -> None:
    """Protected API should be admin-readable/disabled-safe by default."""
    from src.api.v1.referrals import GenerateRequest, generate_referral_code

    mock_db = AsyncMock()
    mock_config_result = MagicMock()
    mock_config_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_config_result)
    mock_db.commit = AsyncMock()

    result = await generate_referral_code(
        GenerateRequest(phone="+971501234567"),
        mock_db,
    )

    assert result.success is False
    assert result.code == ""
    assert "client decision" in result.message.lower()
    mock_db.add.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_llm_apply_referral_code_blocks_without_approved_policy() -> None:
    """The sales agent must not apply a referral discount silently."""
    from pydantic_ai import RunContext

    from src.llm.engine import SalesDeps, apply_referral_code
    from src.models.conversation import Conversation

    mock_db = AsyncMock()
    mock_config_result = MagicMock()
    mock_config_result.scalar_one_or_none.return_value = None
    mock_db.execute = AsyncMock(return_value=mock_config_result)
    mock_db.flush = AsyncMock()

    deps = SalesDeps(
        db=mock_db,
        conversation=Conversation(id=None, phone="+971509876543"),
        embedding_engine=AsyncMock(),
        zoho_inventory=AsyncMock(),
        zoho_crm=AsyncMock(),
        messaging_client=AsyncMock(),
        pii_map={},
        redis=AsyncMock(),
    )
    ctx = RunContext(
        deps=deps,
        retry=0,
        messages=[],
        prompt="",
        model=TestModel(),
        usage=RunUsage(),
    )

    result = await apply_referral_code(ctx, "NOOR-ABC12")

    assert "not launched" in result.lower()
    assert "manager" in result.lower()
    mock_db.flush.assert_not_awaited()
