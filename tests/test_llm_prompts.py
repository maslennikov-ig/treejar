from unittest.mock import AsyncMock, patch

import pytest

from src.llm.communication_policy import (
    COMMERCIAL_CAPABILITIES,
    EVIDENCE_GROUNDING_POLICY,
)
from src.llm.prompts import build_system_prompt
from src.schemas.common import SalesStage


@pytest.mark.asyncio
async def test_build_system_prompt_default_language() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    prompt = await build_system_prompt(
        db, redis, SalesStage.GREETING.value, language="ru"
    )

    assert "You are Noor" in prompt
    assert "You work for Treejar" in prompt
    assert "The user prefers to communicate in English" in prompt
    assert "Russian" not in prompt
    assert "ОАЭ" not in prompt
    assert "STAGE: GREETING" in prompt
    assert "Noor from Treejar" in prompt
    assert "ask how you should address them" in prompt


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
async def test_build_system_prompt_includes_compact_communication_policy() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None

    prompt = await build_system_prompt(
        db, redis, SalesStage.SOLUTION.value, language="en"
    )

    marker = "[COMMUNICATION RULES POLICY]"
    assert marker in prompt
    policy = prompt.split(marker, maxsplit=1)[1].split(
        "IMPORTANT: The user prefers", maxsplit=1
    )[0]
    assert "Source: docs/04-sales-dialogue-guidelines.md" in policy
    assert "preserved RU" not in policy
    assert "Opening and trust" in policy
    assert "sincere, specific compliment" in policy
    assert "tailors solutions" in policy
    assert "solution, not just a product" in policy
    assert "multiple options" in policy
    assert "approved discount" in policy
    assert "FU1 before the 24h WhatsApp window closes" in policy
    assert "3d/7d via allowed templates" in policy
    assert "exact next step" in policy
    assert "Правило" not in policy
    assert len(policy) < 1600


@pytest.mark.asyncio
async def test_build_system_prompt_keeps_policy_when_base_prompt_is_overridden() -> (
    None
):
    db, redis = AsyncMock(), AsyncMock()

    async def fake_component(
        _db: AsyncMock, _redis: AsyncMock, name: str, default: str
    ) -> str:
        if name == "base_prompt":
            return "CUSTOM BASE PROMPT"
        if name.startswith("stage_"):
            return "CUSTOM STAGE RULE"
        return default

    with patch(
        "src.llm.prompts.get_system_prompt_component",
        side_effect=fake_component,
    ):
        prompt = await build_system_prompt(
            db, redis, SalesStage.SOLUTION.value, language="en"
        )

    assert "CUSTOM BASE PROMPT" in prompt
    assert "[COMMUNICATION RULES POLICY]" in prompt
    assert "CUSTOM STAGE RULE" in prompt
    assert prompt.index("CUSTOM BASE PROMPT") < prompt.index(
        "[COMMUNICATION RULES POLICY]"
    )
    assert prompt.index("[COMMUNICATION RULES POLICY]") < prompt.index(
        "The user prefers to communicate in English"
    )
    assert prompt.index("The user prefers to communicate in English") < prompt.index(
        "CUSTOM STAGE RULE"
    )


def test_commercial_capability_registry_uses_evidence_authorization_modes() -> None:
    expected_modes = {
        "showroom_visit": "direct",
        "project_samples": "conditional",
        "stock": "tool_required",
        "operational_price": "tool_required",
        "quotation": "tool_required",
        "order_status": "tool_required",
        "discount": "manager_required",
        "exceptional_terms": "manager_required",
    }

    assert {
        name: capability.mode for name, capability in COMMERCIAL_CAPABILITIES.items()
    } == expected_modes
    assert "docs/faq.md" in COMMERCIAL_CAPABILITIES["showroom_visit"].source
    assert "specific product will be available to try" in (
        COMMERCIAL_CAPABILITIES["showroom_visit"].instruction
    )
    assert "depending on project requirements" in (
        COMMERCIAL_CAPABILITIES["project_samples"].instruction
    )


@pytest.mark.asyncio
async def test_build_system_prompt_appends_immutable_evidence_grounding_policy() -> (
    None
):
    db, redis = AsyncMock(), AsyncMock()

    async def fake_component(
        _db: AsyncMock, _redis: AsyncMock, name: str, default: str
    ) -> str:
        if name == "base_prompt":
            return "CUSTOM BASE PROMPT WITHOUT GROUNDING"
        if name == "communication_rules_policy":
            return "CUSTOM COMMUNICATION POLICY WITHOUT GROUNDING"
        if name.startswith("stage_"):
            return "CUSTOM STAGE RULE WITHOUT GROUNDING"
        return default

    with patch(
        "src.llm.prompts.get_system_prompt_component",
        side_effect=fake_component,
    ):
        prompt = await build_system_prompt(
            db, redis, SalesStage.SOLUTION.value, language="en"
        )

    marker = "[EVIDENCE GROUNDING POLICY]"
    assert marker in EVIDENCE_GROUNDING_POLICY
    assert prompt.count(marker) == 1
    assert prompt.index("CUSTOM BASE PROMPT") < prompt.index(marker)
    assert prompt.index("CUSTOM COMMUNICATION POLICY") < prompt.index(marker)
    assert prompt.index("CUSTOM STAGE RULE") < prompt.index(marker)
    assert "Unknown or unconfirmed does not mean unavailable" in prompt
    assert "Do not infer medical" in prompt
    assert "showroom_visit [direct]" in prompt
    assert "project_samples [conditional]" in prompt
    assert "stock [tool_required]" in prompt
    assert "discount [manager_required]" in prompt
    assert "use one verified tool, one useful clarification, or manager handoff" in (
        prompt
    )
    assert "never offer or promise to check, confirm, look up, or verify it later" in (
        prompt
    )


@pytest.mark.asyncio
async def test_build_system_prompt_unknown_stage() -> None:
    db, redis = AsyncMock(), AsyncMock()
    redis.get.return_value = None
    db.execute.return_value.scalars.return_value.first.return_value = None
    # If a database field has an invalid stage string, we default to generic
    prompt = await build_system_prompt(db, redis, "unknown_stage_123", language="ru")

    # Should contain base rules
    assert "You are Noor" in prompt
    assert "The user prefers to communicate in English" in prompt
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
