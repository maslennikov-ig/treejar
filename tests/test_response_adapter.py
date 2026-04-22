"""Tests for the manager response adapter agent."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from src.llm.response_adapter import (
    ManagerReplyWithAutoFAQResult,
    adapt_manager_response,
    adapt_manager_response_with_faq_candidate,
    response_adapter_agent,
)
from src.services.auto_faq_types import AutoFAQCandidate


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_manager_response_returns_string() -> None:
    """Basic test: adapter returns a non-empty string."""
    with response_adapter_agent.override(model=TestModel()):
        result = await adapt_manager_response(
            question="Do you have ergonomic chairs?",
            draft="yes, CH-200 available, 599 AED",
        )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_preserves_factual_content() -> None:
    """Agent should preserve factual content from the draft."""
    with response_adapter_agent.override(
        model=TestModel(
            custom_output_text=(
                "Thank you for your interest! Yes, we have the *CH-200* "
                "ergonomic chair available for *599 AED*. "
                "Would you like to know more?"
            )
        )
    ):
        result = await adapt_manager_response(
            question="Do you have ergonomic chairs?",
            draft="yes, CH-200, 599 AED",
        )
    assert "599" in result
    assert "CH-200" in result


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_handles_arabic_question() -> None:
    """Adapter should handle Arabic input gracefully."""
    with response_adapter_agent.override(
        model=TestModel(
            custom_output_text="شكراً لتواصلكم! نعم، الكرسي CH-200 متوفر بسعر 599 درهم."
        )
    ):
        result = await adapt_manager_response(
            question="هل عندكم كراسي مريحة؟",
            draft="نعم CH-200 متوفر 599",
        )
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_empty_draft() -> None:
    """Adapter should handle empty draft without crashing."""
    with response_adapter_agent.override(model=TestModel()):
        result = await adapt_manager_response(
            question="When will the desk be in stock?",
            draft="",
        )
    assert isinstance(result, str)


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_manager_response_passes_expected_llm_safety_kwargs() -> None:
    with patch(
        "src.llm.response_adapter.response_adapter_agent.run",
        new=AsyncMock(return_value=SimpleNamespace(output="Polished answer")),
    ) as mock_run:
        result = await adapt_manager_response(
            question="Do you have CH-200?",
            draft="yes, 599 AED",
        )

    assert result == "Polished answer"
    call_kwargs = mock_run.await_args.kwargs
    assert call_kwargs["model_settings"]["max_tokens"] == 700
    assert call_kwargs["usage_limits"].request_limit == 1
    assert call_kwargs["usage_limits"].output_tokens_limit == 700
    assert call_kwargs["usage_limits"].total_tokens_limit == 3000


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normal_manager_reply_does_not_generate_kb_candidate() -> None:
    with (
        patch(
            "src.llm.response_adapter.response_adapter_agent.run",
            new=AsyncMock(return_value=SimpleNamespace(output="Polished answer")),
        ) as mock_adapter_run,
        patch(
            "src.llm.response_adapter.auto_faq_manager_reply_agent.run",
            new=AsyncMock(side_effect=AssertionError("unexpected FAQ candidate call")),
        ) as mock_combined_run,
    ):
        result = await adapt_manager_response(
            question="Do you have CH-200?",
            draft="yes, 599 AED",
        )

    assert result == "Polished answer"
    mock_adapter_run.assert_awaited_once()
    mock_combined_run.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_manager_response_with_faq_candidate_uses_one_combined_call() -> (
    None
):
    combined_output = ManagerReplyWithAutoFAQResult(
        customer_message="Delivery takes 3-5 business days in the UAE.",
        kb_candidate=AutoFAQCandidate(
            question="What is the delivery time in the UAE?",
            answer="Delivery takes 3-5 business days in the UAE.",
            confidence=0.91,
        ),
    )
    with patch(
        "src.llm.response_adapter.auto_faq_manager_reply_agent.run",
        new=AsyncMock(return_value=SimpleNamespace(output=combined_output)),
    ) as mock_run:
        result = await adapt_manager_response_with_faq_candidate(
            question="When can you deliver?",
            draft="3-5 business days UAE",
            language="en",
        )

    assert result.customer_message == "Delivery takes 3-5 business days in the UAE."
    assert result.kb_candidate == combined_output.kb_candidate
    mock_run.assert_awaited_once()
    call_kwargs = mock_run.await_args.kwargs
    assert call_kwargs["model_settings"]["max_tokens"] == 900
    assert call_kwargs["usage_limits"].request_limit == 1
    assert call_kwargs["usage_limits"].output_tokens_limit == 900
    assert call_kwargs["usage_limits"].total_tokens_limit == 3500
