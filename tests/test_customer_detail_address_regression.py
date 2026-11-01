"""Customer messages must survive extraction and quotation state unchanged."""

import pytest

from src.llm import engine

ADDRESS = "8, Street 42B, Sample District, Example City, Emirate of Dubai"


@pytest.mark.parametrize(
    "message", [ADDRESS, f"I’m an individual\n{ADDRESS}\ntester@example.com"]
)
def test_address_district_never_becomes_customer_name(message: str) -> None:
    details = engine._extract_quote_customer_details(message)
    assert details["address"] == ADDRESS
    assert "name" not in details


@pytest.mark.parametrize("invalid", ["?", "5", "What cities do you deliver to?"])
def test_invalid_address_is_not_specific_delivery_address(
    invalid: str,
) -> None:
    assert not engine._is_specific_delivery_address(invalid)


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
    details = engine._extract_quote_customer_details(question)
    assert "address" not in details
    assert "name" not in details


def test_question_mark_is_not_a_company_in_quote_details() -> None:
    assert "company" not in engine._extract_quote_customer_details("Company: ?")
