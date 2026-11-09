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


# --- *6551: deferred team-check variations, quote-turn FAQ, & CRM Deal sync ---


@pytest.mark.parametrize(
    "reply_text",
    [
        # Exact *6551 Turn 3 wording (no article before "confirmation")
        (
            "Ready-stock delivery to Abu Dhabi takes *2–5 business days*. "
            "The payment method and earliest delivery date after payment remain "
            "unconfirmed; I’ll check these with our sales team and return with "
            "confirmation."
        ),
        # Exact *6551 Turn 4 wording ("sales team" in sentence 1, "I’ll check" in sentence 2)
        (
            "Your email is recorded as *Bashar@bonmarche.vip*.\n\n"
            "*Quotation Fr4364* for *12 × CH 145 grey* has been prepared and sent.\n\n"
            "The delivery charge, payment method and earliest delivery date after "
            "payment still need confirmation from our sales team. I’ll check these "
            "and return with an update."
        ),
        # Two straight-apostrophe contractions on the same line must not be eaten by _QUOTED_SPAN_RE
        (
            "I've noted TRN 104397709700003; I'll check these with our sales team "
            "and return with confirmation."
        ),
    ],
)
def test_pilot_6551_deferred_team_check_variants_are_detected(reply_text: str) -> None:
    assert has_deferred_team_check_promise(reply_text) is True


@pytest.mark.parametrize(
    "reply_text",
    [
        # *6551 Turn 2: passive policy disclosure + clarifying question, no promise to check now
        (
            "Delivery: 2–3 business days to Dubai or Sharjah; 2–5 business days to "
            "other UAE emirates. Delivery is charged; an exact date requires manager "
            "confirmation.\n\nWhich emirate will we deliver to?"
        ),
        # *6551 Turn 5: showroom scheduling question, no deferred check promise
        (
            "You’re welcome to visit. The visit time and whether the *CH 145 grey* "
            "is on display to try need to be arranged with our manager.\n\n"
            "When would you like to visit?"
        ),
    ],
)
def test_pilot_6551_passive_manager_mentions_stay_negative(reply_text: str) -> None:
    assert has_deferred_team_check_promise(reply_text) is False


def test_pilot_6551_email_continuation_retains_delivery_faq_and_grounds_400_aed() -> (
    None
):
    from src.llm.catalog_planning import SalesDeps, grounded_amounts_for_turn
    from src.llm.company_faq import with_approved_faq

    recent_history = [
        (
            "user: 1) My name is Bashar, from Bon Marche Interior Design. "
            "2) Delivery to Abu Dhabi (Al Shawamekh). "
            "3) Please send a formal quotation for 12 × CH 145 grey, including "
            "the delivery charge to Abu Dhabi."
        ),
        (
            "assistant: Ready-stock delivery to Abu Dhabi takes *2–5 business days*. "
            "What email address should I use for your formal quotation, including "
            "the delivery charge?"
        ),
    ]
    faq_ctx = with_approved_faq("[EMAIL_1]", [], recent_history=recent_history)
    assert any("AED 400" in item["content"] for item in faq_ctx)

    # Later unrelated showroom question after the email turn does not keep delivery FAQ active
    later_history = [
        *recent_history,
        "user: Bashar@bonmarche.vip",
        "assistant: Quotation Fr4364 has been prepared and sent.",
    ]
    assert (
        with_approved_faq("Where's your showroom?", [], recent_history=later_history)
        == []
    )

    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971501036551",
        language="en",
        escalation_status="none",
        metadata_={},
    )
    deps = SalesDeps(
        db=AsyncMock(),
        redis=AsyncMock(),
        conversation=conv,
        embedding_engine=AsyncMock(),
        zoho_inventory=AsyncMock(),
        zoho_crm=None,
        messaging_client=AsyncMock(),
        pii_map={},
        faq_context=faq_ctx,
        recent_history=recent_history,
        quotation_subtotal=7920.0,
    )
    grounded = set(grounded_amounts_for_turn(deps, customer_text="[EMAIL_1]") or ())
    assert {400.0, 420.0, 7920.0, 8316.0, 8320.0, 8736.0} <= grounded


