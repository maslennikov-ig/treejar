from __future__ import annotations

from src.llm.response_policy import (
    ReplyPolicyState,
    apply_first_turn_opening_guard,
    guard_premature_quote_detail_collection,
    render_reply,
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


def test_selling_turn_guards_need_only_explicit_state() -> None:
    """The three selling-turn guards, read through the one path that ships them.

    This replaces a test of `apply_selling_turn_guard`, the composition they
    shared. Declaring each guard separately removed the composition, and the
    end-to-end path is the coverage whose absence let the bundle's mode go
    unnoticed in the first place.
    """

    guarded = render_reply(
        "Which category suits you? What quantity do you need?",
        state=ReplyPolicyState(language="en", is_first_turn=False),
        provenance="model",
    )

    assert guarded.text == "Which category suits you?"
    assert guarded.flags == ()


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
