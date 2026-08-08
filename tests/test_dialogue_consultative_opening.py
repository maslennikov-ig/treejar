"""The three sentences Noor never says.

Measured on 2026-08-07 by scoring all ten stored acceptance transcripts
criterion by criterion. Rule 7, Treejar's value proposition: zero in ten of
ten. Rule 13, asking what the customer's company does: zero in five of five
where it applies. Rule 6, a compliment or thanks: four of a possible twenty.
Rules 1 and 2, the greeting and the introduction, are a perfect twenty of
twenty — so this is not a bot that cannot open a conversation. It is one that
opens it and then never says why the customer should care, never asks who they
are, and rarely thanks them.

Like the sizing and comparison directives beside it, these tests are about the
**customer request** and the typed stage, never the reply text: a lexical
backstop over generated text is on the specification's rejected list.
"""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    consultative_opening_directive,
    defers_the_purchase,
    earns_consultative_opening,
    next_contact_directive,
    substantive_reply_directive,
)

# --- the trigger ------------------------------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        # The opening turns of the stored scenarios, as the customer sent them.
        "Hi! We are furnishing a new office and I need help choosing furniture.",
        "We need chairs for twelve call-center staff below AED 400 each.",
        "Do you sell laboratory fume hoods and chemical-resistant lab benches?",
        # And the reply to the name gate, which carries no request at all and is
        # exactly where the value proposition and the company question belong.
        "My name is Maya, and I am the facilities manager at Cedarline Test.",
        "My name is Samir.",
        "مرحباً، نجهز مكتباً في دبي لستة موظفين ونحتاج محطات عمل خاصة.",
    ],
)
def test_a_turn_that_is_still_building_the_sale_earns_the_directive(
    request_text: str,
) -> None:
    assert earns_consultative_opening(request_text, sales_stage="qualifying") is True


@pytest.mark.parametrize(
    "sales_stage",
    ["greeting", "qualifying", "needs_analysis"],
)
def test_every_early_stage_earns_it(sales_stage: str) -> None:
    assert earns_consultative_opening("We need desks", sales_stage=sales_stage) is True


@pytest.mark.parametrize(
    "sales_stage",
    ["solution", "company_details", "quoting", "closing", "feedback", "", "unknown"],
)
def test_a_conversation_past_the_opening_does_not_earn_it(sales_stage: str) -> None:
    """Rule 7 belongs to the opening. Repeating what Treejar is at the quoting
    stage is not selling, it is padding."""

    assert earns_consultative_opening("We need desks", sales_stage=sales_stage) is False


@pytest.mark.parametrize(
    "request_text",
    [
        # S06: one exact SKU, no alternatives, no quotation.
        (
            "Please check the exact live price and stock for SKU CH 616 NEW "
            "black. I may need twelve units, but I do not want a quotation."
        ),
        (
            "Confirm from live inventory whether twelve units of that exact "
            "SKU are available and state the unit price. Do not suggest "
            "alternatives or offer a quotation."
        ),
        # S09: a quotation for an exact quantity at a confirmed price.
        (
            "Please prepare a formal quotation for exactly four CH 616 NEW "
            "black chairs at the current confirmed price."
        ),
        "Show me only these two, no alternatives and no upsell.",
        "Just the price of the LUMA 9719-4, nothing else.",
        "لا تقترح بدائل، أريد هذا الصنف فقط.",
    ],
)
def test_a_customer_who_has_narrowed_the_request_is_left_alone(
    request_text: str,
) -> None:
    """S06 and S09 are the reason this half exists.

    Both were marked down by the checklist for not consulting on turns where
    the customer had ruled consultation out. The answer to that is not to
    consult anyway; it is `tj-swgu.11` on the scoring side and this stand-down
    on the dialogue side.
    """

    assert earns_consultative_opening(request_text, sales_stage="qualifying") is False


