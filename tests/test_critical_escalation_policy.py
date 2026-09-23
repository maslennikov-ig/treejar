from __future__ import annotations

import pytest

from src.llm.escalation_policy import critical_escalation_decision
from src.schemas.common import EscalationType


@pytest.mark.parametrize(
    ("customer_text", "expected_type", "expected_trigger"),
    [
        (
            "I want to speak to a manager, please.",
            EscalationType.HUMAN_REQUESTED,
            "explicit_human_request",
        ),
        (
            "I need a human.",
            EscalationType.HUMAN_REQUESTED,
            "explicit_human_request",
        ),
        (
            "Please have someone call me.",
            EscalationType.HUMAN_REQUESTED,
            "explicit_human_request",
        ),
        (
            "أريد التحدث مع مدير",
            EscalationType.HUMAN_REQUESTED,
            "explicit_human_request",
        ),
        (
            "My order arrived damaged.",
            EscalationType.GENERAL,
            "critical_customer_incident",
        ),
        (
            "I need a refund for my order.",
            EscalationType.GENERAL,
            "critical_customer_incident",
        ),
        (
            "This exposed wire is unsafe.",
            EscalationType.GENERAL,
            "critical_customer_incident",
        ),
        (
            "My payment failed twice.",
            EscalationType.GENERAL,
            "critical_customer_incident",
        ),
    ],
)
def test_only_customer_evidenced_critical_cases_are_allowed(
    customer_text: str,
    expected_type: EscalationType,
    expected_trigger: str,
) -> None:
    decision = critical_escalation_decision(customer_text=customer_text)

    assert decision.allowed is True
    assert decision.escalation_type is expected_type
    assert decision.trigger == expected_trigger


@pytest.mark.parametrize(
    "customer_text",
    [
        "I need a manager desk and four chairs.",
        "I need 200 chairs delivered next week.",
        "Can you make this in a custom colour?",
        "No, thanks.",
        "What is your return policy?",
        "I need a refund policy.",
        "I want a return policy, please.",
        "أريد معرفة سياسة الاسترداد",
        "ما هي شروط إرجاع المنتج؟",
        "The catalog price is missing.",
        "This is ridiculous.",
        "أريد كرسي مدير",
        "Our manager will contact you tomorrow.",
        "How do you prevent payment fraud?",
        "Do your chairs comply with fire safety standards?",
        "I don't need a human, thanks.",
        "I do not want to speak to a manager.",
        "My order is not damaged.",
    ],
)
def test_ordinary_sales_and_policy_cases_stay_autonomous(customer_text: str) -> None:
    decision = critical_escalation_decision(customer_text=customer_text)

    assert decision.allowed is False
    assert decision.escalation_type is None
    assert decision.trigger == "noncritical"


def test_accepted_prepared_quotation_is_allowed() -> None:
    decision = critical_escalation_decision(
        customer_text="Yes, proceed with the quotation.",
        conversation_metadata={"quotation_decision_status": "approved"},
    )

    assert decision.allowed is True
    assert decision.escalation_type is EscalationType.ORDER_CONFIRMATION
    assert decision.trigger == "accepted_quotation"


def test_bare_yes_without_an_accepted_quotation_stays_autonomous() -> None:
    decision = critical_escalation_decision(
        customer_text="yes",
        conversation_metadata={"quotation_decision_status": "pending"},
    )

    assert decision.allowed is False


def test_old_approved_quote_does_not_turn_a_new_yes_into_an_order() -> None:
    decision = critical_escalation_decision(
        customer_text="yes",
        conversation_metadata={"quotation_decision_status": "approved"},
        recent_history=(
            "assistant: Would you like the chairs in black?",
            "user: yes",
        ),
    )

    assert decision.allowed is False


def test_old_critical_message_does_not_escalate_an_empty_current_turn() -> None:
    decision = critical_escalation_decision(
        customer_text="",
        recent_history=("user: I want to speak to a manager",),
    )

    assert decision.allowed is False


def test_recorded_acceptance_of_sent_quote_allows_short_current_reply() -> None:
    decision = critical_escalation_decision(
        customer_text="That works, go ahead",
        conversation_metadata={"quotation_decision_status": "approved"},
        quote_acceptance_recorded_this_turn=True,
    )

    assert decision.allowed is True
    assert decision.escalation_type is EscalationType.ORDER_CONFIRMATION


def test_approved_quote_does_not_escalate_order_question() -> None:
    decision = critical_escalation_decision(
        customer_text="Can you confirm the order details?",
        conversation_metadata={"quotation_decision_status": "approved"},
    )

    assert decision.allowed is False


@pytest.mark.parametrize(
    "customer_text",
    [
        "I do not accept the quotation.",
        "Do not proceed with the order.",
        "I reject the quotation.",
    ],
)
def test_negated_or_rejected_quotation_never_escalates(customer_text: str) -> None:
    decision = critical_escalation_decision(
        customer_text=customer_text,
        conversation_metadata={"quotation_decision_status": "approved"},
    )

    assert decision.allowed is False


def test_explicit_acceptance_must_be_recorded_before_escalation() -> None:
    decision = critical_escalation_decision(
        customer_text="I accept the quotation, please proceed.",
        conversation_metadata={
            "quotation_decision_status": "pending",
            "proposal_followup": {"sent_at": "2026-09-22T10:00:00+00:00"},
        },
    )

    assert decision.allowed is False


def test_bare_yes_after_quote_question_must_be_recorded_before_escalation() -> None:
    decision = critical_escalation_decision(
        customer_text="yes",
        conversation_metadata={
            "quotation_decision_status": "pending",
            "proposal_followup": {"sent_at": "2026-09-22T10:00:00+00:00"},
        },
        recent_history=(
            "assistant: Does the quotation work for you?",
            "user: yes",
        ),
    )

    assert decision.allowed is False
