"""Regression tests for 2026-11-19 live pilot audit (*1201 and *9005)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.dialogue.decision_state import decision_state_directives
from src.llm.engine import check_order_status
from src.llm.escalation_policy import (
    b2b_handoff_buckets,
    critical_escalation_decision,
)
from src.schemas.common import EscalationType


def _make_ctx(*, language: str, metadata: dict) -> SimpleNamespace:
    conversation = SimpleNamespace(
        language=language,
        metadata_=metadata,
        zoho_deal_id=None,
    )
    deps = SimpleNamespace(
        conversation=conversation,
        zoho_inventory=AsyncMock(),
        zoho_crm=None,
    )
    return SimpleNamespace(deps=deps)


@pytest.mark.parametrize("language", ["en", "ar"])
def test_non_pausing_external_order_notification_is_visible_in_decision_state(
    language: str,
) -> None:
    conversation = SimpleNamespace(
        language=language,
        metadata_={"manager_sourcing_leads_notified": ["external_order_support"]},
    )
    directives = decision_state_directives(
        conversation,
        customer_text="can you share with me invoice",
    )
    assert any(
        "ALREADY been notified about this unlinked external order inquiry" in d
        for d in directives
    )


def test_team_followup_notice_is_visible_in_decision_state() -> None:
    conversation = SimpleNamespace(
        language="en",
        metadata_={
            "team_followup_notice": {"kind": "deferred_team_check"},
            "manager_sourcing_leads_notified": ["specialist_out_of_catalog_scope"],
        },
    )
    directives = decision_state_directives(
        conversation,
        customer_text="Any update?",
    )
    assert any(
        "specialist_out_of_catalog_scope, deferred_team_check" in d
        and "ALREADY received an internal notification" in d
        for d in directives
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("metadata", "language", "expected_fragment"),
    [
        (
            {"manager_sourcing_leads_notified": ["external_order_support"]},
            "en",
            "ALREADY been notified to review this external order reference",
        ),
        (
            {"team_followup_notice": {"kind": "external_order_support"}},
            "ar",
            "تم إبلاغ فريقنا مسبقاً للتحقق من مرجع الطلب الخارجي",
        ),
    ],
)
async def test_check_order_status_preserves_prior_external_order_escalation(
    metadata: dict,
    language: str,
    expected_fragment: str,
) -> None:
    ctx = _make_ctx(language=language, metadata=metadata)
    result = await check_order_status(ctx)
    assert expected_fragment in result


@pytest.mark.asyncio
async def test_check_order_status_default_unchanged_without_escalation() -> None:
    ctx = _make_ctx(language="en", metadata={})
    result = await check_order_status(ctx)
    assert (
        result
        == "No order found linked to this conversation. The customer may not have a confirmed deal yet."
    )


@pytest.mark.parametrize(
    "text",
    [
        "Hello Do you make customized Chair ?",
        "Like this is also ok we need as a prototype",
        "Can you make a custom bar stool for our lounge?",
        "نريد تفصيل كرسي خاص للمعرض",
    ],
)
def test_custom_seating_and_prototype_trigger_custom_made_to_order(text: str) -> None:
    assert "custom_made_to_order" in b2b_handoff_buckets(text)
    decision = critical_escalation_decision(customer_text=text)
    assert decision.allowed is True
    assert decision.trigger == "custom_made_to_order"
    assert decision.escalation_type is EscalationType.GENERAL


def test_custom_colour_still_does_not_trigger_made_to_order() -> None:
    assert "custom_made_to_order" not in b2b_handoff_buckets(
        "Can you make this in a custom colour?"
    )
