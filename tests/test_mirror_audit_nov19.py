"""Regression suite for tj-y79o: Nikita Nov 18 shift / Noor mirror audit fixes.

Covers the structural gaps and observed scenarios from the Nov 18 shift and
Nov 17 router-blackout dialogues:
1. Multi-turn non_sales_notice memory in decision_state_directives & permitted_asks (*5256).
2. Warehouse/showroom Freezone status & trigger keywords in FAQ Q8, company_faq, communication_policy, and canonical seed (*2482).
3. Urgent failed phone call attempts trigger HUMAN_REQUESTED escalation (*3939), and GCC destination phrasing in B2B handoff.
4. Residential villa/home furniture and office-supplies/stationery boundaries in FAQ Q26, Rule 14, and canonical seed (*0234, *2203).
5. Observed Nov 18 shift scenarios: Turn 1 delivery+assembly FAQ (*6586), Qatar delivery FAQ (*3939), 200/250 pcs & 130 pcs / 4x8 sets bulk quantities (*6569, *6673).
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.dialogue.decision_state import decision_state_directives
from src.llm.communication_policy import COMMERCIAL_CAPABILITIES
from src.llm.company_faq import active_faq_topics, with_approved_faq
from src.llm.escalation_policy import (
    b2b_handoff_decision,
    critical_escalation_decision,
    wholesale_quantity,
)
from src.llm.message_processor import _Turn
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.schemas.common import EscalationType
from src.services.canonical_admin_seed import canonical_kb_articles


def test_non_sales_notice_persists_in_decision_state_and_suppresses_asks() -> None:
    conv = SimpleNamespace(
        metadata_={
            "non_sales_notice": {
                "intent": "supplier_pitch",
                "summary": "Hengli catalog 2026 PDF pitch",
                "source": "model_tool",
            }
        }
    )
    directives = decision_state_directives(conv, customer_text="Thank you")
    joined = "\n".join(directives)
    assert "NON-SALES INQUIRY LOGGED (supplier_pitch)" in joined
    assert "without asking sales discovery or quotation questions" in joined

    turn = _Turn(
        db=MagicMock(),
        redis=MagicMock(),
        conversation_id=uuid.uuid4(),
        embedding_engine=MagicMock(),
        zoho_client=MagicMock(),
        messaging_client=MagicMock(),
        crm_client=None,
        source_message_id=None,
        latency_trace=None,
        context_started=None,
        conv=conv,
        crm_context=None,
        pii_map={},
        history=[],
        is_first_turn=False,
        model_runtime=MagicMock(),
        current_message_quote_customer_details={},
        combined_text="Thank you",
        masked_text="Thank you",
        recent_history=[],
        deps=MagicMock(),
        prose_guards_mode="trust_model",
    )
    assert turn.permitted_asks() == frozenset()


@pytest.mark.parametrize(
    "query",
    [
        "May we know your warehouse location please. You're not inside the Freezone ?",
        "Are you inside JAFZA free zone? Do we need a gate pass?",
        "Freezone status of your warehouse?",
    ],
)
def test_freezone_and_warehouse_location_inject_showroom_faq(query: str) -> None:
    topics = active_faq_topics(query)
    assert "showroom" in topics

    merged = with_approved_faq(query, [])
    titles = [item["title"] for item in merged]
    assert "Can we visit your showroom?" in titles
    content = merged[0]["content"].lower()
    assert "outside the jafza freezone" in content
    assert "no freezone gate pass" in content


def test_showroom_freezone_followup_and_seed_policy() -> None:
    topics = active_faq_topics(
        "Are you inside Freezone?",
        recent_history=["user: Where is your warehouse located?"],
    )
    assert "showroom" in topics

    assert (
        "outside the jafza freezone"
        in COMMERCIAL_CAPABILITIES["showroom_visit"].instruction.lower()
    )
    kb = canonical_kb_articles()
    showroom = next(a for a in kb if a.title == "Showroom in Dubai")
    assert "outside the jafza freezone" in showroom.content.lower()


@pytest.mark.parametrize(
    "text",
    [
        "I am trying to call you. To the mobile number 54567851",
        "We tried calling your office but no one is answering the phone",
        "Can't reach you by phone, we don't have time",
    ],
)
def test_failed_call_attempt_escalates_as_human_requested(text: str) -> None:
    decision = critical_escalation_decision(customer_text=text)
    assert decision.allowed is True
    assert decision.escalation_type is EscalationType.HUMAN_REQUESTED
    assert decision.trigger == "explicit_human_request"


def test_residential_villa_and_office_supplies_boundaries_in_faq_and_prompts() -> None:
    assert "general office supplies / stationery consumables" in BASE_SYSTEM_PROMPT
    assert "residential villa/home furniture" in BASE_SYSTEM_PROMPT
    assert "catalog PDF" in BASE_SYSTEM_PROMPT

    kb = canonical_kb_articles()
    faq26 = next(a for a in kb if "FAQ: Do you sell petty cash boxes" in a.title)
    assert "general office supplies / stationery consumables" in faq26.content.lower()
    assert "residential villa/home furniture" in faq26.content.lower()

    prod_cat = next(a for a in kb if a.title == "Product categories Treejar supplies")
    assert "office supplies/stationery" in prod_cat.content.lower()
    assert "residential villa/home furniture" in prod_cat.content.lower()


def test_nov18_observed_shift_scenarios_handled_cleanly() -> None:
    # *6586: Turn 1 delivery + assembly question injects both approved FAQ entries
    merged_6586 = with_approved_faq(
        "Hi. I am interested in purchasing office furniture. Could you assist me?\n"
        "Can you deliver it and also assemble it",
        [],
    )
    titles_6586 = {item["title"] for item in merged_6586}
    assert "What is your delivery timeline?" in titles_6586
    assert "Do you provide installation services?" in titles_6586

    # *3939: Qatar delivery inquiry injects delivery FAQ (manager arranges GCC)
    merged_3939 = with_approved_faq("Deliver to Qatar how many days ?", [])
    assert any(
        "qatar" in item["content"].lower()
        and "arranged through a manager" in item["content"].lower()
        for item in merged_3939
    )
    assert wholesale_quantity("48pcs") == 48
    assert b2b_handoff_decision("48pcs").trigger == "wholesale_or_bulk_project"

    # *6569: alternative 200 or 250 pcs still escalates (>= 20)
    assert wholesale_quantity("Qty - 200 pcs or 250 pcs") == 250
    assert (
        b2b_handoff_decision("Qty - 200 pcs or 250 pcs").trigger
        == "wholesale_or_bulk_project"
    )

    # *6673: 130 pcs shelves + 4 sets of 8 chairs
    qty_6673 = wholesale_quantity(
        "Wooden Shelves (90cm x 200cm) – 130 pcs\nTables with 8 Chairs – 4 sets"
    )
    assert qty_6673 >= 130
    assert b2b_handoff_decision("Wooden Shelves – 130 pcs").trigger == (
        "wholesale_or_bulk_project"
    )
