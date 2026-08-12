from __future__ import annotations

from src.llm.opening_guard import apply_opening_guard

_ANCHOR = "Chairs from AED 139, desks and workstations from AED 1,813."


def test_the_first_reply_answers_the_question_it_was_asked() -> None:
    """The defect this replaces, in one line.

    The first turn used to be a fixed request for a name and nothing else: the
    model never ran, and whatever the customer asked was stored for later. 36%
    of customers never send a later. Owner decision of 2026-08-10: answer
    first, ask the name in passing.
    """

    response = apply_opening_guard(
        "CH 616 NEW black: 295.00 AED each, 36 in stock now. How many do you need?",
        language="en",
        is_first_turn=True,
        customer_name=None,
        anchor_line=_ANCHOR,
    )

    assert "295.00 AED" in response
    assert "36 in stock now" in response
    assert "And how should I address you?" in response
    # The answer comes before the question about them.
    assert response.index("295.00 AED") < response.index("how should I address")


def test_the_first_reply_carries_value_before_it_asks_for_anything() -> None:
    """Who we are, what we can do now, the price, the answer, then the question.

    Rule 7, the value proposition, measured zero in 26 of 26 transcripts while
    it was left to a directive, so the capability clause is carried rather than
    requested.
    """

    response = apply_opening_guard(
        "Yes, we have ergonomic chairs in stock.",
        language="en",
        is_first_turn=True,
        customer_name=None,
        anchor_line=_ANCHOR,
    )

    assert response.index("Noor from Treejar") < response.index("supply office")
    assert response.index("supply office") < response.index("AED 139")
    assert response.index("AED 139") < response.index("ergonomic chairs")
    assert response.index("ergonomic chairs") < response.index("how should I address")


def test_a_generic_anchor_stands_down_where_the_reply_has_a_real_price() -> None:
    """A floor price beside a confirmed one is noise, and worse than noise: it
    invites the customer to compare our own two numbers."""

    response = apply_opening_guard(
        "CH 616 NEW black: 295.00 AED each, 36 in stock now.",
        language="en",
        is_first_turn=True,
        customer_name=None,
        anchor_line=_ANCHOR,
    )

    assert "AED 139" not in response
    assert "295.00 AED" in response


