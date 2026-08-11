from __future__ import annotations

from src.llm.response_policy import (
    apply_first_turn_opening_guard,
    apply_selling_turn_guard,
    guard_premature_quote_detail_collection,
    repair_closed_questions,
)


def test_first_turn_opening_guard_needs_only_explicit_state() -> None:
    guarded = apply_first_turn_opening_guard(
        "I can help with office furniture.",
        language="en",
        is_first_turn=True,
        customer_name=None,
        anchor_line=None,
    )

    assert guarded.startswith("Hello, I'm Noor from Treejar.")
    assert guarded.endswith("And how should I address you?")


def test_selling_turn_guard_needs_only_explicit_state() -> None:
    guarded = apply_selling_turn_guard(
        "Which category suits you? What quantity do you need?",
        language="en",
        is_first_turn=False,
        previous_assistant_turns=(),
        customer_name=None,
        owes_company_question=False,
    )

    assert guarded == "Which category suits you?"


def test_closed_question_repair_needs_only_explicit_state() -> None:
    guarded = repair_closed_questions(
        "What is your name?",
        language="en",
        customer_name="Stored Name",
        company=None,
        customer_type=None,
        delivery_address=None,
    )

    assert guarded == (
        "Thank you, Stored Name. I already have your name, so I will continue "
        "with your request."
    )


def test_premature_quote_detail_guard_needs_only_explicit_state() -> None:
    guarded = guard_premature_quote_detail_collection(
        "A suitable package is available.\n\n"
        "For a quotation, please share your delivery address.",
        language="en",
        quote_consent_granted=False,
    )

    assert guarded == (
        "A suitable package is available.\n\n"
        "Would you like me to prepare a formal quotation?"
    )
