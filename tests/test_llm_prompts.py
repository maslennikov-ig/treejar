from unittest.mock import AsyncMock

import pytest

from src.llm.prompts import build_system_prompt
from src.schemas.common import SalesStage


@pytest.mark.asyncio
async def test_build_system_prompt_default_language() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    prompt = await build_system_prompt(
        db, redis, SalesStage.GREETING.value, language="Russian"
    )

    assert "You are Noor" in prompt
    assert "You work for Treejar" in prompt
    assert "The user prefers to communicate in Arabic" in prompt
    assert "STAGE: GREETING" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_custom_language() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    prompt = await build_system_prompt(
        db, redis, SalesStage.SOLUTION.value, language="en"
    )

    assert "The user prefers to communicate in English" in prompt
    assert "STAGE: SOLUTION" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_unknown_stage() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    # If a database field has an invalid stage string, we default to generic
    prompt = await build_system_prompt(
        db, redis, "unknown_stage_123", language="Russian"
    )

    # Should contain base rules
    assert "You are Noor" in prompt
    # Shouldn't crash and returns at least the base
    assert len(prompt) > 100
