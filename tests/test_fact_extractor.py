from __future__ import annotations

import pytest

from src.llm.fact_extractor import (
    extract_delivery_address,
    is_customer_phone_detail,
    is_question_clause,
    is_specific_delivery_address,
)
from src.llm.pii import PHONE_PATTERN


@pytest.mark.parametrize(
    "address",
    [
        "8, Street 42B, Sample District, Example City, Emirate of Dubai",
        "12, Cedar Road, Al Nahda, Sharjah",
    ],
)
def test_extract_delivery_address_preserves_full_comma_address(address: str) -> None:
    assert extract_delivery_address(address) == address


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Delivery address: Office 1204, Test Tower, Business Bay, Dubai, UAE. "
            "Please quote exactly 4 x CH 616 NEW black.",
            "Office 1204, Test Tower, Business Bay, Dubai, UAE",
        ),
        (
            "Delivery address: Office 42, Test Tower, Dubai, UAE. "
            "Proceed with the requested order.",
            "Office 42, Test Tower, Dubai, UAE",
        ),
        (
            "Victor, individual, delivery address Office 1905, JLT Dubai, "
            "email victor@example.com, phone +971501112233",
            "Office 1905, JLT Dubai",
        ),
        ("Office 5, Dubai, name: Arina", "Office 5, Dubai"),
        ("Address: Office 5, Dubai, name: Arina", "Office 5, Dubai"),
    ],
)
def test_extract_delivery_address_stops_before_adjacent_details_or_instructions(
    text: str,
    expected: str,
) -> None:
    assert extract_delivery_address(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "What cities do you deliver to?",
        "What is your delivery address?",
        "Do you deliver to all emirates?",
        "Can you deliver to Business Bay, email arina@example.com?",
        "Do you deliver to Business Bay, phone +971501234567?",
        "Is Business Bay covered, email arina@example.com?",
        "Lili, Dubai",
        "Hi Noor, I need 2 CH 616 chairs with delivery and assembly.",
    ],
)
def test_extract_delivery_address_rejects_questions_and_non_addresses(
    text: str,
) -> None:
    assert extract_delivery_address(text) is None


def test_address_assertion_survives_separate_followup_question() -> None:
    text = "My address is Office 5. Can you deliver tomorrow?"

    assert extract_delivery_address(text) == "Office 5"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Office 5", True),
        ("Business Bay", True),
        ("Dubai", False),
        ("?", False),
        (None, False),
    ],
)
def test_specific_delivery_address_contract(
    value: str | None,
    expected: bool,
) -> None:
    assert is_specific_delivery_address(value) is expected


def test_invoice_number_is_not_a_customer_phone() -> None:
    text = "The invoice number is 1234567890"
    match = next(iter(PHONE_PATTERN.finditer(text)))

    assert is_customer_phone_detail(text, match) is False


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Can you deliver to Business Bay", True),
        ("Will Smith, individual, 1 Dubai", False),
        ("May West, individual, 1 Dubai", False),
    ],
)
def test_is_question_clause_distinguishes_questions_from_person_names(
    text: str,
    expected: bool,
) -> None:
    assert is_question_clause(text, len(text)) is expected