def test_an_empty_turn_earns_nothing() -> None:
    """Same as the two detectors beside it: no text, no directive."""

    assert earns_consultative_opening("", sales_stage="qualifying") is False
    assert earns_consultative_opening("   ", sales_stage="qualifying") is False


# --- the directive ----------------------------------------------------------


def test_the_directive_names_the_three_moves_that_scored_zero() -> None:
    directive = consultative_opening_directive()
    lowered = directive.casefold()

    # Rule 7, zero in ten of ten.
    assert "what treejar offers" in lowered
    assert "one short clause" in lowered
    # Rule 6, four of twenty.
    assert "acknowledge the project" in lowered
    # Rule 13, zero in five of five where it applies.
    assert "what their company does" in lowered


def test_the_value_proposition_is_not_discharged_by_the_greeting() -> None:
    """The escape clause that made rule 7 unreachable, removed 2026-08-08.

    `src/llm/opening_guard.py` prepends "Hello, I'm Noor from Treejar." to every
    first turn, so "if you have not already said it" was satisfied by the same
    reply the directive was asking to change. Naming the company and saying what
    it offers are different acts, and the directive must say so.
    """

    lowered = consultative_opening_directive().casefold()

    assert "if you have not already said it" not in lowered
    assert "does not discharge this" in lowered
    assert "the greeting names treejar" in lowered


def test_the_company_question_is_folded_rather_than_deferred() -> None:
    """The starvation that made rule 13 unreachable, removed 2026-08-08.

    There is always a more urgent product question, so "leave it for the next
    turn" deferred the company question on every turn forever. Folding it into
    the same sentence costs nothing and is how a salesperson asks it anyway.
    """

    lowered = consultative_opening_directive().casefold()

    assert "in the same sentence as whatever else you need to know" in lowered
    assert "counts as one question" in lowered
    assert "leave it for the next turn" not in lowered
    # The bound itself stays: the transcripts were never interrogations.
    assert "at most one question" in lowered


def test_no_move_is_gated_on_what_noor_thinks_she_already_did() -> None:
    """The audit rule, 2026-08-08.

    A condition on the world is a guard; a condition on the assistant's own
    past behaviour or judgement is where a rule dies quietly, because the model
    is both the actor and the judge of whether it already acted. Two rules died
    that way before anyone noticed. These clauses stay out.
    """

    lowered = consultative_opening_directive().casefold()

    for escape in (
        "once per conversation",
        "if you have not already",
        "you do not know what their company does",
        "plainly missing",
        "once you know it",
    ):
        assert escape not in lowered, escape

    # And the two that replaced them are anchored to this reply, not to memory.
    assert lowered.count("in this reply") >= 2
    assert "knowing the company's name is not knowing its line of work" in lowered


def test_the_directive_bounds_itself_against_the_reply_it_shares_a_turn_with() -> None:
    """Two directives can fire on one turn, and both want a question. Without
    this bound the customer gets an interrogation instead of an answer."""

    lowered = consultative_opening_directive().casefold()

    assert "at most one question" in lowered
    assert "before answering" in lowered


def test_the_directive_unlocks_no_fact_and_no_commercial_term() -> None:
    """Rule 11 wants an incentive and stays at zero on purpose: a discount is a
    commitment nobody has authorised. The sibling comparison directive forbids
    one in the same words."""

    lowered = consultative_opening_directive().casefold()

    assert "never offer a discount or a bonus" in lowered
    assert "you have not verified" in lowered


def test_the_directive_carries_the_job_and_the_widening() -> None:
    """Rules 9 and 10, added 2026-08-08 on the owner's decision that Noor may
    widen past the literal request from the catalog."""

    lowered = consultative_opening_directive().casefold()

    # Rule 9, the job to be done rather than the words of the request.
    assert "what the furniture is for" in lowered
    assert "rather than against the words of the request" in lowered
    # Rule 10, one missing piece, verified before it is named.
    assert "do not stop at the item they named" in lowered
    assert "search_products" in lowered
    assert "one piece, not a list" in lowered


