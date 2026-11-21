"""Regression suite for tj-9f5e: Nikita Nov 20 shift / Noor mirror audit fixes.

Covers the structural gaps and observed scenarios from the Nov 20 shift and
Nov 19/21 router-blackout dialogues:
1. B2B buyer vendor/supplier onboarding & compliance requests (*2248, *2203)
   route to non-pausing `b2b_vendor_onboarding` via `escalate_to_manager` and
   are never flagged as `supplier_pitch` by `non_sales_intent`.
2. Post-nominal custom furniture requests ("office desk customised" in *1654)
   and prompt guidance for unspecified-quantity custom requests.
3. Residential bedside tables / nightstands exclusion vs commercial office
   pedestals in FAQ Q26, Rule 14, and canonical KB seed (*3589).
4. Wazzup `?filename=...` query parameter extraction in `_filename_hint` and
   unreadable spreadsheet guidance (*3438).
5. Real multi-word Russian text does not trigger `keyboard_layout_reading`
   false positives while short Cyrillic layout slips still work (*3438).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dialogue.decision_state import (
    decision_state_directives,
    keyboard_layout_reading,
)
from src.llm.escalation_policy import (
    NON_PAUSING_HANDOFF_TRIGGERS,
    b2b_handoff_buckets,
    b2b_vendor_onboarding_decision,
    critical_escalation_decision,
)
from src.llm.escalation_tools import escalate_to_manager
from src.llm.non_sales_intent import non_sales_intent
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.schemas.common import EscalationType
from src.services.canonical_admin_seed import canonical_kb_articles
from src.services.inbound_media import _filename_hint


def test_b2b_vendor_onboarding_triggers_non_pausing_escalation_and_not_supplier_pitch() -> (
    None
):
    buyer_pdf_note = (
        '[The customer sent a document "Calidus_External Supplier Registration.pdf". '
        "It contains: External supplier registration form for Calidus.]"
    )
    assert non_sales_intent(buyer_pdf_note) is None
    assert (
        non_sales_intent("Please share your Trade License and vendor registration")
        is None
    )

    decision = b2b_vendor_onboarding_decision(buyer_pdf_note)
    assert decision.allowed is True
    assert decision.trigger == "b2b_vendor_onboarding"
    assert decision.escalation_type is EscalationType.GENERAL
    assert "b2b_vendor_onboarding" in NON_PAUSING_HANDOFF_TRIGGERS

    full_decision = critical_escalation_decision(
        customer_text="Can you please share trade license and TRN certificate?"
    )
    assert full_decision.allowed is True
    assert full_decision.trigger == "b2b_vendor_onboarding"

    # Cold inbound supplier pitches must still NOT trigger buyer vendor onboarding
    cold_pitch = "We are a manufacturer in China and want to become your supplier."
    assert b2b_vendor_onboarding_decision(cold_pitch).allowed is False
    assert non_sales_intent(cold_pitch) == "supplier_pitch"


@pytest.mark.asyncio
async def test_escalate_to_manager_b2b_vendor_onboarding_is_non_pausing_and_deduped() -> (
    None
):
    conv = SimpleNamespace(
        id=uuid.uuid4(),
        escalation_status="none",
        metadata_={},
    )
    deps = SimpleNamespace(
        conversation=conv,
        user_query='[The customer sent a document "Calidus_External Supplier Registration.pdf". It contains: Vendor registration form]',
        recent_history=[],
        db=MagicMock(),
        quote_acceptance_recorded_this_turn=False,
    )
    ctx = SimpleNamespace(deps=deps)

    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation",
        notify,
    ):
        first = await escalate_to_manager(
            ctx,  # type: ignore[arg-type]
            reason="Corporate buyer sent External Supplier Registration form",
            escalation_type="general",
        )
        second = await escalate_to_manager(
            ctx,  # type: ignore[arg-type]
            reason="Repeat vendor onboarding check",
            escalation_type="general",
        )

    assert "you stay in the conversation" in first
    assert "Trade License or TRN" in first
    assert "already has this B2B vendor-onboarding" in second
    notify.assert_awaited_once()
    assert notify.await_args.kwargs["pause_bot"] is False
    assert conv.metadata_["manager_sourcing_leads_notified"] == [
        "b2b_vendor_onboarding"
    ]

    directives = decision_state_directives(
        conv, customer_text="Any update on the form?"
    )
    assert any(
        "B2B vendor-onboarding or compliance document request" in d for d in directives
    )


def test_post_nominal_custom_desk_and_prompt_guidance() -> None:
    assert "custom_made_to_order" in b2b_handoff_buckets(
        "Hello need a office desk customised"
    )
    normalized_prompt = " ".join(BASE_SYSTEM_PROMPT.split())
    assert "without stating a multi-unit/project quantity" in normalized_prompt
    assert (
        "ask for quantity and offer ready-stock alternatives first" in normalized_prompt
    )
    assert "External Supplier/Vendor Registration PDF" in normalized_prompt


def test_bedside_boundary_in_faq_rule14_and_canonical_seed() -> None:
    assert "bedside tables / nightstands" in BASE_SYSTEM_PROMPT
    assert "bedside" in BASE_SYSTEM_PROMPT

    kb = canonical_kb_articles()
    faq26 = next(a for a in kb if "FAQ: Do you sell petty cash boxes" in a.title)
    assert "bedside tables / nightstands" in faq26.content.lower()

    prod_cat = next(a for a in kb if a.title == "Product categories Treejar supplies")
    assert "bedside tables/nightstands" in prod_cat.content.lower()


def test_wazzup_filename_query_hint_and_unreadable_spreadsheet_prompt() -> None:
    msg = SimpleNamespace(media=None)
    url = "https://store.wazzup24.com/125628bcca299cf4a4d154b59cceb090349bccee/?filename=for%20sc%20rate%20(1).xlsx"
    assert _filename_hint(msg, url, "") == "for sc rate (1).xlsx"
    assert "resend it as `.xlsx` or `.pdf`" in BASE_SYSTEM_PROMPT


def test_cyrillic_russian_sentence_not_treated_as_keyboard_layout_slip() -> None:
    assert keyboard_layout_reading("Привет! Мне нужна офисная мебель") is None
    assert keyboard_layout_reading("Добрый день, подскажите цену") is None
    # Short layout slip still recognised
    assert keyboard_layout_reading("ыгку") == ("Russian", "sure")
    assert keyboard_layout_reading("руддщ") == ("Russian", "hello")
