"""Tests for trusting strong model prose while preserving factual grounding (tj-r62i.8)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.llm import engine, message_processor
from src.llm.escalation_tools import report_non_sales_inquiry
from src.llm.response_policy import (
    AskKind,
    ReplyPolicyState,
    render_reply,
    resolve_trust_model_prose,
)
from src.models.conversation import Conversation


def test_resolve_trust_model_prose_modes() -> None:
    assert resolve_trust_model_prose("auto", "anthropic/claude-sonnet-5.5") is True
    assert resolve_trust_model_prose("auto", "anthropic/claude-haiku-5.5") is True
    assert resolve_trust_model_prose("auto", "mock-model") is False
    assert resolve_trust_model_prose("trust_model", "mock-model") is True
    assert resolve_trust_model_prose("legacy", "anthropic/claude-sonnet-5.5") is False


def test_trust_model_prose_preserves_natural_opening_without_splicing() -> None:
    raw = (
        "Hello and welcome! 🌷\n\n"
        "I'm Noor from Treejar — we supply office furniture across the UAE. "
        "What kind of space are you looking to furnish?"
    )
    rendered = render_reply(
        raw,
        state=ReplyPolicyState(
            language="en",
            is_first_turn=True,
            permitted_asks=frozenset({AskKind.SALES_DISCOVERY, AskKind.CUSTOMER_NAME}),
            trust_model_prose=True,
        ),
        provenance="model",
    )
    assert rendered.text == raw
    assert "how should I address you" not in rendered.text


def test_trust_model_prose_never_splices_quotation_question_onto_supplier_reply() -> (
    None
):
    raw = (
        "Mark, thank you for reaching out.\n\n"
        "This WhatsApp line is for office furniture customers, so please send your "
        "company profile to the official email address on treejartrading.ae."
    )
    rendered = render_reply(
        raw,
        state=ReplyPolicyState(
            language="en",
            is_first_turn=True,
            quote_consent_granted=False,
            trust_model_prose=True,
        ),
        provenance="model",
    )
    assert rendered.text == raw
    assert "Would you like me to prepare a formal quotation?" not in rendered.text


def test_trust_model_prose_still_enforces_price_grounding() -> None:
    raw = "This ergonomic chair is 499 AED excl. VAT."
    rendered = render_reply(
        raw,
        state=ReplyPolicyState(
            language="en",
            is_first_turn=False,
            grounded_amounts=(),
            trust_model_prose=True,
        ),
        provenance="model",
    )
    assert any(flag.guard_name == "grounding_output" for flag in rendered.flags)


@pytest.mark.asyncio
async def test_report_non_sales_inquiry_tool_logs_once_without_pausing() -> None:
    registered = engine.sales_agent._function_toolset.tools
    assert "report_non_sales_inquiry" in registered
    assert registered["report_non_sales_inquiry"].sequential is True

    conversation = Conversation(
        id=uuid.uuid4(),
        phone="+8615138904919",
        language="en",
        escalation_status="none",
        metadata_={},
    )
    ctx = SimpleNamespace(
        deps=SimpleNamespace(
            conversation=conversation,
            recent_history=["Hi, we are a steel furniture manufacturer in China."],
            user_query="May I have the WhatsApp number of your purchasing manager?",
            db=AsyncMock(),
        )
    )
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        first = await report_non_sales_inquiry(
            ctx,  # type: ignore[arg-type]
            inquiry_type="supplier_pitch",
            summary="Mark from ZXD Steel Furniture pitching Chinese metal cabinets",
        )
        second = await report_non_sales_inquiry(
            ctx,  # type: ignore[arg-type]
            inquiry_type="supplier_pitch",
            summary="Mark follow-up",
        )

    assert "commercial team" in first
    assert "Already logged" in second
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["pause_bot"] is False
    assert conversation.escalation_status == "none"
    assert conversation.metadata_["non_sales_notice"]["source"] == "model_tool"


@pytest.mark.asyncio
async def test_trust_model_prose_skips_regex_non_sales_intent() -> None:
    conversation = Conversation(
        id=uuid.uuid4(),
        phone="+971500000001",
        language="en",
        escalation_status="none",
        metadata_={},
    )
    turn = SimpleNamespace(
        combined_text="We are a cargo and freight logistics services firm looking for 15 chairs",
        db=AsyncMock(),
        deps=SimpleNamespace(conversation=conversation, recent_history=[]),
        trusts_model_prose=lambda: True,
    )
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        result = await message_processor._non_sales_team_notice(turn)  # type: ignore[arg-type]

    assert result is None
    notify.assert_not_awaited()
