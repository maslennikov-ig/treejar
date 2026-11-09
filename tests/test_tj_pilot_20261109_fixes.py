"""Regression tests for 2026-11-09 live-pilot dialogue fixes (tj-41ra).

1. *6040 (a440e45c): customer shared paid website order B2C-20261109-5702 asking
   about showroom pickup readiness; check_order_status had no linked deal and
   Noor promised 5 times to check with the showroom/order team and get back
   without alerting any manager.
2. *5892 (c1822de7): off-topic wrong-number/personal/matchmaking chat ran 26
   turns, called the caller "حبيبي يا هاني", asked personal follow-up questions,
   and drafted a marriage bio.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.llm import LLMResponse, message_processor
from src.llm.escalation_policy import (
    NON_PAUSING_HANDOFF_TRIGGERS,
    critical_escalation_decision,
    external_order_support_decision,
)
from src.llm.escalation_tools import escalate_to_manager
from src.llm.message_processor import has_deferred_team_check_promise
from src.llm.outbound_reply_guard import finalize_customer_reply_text
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.models.conversation import Conversation
from src.schemas.common import EscalationType


def _turn(
    text: str,
    *,
    metadata: dict[str, Any] | None = None,
    escalation_status: str = "none",
) -> Any:
    conversation = Conversation(
        id=uuid.uuid4(),
        phone="+971500006040",
        language="en",
        escalation_status=escalation_status,
        metadata_=metadata or {},
    )
    return SimpleNamespace(
        combined_text=text,
        db=AsyncMock(),
        deps=SimpleNamespace(
            conversation=conversation,
            recent_history=["user: Hi"],
        ),
    )


def _tool_ctx(user_query: str, metadata: dict[str, Any] | None = None) -> Any:
    conversation = SimpleNamespace(
        escalation_status="none",
        metadata_=metadata or {},
        id=uuid.uuid4(),
    )
    deps = SimpleNamespace(
        conversation=conversation,
        recent_history=["user: " + user_query],
        user_query=user_query,
        db=AsyncMock(),
        quote_acceptance_recorded_this_turn=False,
    )
    return SimpleNamespace(deps=deps)


# --- *6040: external order support & deferred team-check promises -------------


@pytest.mark.parametrize(
    "customer_text",
    [
        (
            "Order number: B2C-20261109-5702\nStatus: Completed\n"
            "Hi, can I confirm if the order is ready for collection today?"
        ),
        "I have already paid on website. Just wonder when I can collect.",
        "Can you check Order #SO-10492 pickup readiness?",
        "رقم الطلب: B2C-20261109-5702 هل الطلب جاهز للاستلام اليوم؟",
    ],
)
def test_external_order_inquiry_is_allowed_as_non_pausing_support(
    customer_text: str,
) -> None:
    assert "external_order_support" in NON_PAUSING_HANDOFF_TRIGGERS
    decision = critical_escalation_decision(customer_text=customer_text)
    assert decision.allowed is True
    assert decision.escalation_type is EscalationType.GENERAL
    assert decision.trigger == "external_order_support"


def test_linked_sale_order_keeps_ordinary_status_check_autonomous() -> None:
    decision = external_order_support_decision(
        "Order number: B2C-20261109-5702 — is it ready?",
        conversation_metadata={"zoho_sale_order_id": "99887766"},
    )
    assert decision.allowed is False


@pytest.mark.asyncio
async def test_escalate_to_manager_on_external_order_alerts_once_without_pausing() -> (
    None
):
    ctx = _tool_ctx(
        "Order number: B2C-20261109-5702\nStatus: Completed\n"
        "Can I confirm if the order is ready for collection today?"
    )
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        first = await escalate_to_manager(ctx, reason="Website order pickup check")
        second = await escalate_to_manager(ctx, reason="Website order pickup check")

    notify.assert_awaited_once()
    assert notify.await_args.kwargs["pause_bot"] is False
    assert ctx.deps.conversation.escalation_status == "none"
    assert "stay in the conversation" in first
    assert "do not create another alert" in second.casefold()


@pytest.mark.parametrize(
    "reply_text",
    [
        (
            "I can’t see order *B2C-20261109-5702* linked to this WhatsApp chat. "
            "I will check its preparation and pickup readiness with our showroom "
            "and warehouse team and come back to you with the confirmation."
        ),
        (
            "I’ll check with our showroom/order team on the pickup readiness for "
            "*B2C-20261109-5702* and get back to you."
        ),
        "Let me confirm the floor model with our showroom team and return with the answer.",
        "سأتحقق مع فريق المعرض بخصوص جاهزية الطلب وأعود إليك بالتأكيد.",
        (
            "The payment method and earliest delivery date after payment remain unconfirmed; "
            "I’ll check these with our sales team and return with confirmation."
        ),
        (
            "The delivery charge, payment method and earliest delivery date after payment "
            "still need confirmation from our sales team. I’ll check these and return with an update."
        ),
        "سأتحقق من ذلك مع الإدارة وأعود إليك بالتفاصيل.",
    ],
)
def test_deferred_team_check_promises_are_detected(reply_text: str) -> None:
    assert has_deferred_team_check_promise(reply_text) is True


@pytest.mark.parametrize(
    "reply_text",
    [
        "Here are 3 ergonomic mesh chairs in stock in Sharjah.",
        "Current stock is unconfirmed. The note says, 'I will check with our team and get back to you.'",
        "You are welcome to visit our showroom in Sharjah to try the chair.",
        "I will check our catalog for executive chairs.",
        "Let me check the dimensions of this chair: it is 120cm high.",
    ],
)
def test_ordinary_or_quoted_replies_are_not_flagged_as_team_promises(
    reply_text: str,
) -> None:
    assert has_deferred_team_check_promise(reply_text) is False


@pytest.mark.asyncio
async def test_runtime_followup_alerts_manager_once_when_model_skips_tool() -> None:
    turn = _turn(
        "Order number: B2C-20261109-5702\nStatus: Completed\n"
        "Can I confirm if the order is ready for collection today?"
    )
    reply = LLMResponse(
        text=(
            "I will check its preparation and pickup readiness with our showroom "
            "and warehouse team and come back to you with the confirmation."
        ),
        tokens_in=10,
        tokens_out=20,
        cost=0.001,
        model="openai/gpt-6.1-sol",
    )
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        first = await message_processor._deterministic_team_followup_notice(turn, reply)
        second = await message_processor._deterministic_team_followup_notice(
            turn, reply
        )

    assert first == "external_order_support"
    assert second is None
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["pause_bot"] is False
    assert turn.deps.conversation.escalation_status == "none"


@pytest.mark.asyncio
async def test_runtime_followup_alerts_on_unsolicited_team_check_promise() -> None:
    turn = _turn("Is the grey CH 620 currently on display on the showroom floor?")
    reply = LLMResponse(
        text=(
            "CH 620 has 19 units in warehouse stock. I’ll check with the showroom "
            "team whether a grey unit is on the display floor and come back to you."
        ),
        tokens_in=10,
        tokens_out=20,
        cost=0.001,
        model="openai/gpt-6.1-sol",
    )
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        kind = await message_processor._deterministic_team_followup_notice(turn, reply)

    assert kind == "deferred_team_check"
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["pause_bot"] is False


# --- *5892: corporate off-topic boundary & endearment guard -------------------


def test_base_prompt_forbids_personal_matchmaking_chat_and_habibi() -> None:
    lower = BASE_SYSTEM_PROMPT.casefold()
    assert "matchmaking" in lower
    assert "marriage or dating profiles" in lower
    assert '"habibi"' in lower
    assert "do not ask personal follow-up questions" in lower


def test_outbound_guard_strips_arabic_and_english_habibi() -> None:
    arabic_reply = "حبيبي يا هاني، هذا الرقم مخصص لاستفسارات أثاث المكاتب من Treejar."
    cleaned_ar = finalize_customer_reply_text(arabic_reply, language="ar")
    assert "حبيب" not in cleaned_ar
    assert cleaned_ar.startswith("يا هاني،")

    arabic_clause = "شكراً لتواصلك معنا يا حبيبي."
    cleaned_clause = finalize_customer_reply_text(arabic_clause, language="ar")
    assert "حبيب" not in cleaned_clause
    assert cleaned_clause == "شكراً لتواصلك معنا."

    english_reply = "Thank you, habibi, how can I help with office furniture today?"
    cleaned_en = finalize_customer_reply_text(english_reply, language="en")
    assert "habibi" not in cleaned_en.casefold()
