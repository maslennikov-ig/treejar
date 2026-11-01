"""Customer messages must survive extraction and quotation state unchanged."""

import pytest

from src.llm import engine

ADDRESS = "8, Street 42B, Sample District, Example City, Emirate of Dubai"


@pytest.mark.parametrize(
    "message", [ADDRESS, f"I’m an individual\n{ADDRESS}\ntester@example.com"]
)
def test_address_district_never_becomes_customer_name(message: str) -> None:
    details = engine._extract_quote_customer_details(message)
    terse = engine._extract_terse_quote_customer_details(message)
    assert details["address"] == ADDRESS
    assert terse["address"] == ADDRESS
    assert "name" not in details
    assert "name" not in terse
    assert "company" not in terse
    if "individual" in message:
        assert terse["customer_type"] == "individual"
        assert terse["email"] == "tester@example.com"


@pytest.mark.parametrize("invalid", ["?", "5", "What cities do you deliver to?"])
def test_invalid_address_is_not_specific_delivery_address(
    invalid: str,
) -> None:
    assert not engine._is_specific_delivery_address(invalid)


@pytest.mark.parametrize("message", ["Lil, 1 dubay", "Lil, 1 dubay, lil@example.com"])
def test_terse_address_capture_preserves_separate_name(message: str) -> None:
    details = engine._extract_terse_quote_customer_details(message)
    assert details["name"] == "Lil"
    assert details["address"] == "1 dubay"


@pytest.mark.parametrize(
    "question",
    [
        "Can you deliver to Business Bay, email arina@example.com?",
        "Is Business Bay covered, email arina@example.com?",
        "Do you deliver to Business Bay, phone +971501234567?",
    ],
)
def test_quote_extractors_do_not_turn_delivery_question_into_address(
    question: str,
) -> None:
    for details in (
        engine._extract_quote_customer_details(question),
        engine._extract_terse_quote_customer_details(question),
    ):
        assert "address" not in details
        assert "name" not in details


def test_question_mark_is_not_a_company_in_quote_details() -> None:
    assert "company" not in engine._extract_quote_customer_details("Company: ?")


def test_individual_status_is_not_a_name_after_address_removal() -> None:
    details = engine._extract_terse_quote_customer_details(
        "individual\ndubay 2 street 7"
    )
    assert details["address"] == "dubay 2 street 7"
    assert details["customer_type"] == "individual"
    assert "name" not in details
