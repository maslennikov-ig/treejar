from src.llm.closed_question_guard import (
    apply_closed_question_guard,
    response_asks_customer_name,
)


def test_response_asks_customer_name_detects_direct_name_questions() -> None:
    assert response_asks_customer_name(
        "May I know your name so I can address you properly?"
    )
    assert response_asks_customer_name("What is your name?")
    assert not response_asks_customer_name("I already have your name on the request.")


def test_closed_question_guard_repairs_known_customer_name_question() -> None:
    result = apply_closed_question_guard(
        "May I know your name so I can address you properly?",
        language="en",
        customer_name="Lili",
    )

    assert result.repaired is True
    assert result.reason == "answered_slots_already_known"
    assert result.text == (
        "Thank you, Lili. I already have your name, so I will continue "
        "with your request."
    )


def test_closed_question_guard_leaves_open_name_question_when_name_unknown() -> None:
    text = "May I know your name so I can address you properly?"

    result = apply_closed_question_guard(
        text,
        language="en",
        customer_name=None,
    )

    assert result.repaired is False
    assert result.text == text


def test_closed_question_guard_repairs_known_quote_detail_questions() -> None:
    result = apply_closed_question_guard(
        "Please share your company name and delivery address.",
        language="en",
        customer_name="Lili",
        company="LLD",
        delivery_address="1 dubay",
    )

    assert result.repaired is True
    assert result.text == (
        "Thank you, Lili. I already have your company or individual status and "
        "your delivery address, so I will continue with your request."
    )


def test_closed_question_guard_keeps_only_missing_quote_detail_question() -> None:
    result = apply_closed_question_guard(
        "Please share your name, company name, and delivery address.",
        language="en",
        customer_name="Lili",
        delivery_address="1 dubay",
    )

    assert result.repaired is True
    assert result.text == (
        "Thank you, Lili. I already have your name and your delivery address. "
        "Please share your company name or confirm you are buying as an individual."
    )


def test_closed_question_guard_does_not_replace_substantive_content() -> None:
    text = (
        "I found CH 140 for you.\n"
        "Quantity: 5\n"
        "Please share your company name and delivery address."
    )

    result = apply_closed_question_guard(
        text,
        language="en",
        customer_name="Lili",
        company="LLD",
        delivery_address="1 dubay",
    )

    assert result.repaired is False
    assert result.text == text
