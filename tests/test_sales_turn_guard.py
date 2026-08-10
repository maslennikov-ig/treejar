"""The three things a selling turn owes the customer, and why a guard owns them.

Every case here is a real reply from the `ac36265` packets or a control that
must survive untouched. Rules 11 and 13 and the one-question cap were all given
to the model as directives and all measured at or near zero over 82 blind reads,
so they are guaranteed here instead. `tj-odeq`, `tj-6tx6`.

Rule 11's package total lived here until 2026-08-10 and fired on 0 of 53
packets: it read a mapping written only inside the catalog-decision tool
path, empty on an ordinary selling turn. It went back to a directive, in
positive form this time. `tj-wvo4` holds the terms for bringing it back.
"""

from __future__ import annotations

import pytest

from src.llm.grounding_output import (
    GroundingOutputAction,
    enforce_grounding_output,
)
from src.llm.sales_turn_guard import (
    asks_the_company_activity,
    carry_the_company_question,
    collapse_question_form,
    commit_to_what_you_deferred,
    refuse_to_chase_the_name,
)

# S01 turn 2 at ac36265, verbatim. Five questions in a numbered list, no catalog
# row, and a company activity asserted from the company's name -- which the
# directive forbids in as many words.
S01_TURN_2 = """Hi Maya - nice to meet you. I've noted that you're the \
facilities manager at Cedarline Test Offices, a test-office company.

To recommend the right setup, could you share:

1. How many people or workstations do you need to furnish?
2. Which items are required - desks, ergonomic chairs, meeting-room furniture?
3. Your approximate budget, and when you need the furniture delivered?
4. The delivery location in the UAE, if known?

Also, will you be approving the purchase, or does someone else sign off?"""

# R04 turn 2 at ac36265, verbatim in shape. The four items carry no question
# mark at all: they are nouns under "please share:". Counting question marks
# finds nothing here, which is exactly why the lead-in is what gets matched.
R04_TURN_2 = """Thanks, Leila. I can help you plan a complete office package \
for Business Bay, including:

- 14 desks or workstations
- 14 ergonomic office chairs
- Meeting-room table and chairs

To recommend the right options and confirm availability, please share:

1. Your preferred desk style - individual desks or benching
2. Approximate meeting-room capacity
3. Preferred look or budget range
4. Your target move-in date next month

Once I have those details, I can prepare suitable options."""


def test_a_numbered_list_of_questions_becomes_one_question() -> None:
    collapsed = collapse_question_form(S01_TURN_2)

    assert collapsed.count("?") == 1
    assert "How many people or workstations" in collapsed
    assert "approving the purchase" not in collapsed
    # The lead-in keeps its surviving item rather than pointing at a lone "1.".
    assert "could you share: How many people" in collapsed
    # Nothing but questions is dropped.
    assert "nice to meet you" in collapsed


def test_a_form_with_no_question_mark_is_still_a_form() -> None:
    """The failure counting question marks cannot see."""

    assert R04_TURN_2.count("?") == 0

    collapsed = collapse_question_form(R04_TURN_2)

    assert "Approximate meeting-room capacity" not in collapsed
    assert "Preferred look or budget range" not in collapsed
    assert "target move-in date" not in collapsed
    assert "Your preferred desk style" in collapsed


def test_a_list_of_products_is_selling_and_survives_whole() -> None:
    """The list is innocent; the lead-in asking for information is not."""

    collapsed = collapse_question_form(R04_TURN_2)

    assert "14 desks or workstations" in collapsed
    assert "14 ergonomic office chairs" in collapsed
    assert "Meeting-room table and chairs" in collapsed
    assert "Once I have those details" in collapsed


def test_a_verified_answer_with_one_question_is_left_exactly_alone() -> None:
    reply = "CH 616 NEW black: 295.00 AED each, 36 in stock now. How many do you need?"

    assert collapse_question_form(reply) == reply


