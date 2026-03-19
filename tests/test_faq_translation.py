"""Tests for _normalize_to_english and adapt_manager_response.

M1: Verifies translation parsing, fallback on bad format, and fallback on exception.
M2: Verifies that adapt_manager_response includes the language in the prompt.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ====================================================================
# M1: Tests for _normalize_to_english
# ====================================================================


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_to_english_success() -> None:
    """Test successful Q&A parsing from LLM output."""
    from src.services.auto_faq import _normalize_to_english

    mock_result = MagicMock()
    mock_result.output = "Q: What is the delivery time?\nA: Delivery takes 3-5 days."

    with patch("src.services.auto_faq._translate_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        q, a = await _normalize_to_english(
            "ما هو وقت التسليم؟", "التسليم يستغرق 3-5 أيام"
        )

    assert q == "What is the delivery time?"
    assert a == "Delivery takes 3-5 days."


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_to_english_parsing_fallback() -> None:
    """Test fallback when LLM output doesn't contain the expected Q/A format."""
    from src.services.auto_faq import _normalize_to_english

    mock_result = MagicMock()
    mock_result.output = "Here is the translation without proper formatting"

    with patch("src.services.auto_faq._translate_agent") as mock_agent:
        mock_agent.run = AsyncMock(return_value=mock_result)
        q, a = await _normalize_to_english("оригинал", "ответ")

    assert q == "оригинал"
    assert a == "ответ"


@pytest.mark.asyncio
@pytest.mark.unit
async def test_normalize_to_english_exception_fallback() -> None:
    """Test fallback when LLM call raises an exception."""
    from src.services.auto_faq import _normalize_to_english

    with patch("src.services.auto_faq._translate_agent") as mock_agent:
        mock_agent.run = AsyncMock(side_effect=RuntimeError("API error"))
        q, a = await _normalize_to_english("вопрос", "ответ")

    assert q == "вопрос"
    assert a == "ответ"


# ====================================================================
# M2: Test for adapt_manager_response with language parameter
# ====================================================================


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
            draft="коллега свяжется через 5 минут",
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
            draft="коллега свяжется через 5 минут",
        )

    assert result == "Our colleague will contact you within 5 minutes."
    call_args = mock_agent.run.call_args[0][0]
    assert "'en'" in call_args