def test_the_widening_is_a_package_and_never_a_discount() -> None:
    """Rule 11's honest form. A combined total over verified rows commits
    nothing; a discount is a commercial commitment nobody has authorised."""

    lowered = consultative_opening_directive().casefold()

    assert "one package with a combined total" in lowered
    assert "a package, never a discount" in lowered
    assert "never offer a discount or a bonus" in lowered


def test_the_directive_does_not_grow_the_product_system_prompt() -> None:
    """Raised from 900 on 2026-08-08 when rules 9, 10 and 11 joined it. One
    directive on a shared trigger beats three, but it is not free."""

    assert len(consultative_opening_directive()) < 1700


# --- not buying today -------------------------------------------------------


@pytest.mark.parametrize(
    "request_text",
    [
        "We are not ready to order yet, but keep the details.",
        "Do not create a quotation for now.",
        "Please continue without a quotation.",
        # S08 turn 5, where the refusal is restated rather than repeated.
        "Correction: the team is now twelve. Keep the no-quotation instruction.",
        "I need to discuss it internally before we commit.",
        "Let me think about it and I will get back to you.",
        "We are waiting for budget approval.",
        "Let us pick this up next month.",
        "لسنا مستعدين للشراء الآن.",
        "بدون عرض سعر من فضلك.",
    ],
)
def test_a_customer_who_is_not_buying_today_earns_a_next_contact(
    request_text: str,
) -> None:
    assert defers_the_purchase(request_text) is True


@pytest.mark.parametrize(
    "request_text",
    [
        "Please prepare a formal quotation for exactly four CH 616 NEW black chairs.",
        "We need chairs for twelve call-center staff below AED 400 each.",
        "Do you deliver and assemble in Dubai?",
        "We plan to buy twenty CH 616 NEW black chairs this month.",
        # A date is a deadline until the customer attaches it to talking again.
        "We need 20 chairs for next week, what options do you have?",
        "Delivery has to land next month at the latest.",
        "",
        "   ",
    ],
)
def test_a_customer_who_is_still_buying_is_not_pushed_into_a_calendar(
    request_text: str,
) -> None:
    assert defers_the_purchase(request_text) is False


def test_the_next_contact_directive_proposes_a_time_and_promises_nothing() -> None:
    lowered = next_contact_directive().casefold()

    assert "propose one specific time" in lowered
    assert "confirm it" in lowered
    # A follow-up nobody scheduled is the unverified commitment the contract
    # exists to stop.
    assert "unless a tool call in this conversation did it" in lowered


# --- the reply that says nothing --------------------------------------------


def test_the_substantive_directive_separates_the_ban_from_the_silence() -> None:
    """S08's defect in one sentence: a ban on a quotation became a ban on
    selling."""

    lowered = substantive_reply_directive().casefold()

    assert "the restriction the customer actually stated and nothing wider" in lowered
    assert "has not ruled out prices" in lowered


def test_the_substantive_directive_forbids_the_bulleted_echo() -> None:
    lowered = substantive_reply_directive().casefold()

    assert "add at least one thing the customer did not already have" in lowered


def test_padding_an_echo_with_a_promise_is_still_an_echo() -> None:
    """The escape clause S08 walked through, removed 2026-08-08.

    Its turns are a restatement plus "I'll keep these details in mind", so the
    restatement was never the *whole* content and the prohibition never bound.
    The test is now what the reply adds, not what it consists of.
    """

    lowered = substantive_reply_directive().casefold()

    assert "whole content" not in lowered
    assert "adding one to the other does not make" in lowered
    assert "must not be sent" in lowered


def test_the_substantive_directive_does_noors_own_next_step() -> None:
    """S08's closing turn proposes as the customer's next step an action Noor
    holds the tools to perform."""

    lowered = substantive_reply_directive().casefold()

    assert "your tools can do now" in lowered
    assert "instead of handing it back to them" in lowered
    assert "a row you verified this turn" in lowered
