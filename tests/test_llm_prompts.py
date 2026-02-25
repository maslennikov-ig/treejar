from src.llm.prompts import build_system_prompt
from src.schemas.common import SalesStage


def test_build_system_prompt_default_language() -> None:
    prompt = build_system_prompt(SalesStage.GREETING.value, language="Russian")

    assert "You are Noor" in prompt
    assert "You work for Treejar" in prompt
    assert "The user prefers to communicate in Arabic" in prompt
    assert "STAGE: GREETING" in prompt


def test_build_system_prompt_custom_language() -> None:
    prompt = build_system_prompt(SalesStage.SOLUTION.value, language="en")

    assert "The user prefers to communicate in English" in prompt
    assert "STAGE: SOLUTION" in prompt


def test_build_system_prompt_unknown_stage() -> None:
    # If a database field has an invalid stage string, we default to generic
    prompt = build_system_prompt("unknown_stage_123", language="Russian")

    # Should contain base rules
    assert "You are Noor" in prompt
    # Shouldn't crash and returns at least the base
    assert len(prompt) > 100