def test_two_questions_in_one_paragraph_are_still_two() -> None:
    reply = "Thanks. Which finish would you like? And what is your delivery address?"

    collapsed = collapse_question_form(reply)

    assert collapsed.count("?") == 1
    assert "Which finish" in collapsed


def test_a_reply_that_asks_nothing_is_left_alone() -> None:
    reply = "Your quotation SO-1043 is attached. The total is 8,922.00 AED."

    assert collapse_question_form(reply) == reply


@pytest.mark.parametrize(
    ("text", "asked"),
    [
        ("And what does your company actually do, day to day?", True),
        ("What kind of work does the team do?", True),
        ("وما طبيعة عمل شركتكم فعليًا؟", True),
        # The failure this rule keeps scoring zero on: the company's name read
        # as its line of work. Naming the company is not asking about it.
        ("I've noted you're the facilities manager at Cedarline Test Offices.", False),
        ("Which chair would you prefer?", False),
    ],
)
def test_naming_the_company_is_not_asking_what_it_does(text: str, asked: bool) -> None:
    assert asks_the_company_activity(text) is asked


def test_the_company_question_is_folded_onto_the_reply_not_added_as_a_form() -> None:
    reply = "CH 616 NEW black: 295.00 AED each, 36 in stock. How many do you need?"

    carried = carry_the_company_question(reply, language="en")

    assert carried.startswith(reply)
    assert asks_the_company_activity(carried)


def test_the_company_question_is_not_asked_twice() -> None:
    reply = "Happy to help. What kind of work does the team do?"

    assert carry_the_company_question(reply, language="en") == reply


def test_the_company_question_follows_the_customers_language() -> None:
    carried = carry_the_company_question("شكرًا لك.", language="ar")

    assert "طبيعة عمل" in carried


def test_the_name_is_asked_once_and_then_let_go() -> None:
    """Owner decision of 2026-08-10: a customer who ignores the name question
    has answered it. The median conversation is two messages long; spending the
    second one asking again for something already declined spends the sale."""

    text = "The CH 616 is 295 AED and 36 are in stock. May I know your name?"

    assert (
        refuse_to_chase_the_name(
            text,
            previous_assistant_turns=[
                "Hello, I'm Noor from Treejar. And how should I address you?"
            ],
            customer_name=None,
        )
        == "The CH 616 is 295 AED and 36 are in stock."
    )


def test_the_first_ask_survives() -> None:
    text = "We stock that chair. And how should I address you?"

    assert (
        refuse_to_chase_the_name(
            text,
            previous_assistant_turns=["Hello, I'm Noor from Treejar."],
            customer_name=None,
        )
        == text
    )


def test_a_known_name_is_left_to_the_closed_question_guard() -> None:
    """Two guards, one signal list, and no overlap: this one owns the customer
    who never gave a name, the other owns the one who did."""

    text = "May I know your name?"

    assert (
        refuse_to_chase_the_name(
            text,
            previous_assistant_turns=["May I know your name?"],
            customer_name="Ahmed",
        )
        == text
    )


def test_a_reply_that_is_only_a_repeated_question_is_kept_rather_than_emptied() -> None:
    """An empty message cannot be sent to WhatsApp at all, so a repeated
    question beats no reply. The route that produced it is the defect."""

    text = "May I know your name?"

    assert (
        refuse_to_chase_the_name(
            text,
            previous_assistant_turns=["May I know your name?"],
            customer_name=None,
        )
        == text
    )


def test_the_quote_route_list_form_counts_as_having_asked() -> None:
    """The routes ask as a list item -- "please share: customer name" -- which
    no fixed phrase matches, so the opening guard used to fold a second name
    request onto a reply that already carried one."""

    assert (
        refuse_to_chase_the_name(
            "CH 616 is 295 AED. Before I prepare the quotation, please share: "
            "customer name.",
            previous_assistant_turns=["And how should I address you?"],
            customer_name=None,
        )
        == "CH 616 is 295 AED."
    )


