import pytest
from pydantic_ai.models.test import TestModel

from src.core.escalation import (
    EscalationEvaluation,
    escalation_agent,
    evaluate_escalation_triggers,
)


@pytest.mark.asyncio
async def test_evaluate_escalation_triggers_true() -> None:
    # pydantic_ai's TestModel automatically returns mock data that matches the output schema
    with escalation_agent.override(
        model=TestModel(
            custom_output_args={
                "should_escalate": True,
                "reason": "B2B / Wholesale inquiry",
            }
        )
    ):
        result = await evaluate_escalation_triggers(
            "We are a hotel chain looking to buy 50 pieces."
        )

    assert result.should_escalate is True
    assert result.reason and "B2B" in result.reason


@pytest.mark.asyncio
async def test_evaluate_escalation_triggers_false() -> None:
    with escalation_agent.override(
        model=TestModel(custom_output_args={"should_escalate": False, "reason": None})
    ):
        result = await evaluate_escalation_triggers("How much is this chair?")

    assert result.should_escalate is False
    assert result.reason is None


def test_escalation_evaluation_schema() -> None:
    eval = EscalationEvaluation(should_escalate=True, reason="Test")
    assert eval.should_escalate is True
    assert eval.reason == "Test"
