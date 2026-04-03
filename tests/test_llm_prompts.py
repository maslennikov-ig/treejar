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


@pytest.mark.asyncio
async def test_build_system_prompt_prioritizes_concrete_orders_without_false_positives() -> (
    None
):
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None

    prompt = await build_system_prompt(
        db, redis, SalesStage.GREETING.value, language="en"
    )

    assert "Product questions, even about wholesale/MOQ/bulk pricing" in prompt
    assert "a concrete order on the first turn" in prompt
    assert "already gave enough order details" in prompt
    assert "escalate immediately" in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_requires_immediate_handoff_for_first_turn_concrete_orders() -> (
    None
):
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None

    prompt = await build_system_prompt(
        db, redis, SalesStage.GREETING.value, language="en"
    )

    assert "I need 200 chairs delivered to Dubai Marina by next week" in prompt
    assert "exact street address, SKU, or price approval is not required" in prompt
    assert (
        "before any qualifying questions, stage advancement, or product search"
        in prompt
    )
    assert '"I need ... delivered/installed"' in prompt


@pytest.mark.asyncio
async def test_build_system_prompt_preserves_non_escalation_examples_for_bulk_questions() -> (
    None
):
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None

    prompt = await build_system_prompt(
        db, redis, SalesStage.GREETING.value, language="en"
    )

    assert "What is your MOQ for chairs?" in prompt
    assert "What are your wholesale prices for bulk orders?" in prompt
    assert "We may need 200 chairs later, what options do you have?" in prompt
    assert "We need 20 chairs for next week, what options do you have?" in prompt
    assert (
        "If the same message is still asking for options, ideas, recommendations,"
        in prompt
    )


@pytest.mark.asyncio
async def test_build_system_prompt_caps_product_search_retries() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None

    prompt = await build_system_prompt(
        db, redis, SalesStage.SOLUTION.value, language="en"
    )

    assert "at most ONE silent retry" in prompt
    assert "Never do more than 2 `search_products` calls" in prompt
    assert "Never send an interim message like" in prompt
    assert "Let me try a more specific search for you" in prompt