def test_arabic_is_asked_once_too() -> None:
    text = "لدينا هذا الكرسي. وكيف أخاطبك؟"

    assert (
        refuse_to_chase_the_name(
            text,
            previous_assistant_turns=["وكيف أخاطبك؟"],
            customer_name=None,
        )
        == "لدينا هذا الكرسي."
    )


# --- a deferral is not an answer, tj-vz7o.10.1 ----------------------------
#
# Measured 2026-08-10 on real customer opening 819. Asked "will you also
# assembly the desk upon delivery?", the reply closed with "Current stock,
# mobile-drawer options, and whether assembly can be included for delivery
# within 2-3 days still need confirmation." True in every word, and the
# customer still had no idea whether anyone would ever find out.

DEFERRED_ASSEMBLY = (
    "Current stock, mobile-drawer options, and whether assembly can be "
    "included for delivery within 2-3 days still need confirmation.\n\n"
    "Could you please share your delivery area in Dubai?"
)


def test_a_deferred_request_gains_someone_who_will_answer_it() -> None:
    result = commit_to_what_you_deferred(DEFERRED_ASSEMBLY, language="en")

    assert "I'll confirm assembly with our team and come back to you." in result
    assert "Could you please share your delivery area in Dubai?" in result


def test_the_commitment_lands_next_to_the_deferral_not_after_the_question() -> None:
    """A promise that arrives two questions later reads as an afterthought,
    and on WhatsApp the customer's eye stops at the first question anyway."""

    result = commit_to_what_you_deferred(DEFERRED_ASSEMBLY, language="en")

    assert result.index("I'll confirm assembly") < result.index("Could you please")


def test_a_reply_that_already_commits_is_left_alone() -> None:
    text = "Assembly needs confirmation. I will confirm and come back to you."

    assert commit_to_what_you_deferred(text, language="en") == text


def test_stock_alone_never_earns_a_promise_to_chase_it() -> None:
    """`grounding_output` removes a promise to go and check stock on purpose.

    A guard that adds a sentence the next guard deletes is worse than no guard,
    so stock is deliberately absent from the subject list.
    """

    text = "Current stock still needs confirmation."

    assert commit_to_what_you_deferred(text, language="en") == text


def test_a_reply_that_defers_nothing_is_untouched() -> None:
    text = "The XTEN-S workstation is AED 566.87 and 12 units are in stock."

    assert commit_to_what_you_deferred(text, language="en") == text


@pytest.mark.parametrize(
    ("deferral", "expected"),
    [
        ("Whether installation is included is not yet confirmed.", "assembly"),
        ("The delivery timeline remains unconfirmed.", "the delivery timing"),
        ("Warranty cover needs to be confirmed.", "the warranty terms"),
        ("Payment terms are still unconfirmed.", "the payment terms"),
    ],
)
def test_the_commitment_names_the_thing_that_was_deferred(
    deferral: str, expected: str
) -> None:
    result = commit_to_what_you_deferred(deferral, language="en")

    assert f"I'll confirm {expected} with our team" in result


def test_arabic_gets_the_commitment_in_arabic() -> None:
    result = commit_to_what_you_deferred("التركيب غير مؤكد حتى الآن.", language="ar")

    assert "سأؤكد التركيب مع فريقنا وأعود إليك." in result


def test_the_commitment_survives_the_grounding_policy() -> None:
    """The two guards run back to back, and grounding has the last word.

    `FUTURE_STOCK_CHECK` exists to delete "I'll check and get back to you"
    where the object is stock. This asserts the subjects chosen here are not
    that, so the sentence added is one the customer actually receives.
    """

    committed = commit_to_what_you_deferred(DEFERRED_ASSEMBLY, language="en")
    enforced = enforce_grounding_output(committed, language="en")

    assert enforced.action is GroundingOutputAction.UNCHANGED
    assert "come back to you" in enforced.text