@pytest.mark.asyncio
async def test_pilot_6551_create_quotation_auto_syncs_zoho_crm_contact_and_deal(
    authorized_outbound_unit_path: None,
) -> None:
    from unittest.mock import MagicMock

    from pydantic_ai import RunContext
    from pydantic_ai.models.test import TestModel
    from pydantic_ai.usage import RunUsage

    from src.llm.engine import QuotationItem, SalesDeps, create_quotation

    conv = Conversation(
        id=uuid.uuid4(),
        phone="+971501036551",
        customer_name="Bashar",
        language="en",
        sales_stage="qualifying",
        escalation_status="none",
        metadata_={
            "quote_customer_details": {
                "name": "Bashar",
                "company": "Bon Marche Interior Design",
                "email": "Bashar@bonmarche.vip",
                "address": "Abu Dhabi (Al Shawamekh)",
            },
            "order_runtime": {
                "quote_workflow": {
                    "version": 2,
                    "consent": "granted",
                    "lifecycle": "quote_requested",
                }
            },
        },
    )
    db = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    product = SimpleNamespace(
        sku="CH 145 grey NEW",
        name_en="Executive Office Chair CH 145 grey NEW",
        price=660.0,
        currency="AED",
        image_url=None,
        attributes={"treejar_slug": "ch-145-grey"},
        zoho_item_id="item-145",
    )
    exec_res = MagicMock()
    exec_res.scalar_one_or_none.return_value = product
    db.execute.return_value = exec_res

    zoho_inv = AsyncMock()
    zoho_inv.get_stock_bulk_fresh.return_value = [
        {
            "sku": "CH 145 grey NEW",
            "item_id": "item-145",
            "name": "Executive Office Chair CH 145 grey NEW",
            "description": "Grey mesh executive chair",
            "stock_on_hand": 167,
            "rate": 660.0,
            "currency_code": "AED",
        }
    ]
    zoho_inv.find_customer_by_phone.return_value = {"contact_id": "inv-cust-6551"}
    zoho_inv.create_sale_order.return_value = {
        "saleorder": {
            "salesorder_id": "378603000026478948",
            "salesorder_number": "Fr4364",
            "status": "draft",
        }
    }

    zoho_crm = AsyncMock()
    zoho_crm.find_contact_by_phone.side_effect = [
        None,
        {"id": "crm-contact-6551", "Phone": "+971501036551"},
    ]
    zoho_crm.create_contact.return_value = {"details": {"id": "crm-contact-6551"}}
    zoho_crm.create_deal.return_value = {"details": {"id": "crm-deal-6551"}}
    zoho_crm.get_deal_status.return_value = {
        "id": "crm-deal-6551",
        "Stage": "New Lead",
        "Deal_Name": "Bon Marche Interior Design - Quotation Fr4364",
        "Contact_Name": {"id": "crm-contact-6551"},
        "Amount": 7920.0,
    }

    messaging = AsyncMock()
    messaging.send_media.return_value = "wazzup-pdf-msg-6551"

    deps = SalesDeps(
        db=db,
        conversation=conv,
        embedding_engine=AsyncMock(),
        zoho_inventory=zoho_inv,
        zoho_crm=zoho_crm,
        messaging_client=messaging,
        pii_map={},
        redis=AsyncMock(),
        source_message_id="msg-8e5a658a",
    )
    ctx = RunContext(
        deps=deps, retry=0, messages=[], prompt="", model=TestModel(), usage=RunUsage()
    )

    with (
        patch(
            "src.services.pdf.generator.render_quotation_html",
            return_value="<html>Fr4364</html>",
        ),
        patch(
            "src.services.pdf.generator.generate_pdf", AsyncMock(return_value=b"%PDF")
        ),
    ):
        result = await create_quotation(
            ctx, [QuotationItem(sku="CH 145 grey NEW", quantity=12)]
        )

    assert "Quotation Fr4364 has been prepared and sent" in result
    assert "AED 7,920.00 excl. 5% VAT" in result
    assert "AED 8,316.00 incl. 5% VAT" in result
    assert deps.quotation_subtotal == 7920.0
    assert conv.zoho_contact_id == "crm-contact-6551"
    assert conv.zoho_deal_id == "crm-deal-6551"
    assert conv.deal_amount == 7920.0
    assert conv.deal_status == "New Lead"
    zoho_crm.create_contact.assert_awaited_once()
    zoho_crm.create_deal.assert_awaited_once()
