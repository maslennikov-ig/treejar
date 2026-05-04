from __future__ import annotations

from src.llm.opening_guard import apply_opening_guard


def test_first_turn_english_response_adds_identity_and_name_question() -> None:
    response = apply_opening_guard(
        "I can help with office chairs.",
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response.startswith("Hello, I'm Siyyad from Treejar.")
    assert "May I know your name so I can address you properly?" in response
    assert response.endswith("I can help with office chairs.")


def test_first_turn_arabic_response_adds_identity_and_name_question() -> None:
    response = apply_opening_guard(
        "يمكنني مساعدتك في كراسي المكتب.",
        language="ar",
        is_first_turn=True,
        customer_name=None,
    )

    assert response.startswith("مرحبًا، أنا Siyyad من Treejar.")
    assert "هل يمكنني معرفة اسمك لأخاطبك بشكل مناسب؟" in response
    assert response.endswith("يمكنني مساعدتك في كراسي المكتب.")


def test_first_turn_response_does_not_duplicate_compliant_opening() -> None:
    original = (
        "Hello, I'm Siyyad from Treejar. "
        "May I know your name so I can address you properly?"
    )

    response = apply_opening_guard(
        original,
        language="en",
        is_first_turn=True,
        customer_name=None,
    )

    assert response == original
    assert response.count("Siyyad") == 1
    assert response.count("Treejar") == 1


def test_known_customer_gets_identity_without_name_question() -> None:
    response = apply_opening_guard(
        "Here are a few chair options.",
        language="en",
        is_first_turn=True,
        customer_name="Ahmed",
    )

    assert response.startswith("Hello, I'm Siyyad from Treejar.")
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
