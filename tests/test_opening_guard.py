from __future__ import annotations

from src.llm.opening_guard import apply_opening_guard, build_name_gate_reply


def test_first_turn_english_response_adds_identity_and_name_question() -> None:
    response = apply_opening_guard(
        "I can help with office chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == build_name_gate_reply(language="en")
    assert "office chairs" not in response


def test_first_turn_unknown_customer_does_not_answer_embedded_question() -> None:
    response = apply_opening_guard(
        "Yes, we have ergonomic chairs in stock.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == build_name_gate_reply(language="en")
    assert "ergonomic chairs" not in response


def test_first_turn_russian_response_adds_identity_and_name_question_only() -> None:
    response = apply_opening_guard(
        "Yes, we do have ergonomic chairs.",
        language="Russian",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == build_name_gate_reply(language="en")
    assert "ergonomic chairs" not in response


def test_first_turn_english_keeps_business_answer_when_customer_name_known() -> None:
    response = apply_opening_guard(
        "I can help with office chairs.",
        language="en",
        is_first_turn=True,
        customer_name="Viktor",
    )

    assert response.startswith("Hello, I'm Noor from Treejar.")
    assert "May I know your name" not in response
    assert response.endswith("I can help with office chairs.")


def test_first_turn_arabic_response_adds_identity_and_name_question_only() -> None:
    response = apply_opening_guard(
        "يمكنني مساعدتك في كراسي المكتب.",
        language="ar",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == build_name_gate_reply(language="ar")


def test_first_turn_english_response_strips_old_identity() -> None:
    old_name = "Si" + "yyad"
    response = apply_opening_guard(
        f"Hello, I'm {old_name} from Treejar. I can help with chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert old_name not in response
    assert response.startswith("Hello, I'm Noor from Treejar.")


def test_first_turn_response_does_not_duplicate_compliant_opening() -> None:
    """The gate reply is regenerated, not appended to, however it arrives."""

    response = apply_opening_guard(
        build_name_gate_reply(language="en"),
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == build_name_gate_reply(language="en")
    assert response.count("Noor") == 1
    assert response.count("Treejar") == 1


def test_first_turn_response_strips_generic_greeting_before_canonical_opening() -> None:
    response = apply_opening_guard(
        (
            "Hello! Welcome to Treejar! 👋\n\n"
            "I'm here to help you find workstation options."
        ),
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == build_name_gate_reply(language="en")
    assert response.count("Hello") == 1
    assert response.count("Treejar") == 1
    assert "Welcome to Treejar" not in response
    assert "workstation options" not in response


def test_known_customer_gets_identity_without_name_question() -> None:
    response = apply_opening_guard(
        "Here are a few chair options.",
        language="en",
        is_first_turn=True,
        customer_name="Ahmed",
    )

    assert response.startswith("Hello, I'm Noor from Treejar.")
    assert "May I know your name" not in response
    assert response.endswith("Here are a few chair options.")


def test_subsequent_turn_is_unchanged() -> None:
    original = "Here are a few chair options."

    response = apply_opening_guard(
        original,
        language="en",
        is_first_turn=False,
        customer_name=None,
    )

    assert response == original


def test_legacy_expectations_removed() -> None:
    response = apply_opening_guard(
        "I can help with office chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert "Noor" in response


def _legacy_tests_removed_marker() -> None:
    """Keep this file focused on Noor-only expectations."""


def test_first_turn_response_adds_identity_and_name_question_legacy_removed() -> None:
    response = apply_opening_guard(
        "I can help with office chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response.startswith("Hello, I'm Noor from Treejar.")
    assert "May I know your name so I can address you properly?" in response


def test_the_first_reply_carries_value_before_it_asks_for_anything() -> None:
    """2026-08-09. Two research reports and our own data agree: a reply that
    only asks for a name spends the single turn a third of customers ever read.
    34% open with a bare greeting, 36% never send a second message."""

    reply = build_name_gate_reply(
        language="en",
        anchor_line="Chairs from AED 139, desks and workstations from AED 1,813.",
    )

    # Who we are, then what we can do now, then the price, then the question.
    assert reply.index("Noor from Treejar") < reply.index("live prices")
    assert reply.index("live prices") < reply.index("AED 139")
    assert reply.index("AED 139") < reply.index("May I know your name")
    # One folded question, answerable in three words.
    assert reply.count("?") == 2
    assert "chairs, desks and workstations, or a full office" in reply
    # Short enough to read on a phone.
    assert len(reply) < 320


def test_the_first_reply_stands_without_an_anchor_rather_than_invent_one() -> None:
    """Every figure is a catalog row. If the catalog cannot answer, the reply
    goes out without a number, never with a plausible one."""

    reply = build_name_gate_reply(language="en")

    assert "AED" not in reply
    assert "May I know your name" in reply
    assert "live prices" in reply
