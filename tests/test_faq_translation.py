"""Tests for adapt_manager_response language handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_manager_response_passes_language() -> None:
    """Test that adapt_manager_response includes language code in the user prompt."""
    from src.llm.response_adapter import adapt_manager_response

    mock_result = MagicMock()
    mock_result.output = "مرحبًا! سيتصل بك زميلنا خلال 5 دقائق."

    with patch("src.llm.response_adapter.response_adapter_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        result = await adapt_manager_response(
            question="I need help",
            draft="a colleague will be in touch in 5 minutes",
            language="ar",
        )

    assert result == "مرحبًا! سيتصل بك زميلنا خلال 5 دقائق."
    # Verify language was included in the prompt
    call_args = mock_agent.run.call_args[0][0]
    assert "'ar'" in call_args


@pytest.mark.asyncio
@pytest.mark.unit
async def test_adapt_manager_response_defaults_to_english() -> None:
    """Test that language defaults to 'en' when not specified."""
    from src.llm.response_adapter import adapt_manager_response

    mock_result = MagicMock()
    mock_result.output = "Our colleague will contact you within 5 minutes."

    with patch("src.llm.response_adapter.response_adapter_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        result = await adapt_manager_response(
            question="I need help",
            draft="a colleague will be in touch in 5 minutes",
        )

    assert result == "Our colleague will contact you within 5 minutes."
    call_args = mock_agent.run.call_args[0][0]
    assert "'en'" in call_args