def test_the_reply_stands_without_an_anchor_rather_than_invent_one() -> None:
    """Every figure is a catalog row. If the catalog cannot answer, the reply
    goes out without a number, never with a plausible one."""

    response = apply_opening_guard(
        "How can I help with your office?",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "AED" not in response
    assert "quote from our own catalog" in response
    assert "how should I address" in response


def test_the_name_question_is_not_asked_twice_in_one_reply() -> None:
    response = apply_opening_guard(
        "We have several chairs in stock. May I know your name?",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "how should I address" not in response
    assert response.count("your name") == 1


def test_a_known_name_is_never_asked_for() -> None:
    response = apply_opening_guard(
        "Here are a few chair options.",
        language="en",
        is_first_turn=True,
        customer_name="Ahmed",
        anchor_line=_ANCHOR,
    )

    assert "how should I address" not in response
    assert response.endswith("Here are a few chair options.")


def test_the_identity_is_stated_once_however_the_reply_arrives() -> None:
    old_name = "Si" + "yyad"
    response = apply_opening_guard(
        f"Hello, I'm {old_name} from Treejar. I can help with chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert old_name not in response
    assert response.startswith("Hello, I'm Noor from Treejar.")
    assert response.count("Noor") == 1
    assert response.count("Treejar") == 1


def test_a_generic_greeting_is_replaced_rather_than_stacked() -> None:
    response = apply_opening_guard(
        "Hello! Welcome to Treejar! 👋\n\nI'm here to help you find workstations.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response.count("Hello") == 1
    assert "Welcome to Treejar" not in response
    assert "workstations" in response


def test_the_capability_clause_is_stated_once() -> None:
    """The model sometimes writes our own capability sentence back at us."""

    response = apply_opening_guard(
        "We supply office furniture across the UAE, and I quote from our "
        "own catalog with confirmed prices and stock. We stock ergonomic chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response.count("supply office furniture") == 1
    assert "ergonomic chairs" in response


def test_the_opening_survives_the_grounding_policy() -> None:
    """The clause this replaced did not, and only ever shipped because the old
    gate returned a static reply that skipped grounding entirely. A promise of
    "UAE delivery with installation" is a service commitment no tool confirmed.
    """

    from src.llm.grounding_output import enforce_grounding_output

    response = apply_opening_guard(
        "What are you furnishing?",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )
    grounded = enforce_grounding_output(
        response, language="en", inventory_confirmed=False
    ).text

    assert "supply office furniture" in grounded
    assert "how should I address you" in grounded


def test_arabic_keeps_the_same_shape() -> None:
    response = apply_opening_guard(
        "نعم، لدينا كراسي مريحة في المخزون.",
        language="ar",
        is_first_turn=True,
        customer_name=None,
    )

    assert response.startswith("مرحبًا، أنا Noor من Treejar.")
    assert "كراسي مريحة" in response
    assert "وكيف أخاطبك؟" in response


def test_a_later_turn_is_untouched() -> None:
    original = "Here are a few chair options."

    response = apply_opening_guard(
        original,
        language="en",
        is_first_turn=False,
        customer_name=None,
    )

    assert response == original


def test_an_empty_reply_is_left_alone() -> None:
    assert (
        apply_opening_guard(
            "   ",
            language="en",
            is_first_turn=True,
            customer_name=None,
        )
        == "   "
    )


# --- a curly apostrophe cost four customers their whole reply -------------
#
# Measured 2026-08-10 over 20 real customer openings. `_strip_legacy_identity`
# knew `I'm` and not `I’m`; the model writes the typographic one. Its own
# introduction therefore survived the strip, `_has_identity` saw "Noor" and
# "Treejar" still in the body, and the guard blanked the entire reply. Four of
# twenty customers -- 293, 421, 867, 1217, every one of them a bare greeting --
# received the identity line and nothing else. Bare greetings are 34% of real
# traffic, so this is the most common opening we have.

TYPOGRAPHIC_INTRO = (
    "Hi, I’m Noor from Treejar. We supply ergonomic chairs, desks, "
    "acoustic pods, and modular workstations for offices in Dubai.\n\n"
    "What are you furnishing—an existing office, or a new workspace?"
)


def test_a_typographic_apostrophe_does_not_cost_the_answer() -> None:
    guarded = apply_opening_guard(
        TYPOGRAPHIC_INTRO,
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "What are you furnishing" in guarded
    assert "ergonomic chairs, desks" in guarded


def test_the_duplicate_introduction_still_goes() -> None:
    """The intent was right; only the blast radius was wrong."""

    guarded = apply_opening_guard(
        TYPOGRAPHIC_INTRO,
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert guarded.count("Noor") == 1
    assert guarded.startswith("Hello, I'm Noor from Treejar.")


def test_only_the_introducing_sentence_is_dropped() -> None:
    """A mid-reply mention must not take the sentences around it.

    The old rule blanked the body the moment "Noor" and "Treejar" both appeared
    anywhere in it, which is how an answer, a price and a question could all
    disappear behind one redundant hello.
    """

    guarded = apply_opening_guard(
        "Thanks for asking. I am Noor from Treejar and happy to help. "
        "The CH 120 is AED 292. How many do you need?",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "AED 292" in guarded
    assert "How many do you need?" in guarded


def test_the_company_name_alone_owns_the_introduction_wherever_it_appears() -> None:
    """A company-only introduction must not be stacked under our own opening.

    This catches the D1 production break: changing `_has_identity` back to
    requiring the persona would leave the middle sentence in place and name
    Treejar twice.
    """

    guarded = apply_opening_guard(
        "Thanks for asking. Treejar supplies office desks. "
        "The CH 120 is AED 292. How many do you need?",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert guarded.count("Treejar") == 1
    assert "Thanks for asking." in guarded
    assert "The CH 120 is AED 292." in guarded
    assert "How many do you need?" in guarded


def test_the_company_name_inside_a_url_is_not_an_identity_sentence() -> None:
    text = (
        "Our showroom is in Dubai. Open the location: "
        "https://example.com/Treejar+Trading/location"
    )

    guarded = apply_opening_guard(
        text,
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "Our showroom is in Dubai." in guarded
    assert "https://example.com/Treejar+Trading/location" in guarded


def test_only_one_company_sentence_is_removed() -> None:
    """A repeated company name is not permission to delete two sentences."""

    guarded = apply_opening_guard(
        "This is the Treejar sales channel. "
        "Please apply through Treejar's official recruitment route. "
        "I wish you every success.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert guarded.count("Treejar") == 2
    assert "official recruitment route" in guarded
    assert "I wish you every success." in guarded


def test_a_company_only_reply_is_kept_instead_of_becoming_an_opening_stub() -> None:
    """If the one-sentence removal empties the answer, ship the model text."""

    original = "Treejar."

    guarded = apply_opening_guard(
        original,
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert guarded == original


def test_the_persona_alone_is_not_treated_as_a_company_introduction() -> None:
    guarded = apply_opening_guard(
        "Noor can help compare the chair options.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert guarded.count("Noor") == 2
    assert "compare the chair options" in guarded


def test_removing_a_sentence_keeps_the_paragraph_break() -> None:
    guarded = apply_opening_guard(
        "Good morning! I’m Noor from Treejar, a premium provider. "
        "We supply desks and chairs.\n\nWhat are you furnishing today?",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "We supply desks and chairs.\n\nWhat are you furnishing today?" in guarded


def test_the_customers_own_punctuation_survives() -> None:
    """The apostrophe is matched, not rewritten: the reply is the model's."""

    guarded = apply_opening_guard(
        "Thanks. I’m sorry, I can’t confirm that today.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "I’m sorry, I can’t confirm that today." in guarded
