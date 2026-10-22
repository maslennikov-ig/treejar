"""tj-asty.2/.3: Treejar B2B handoff routes and canonical product links."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.dialogue.claim_contract import b2b_handoff_reference_directive
from src.llm.engine import _turn_runtime_directives
from src.llm.escalation_policy import (
    b2b_handoff_buckets,
    critical_escalation_decision,
)
from src.llm.escalation_tools import escalate_to_manager
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.llm.response_policy import AskKind, ReplyPolicyState, render_reply
from src.models.product_links import product_canonical_url
from src.schemas.common import EscalationType

LAYAN_PROJECT = (
    "شكراً. لدينا أيضاً مشروع لتجهيز الطابق بالكامل: نحتاج 55 محطة عمل، بالإضافة "
    "إلى تفصيل طاولة اجتماعات خاصة بطول 4.5 متر من خشب الجوز مع وحدات كهرباء "
    "مدمجة، ونريد خصم جملة خاص. كيف نرتب ذلك؟"
)


@pytest.mark.parametrize(
    ("text", "trigger"),
    [
        ("We need 55 workstations for the new floor.", "wholesale_or_bulk_project"),
        ("I need 200 chairs delivered next week.", "wholesale_or_bulk_project"),
        ("Can we get a wholesale discount on chairs?", "wholesale_or_bulk_project"),
        ("نحتاج 30 كرسي للمكتب", "wholesale_or_bulk_project"),
        ("نحتاج ٥٥ محطة عمل", "wholesale_or_bulk_project"),
        (LAYAN_PROJECT, "wholesale_or_bulk_project"),
        (
            "We need a custom 4.5-meter solid walnut boardroom table with built-in "
            "power modules.",
            "custom_made_to_order",
        ),
        ("Do you make bespoke reception desks?", "custom_made_to_order"),
        ("تفصيل طاولة اجتماعات خاصة بطول 4.5 متر", "custom_made_to_order"),
        ("Do you sell laboratory fume hoods?", "specialist_out_of_catalog_scope"),
        ("We also need medical autoclaves.", "specialist_out_of_catalog_scope"),
        ("هل لديكم خزانة أبخرة مختبر؟", "specialist_out_of_catalog_scope"),
    ],
)
def test_b2b_routes_authorize_the_handoff(text: str, trigger: str) -> None:
    decision = critical_escalation_decision(customer_text=text)

    assert decision.allowed is True
    assert decision.trigger == trigger
    assert decision.escalation_type is EscalationType.GENERAL


def test_layan_project_names_both_wholesale_and_made_to_order() -> None:
    assert b2b_handoff_buckets(LAYAN_PROJECT) == (
        "wholesale_or_bulk_project",
        "custom_made_to_order",
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hi, I'm Aisha. Please check the current price and stock for CH 616 NEW "
        "black. I need 4 chairs. No quotation yet.",
        "I want 1 chair CH 616 NEW black and 3 chairs CH 460 black",
        "We need 3 workstations of SKYLAND LUMA 9719-4, budget 6,000 AED. "
        "No quotation needed yet.",
        "مرحباً، اسمي ليان. نجهز مكتباً جديداً في دبي لـ 6 موظفين ونحتاج محطة عمل "
        "لـ 6 أشخاص مع 6 كراسي مكتبية مريحة، والميزانية الإجمالية 10,000 درهم.",
        "We're furnishing a new office for 25 people.",
        "Is the 2400 mm NOVO table available?",
        "Can you make this in a custom colour?",
        "Do you have a lab-style standing desk?",
        "What is the delivery cost for 3 desks in Dubai?",
        "Nothing found? Fine, no quotation yet.",
        "Our budget is 20,000 AED for 10 chairs.",
    ],
)
def test_ordinary_office_furniture_requests_never_hand_off(text: str) -> None:
    assert critical_escalation_decision(customer_text=text).allowed is False
    assert b2b_handoff_buckets(text) == ()


def test_wholesale_turn_earns_the_reference_handoff_directive() -> None:
    directives = _turn_runtime_directives(LAYAN_PROJECT, sales_stage="solution")

    reference = b2b_handoff_reference_directive("wholesale_or_bulk_project")
    assert reference in directives
    # One consultative handoff directive, not one per route.
    assert b2b_handoff_reference_directive("custom_made_to_order") not in directives
    assert "search_products" in reference and "escalate_to_manager" in reference
    assert "company name, target delivery timeline" in reference


def test_fume_hood_turn_earns_the_non_pausing_directive() -> None:
    directives = _turn_runtime_directives(
        "Do you sell laboratory fume hoods? Also 3 LUMA 9719-4 workstations?",
        sales_stage="greeting",
    )
    specialist = b2b_handoff_reference_directive("specialist_out_of_catalog_scope")
    assert specialist in directives
    assert "does not pause you" in specialist


def test_prompt_contract_matches_the_policy() -> None:
    assert "Treejar B2B handoff routes" in BASE_SYSTEM_PROMPT
    never_section = BASE_SYSTEM_PROMPT.split("NEVER escalate for:", 1)[1].split(
        "Escalate only", 1
    )[0]
    assert "wholesale, MOQ" not in never_section
    assert "bulk" not in never_section
    assert "ordinary no-match search" in never_section


def _ctx(user_query: str, metadata: dict[str, Any] | None = None) -> Any:
    conversation = SimpleNamespace(
        escalation_status="none", metadata_=metadata or {}, id="conv-1"
    )
    deps = SimpleNamespace(
        conversation=conversation,
        recent_history=["user: " + user_query],
        user_query=user_query,
        db=object(),
        quote_acceptance_recorded_this_turn=False,
    )
    return SimpleNamespace(deps=deps)


@pytest.mark.asyncio
async def test_specialist_lead_notifies_without_pausing_the_bot() -> None:
    ctx = _ctx("Do you sell laboratory fume hoods?")
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        result = await escalate_to_manager(ctx, reason="fume hood sourcing")
        repeat = await escalate_to_manager(ctx, reason="fume hood sourcing")

    assert notify.await_count == 1
    assert notify.await_args.kwargs["pause_bot"] is False
    assert "Assistant brief: fume hood sourcing" in notify.await_args.kwargs["reason"]
    assert "you stay in the conversation" in result
    assert "already has this sourcing request" in repeat
    assert ctx.deps.conversation.metadata_["manager_sourcing_leads_notified"] == [
        "specialist_out_of_catalog_scope"
    ]


@pytest.mark.asyncio
async def test_wholesale_handoff_pauses_and_asks_for_references_and_brief() -> None:
    ctx = _ctx(LAYAN_PROJECT)
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        result = await escalate_to_manager(ctx, reason="55 workstations project")

    assert notify.await_args.kwargs["pause_bot"] is True
    assert "2-3 standard in-stock catalog reference options" in result
    assert "company name, target" in result


@pytest.mark.asyncio
async def test_ordinary_turn_still_cannot_create_an_escalation() -> None:
    ctx = _ctx("No quotation yet, just the price of CH 460 black.")
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        result = await escalate_to_manager(ctx, reason="unsure")

    notify.assert_not_awaited()
    assert "Escalation was not created" in result


def test_handoff_brief_question_survives_the_reply_policy() -> None:
    text = (
        "A manager will take over the project pricing. What is your company "
        "name, target delivery timeline and delivery location in the UAE?"
    )
    state = ReplyPolicyState(
        language="en", permitted_asks=frozenset({AskKind.SALES_DISCOVERY})
    )
    blocked = render_reply(text, state=state, provenance="model").text
    allowed = render_reply(
        text,
        state=ReplyPolicyState(
            language="en",
            permitted_asks=frozenset({AskKind.SALES_DISCOVERY}),
            handoff_brief_allowed=True,
        ),
        provenance="model",
    ).text

    assert "company name" not in blocked
    assert allowed == text


@pytest.mark.parametrize(
    ("attributes", "name", "expected"),
    [
        (
            {"treejar_url": "https://new.treejartrading.ae/product/luma-9719-4?x=1"},
            "x",
            "https://treejartrading.ae/product/luma-9719-4",
        ),
        (
            {"treejar_slug": "4p-ws-table-skyland-novo-2400"},
            "x",
            "https://treejartrading.ae/product/4p-ws-table-skyland-novo-2400",
        ),
        ({"treejar_url": "https://pub-abc.r2.dev/img.png"}, "x", None),
        ({"source": "treejar"}, "x", None),
        (
            None,
            "Four person workstation SKYLAND LUMA 9719-4",
            "https://treejartrading.ae/product/four-person-workstation-skyland-luma-9719-4",
        ),
    ],
)
def test_product_canonical_url(
    attributes: dict[str, Any] | None, name: str, expected: str | None
) -> None:
    product = SimpleNamespace(attributes=attributes, name_en=name)
    assert product_canonical_url(product) == expected
