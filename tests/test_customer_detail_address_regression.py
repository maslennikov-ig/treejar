"""Customer messages must survive extraction and quotation state unchanged."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.llm import engine
from src.llm.fact_extractor import extract_customer_facts

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


@pytest.mark.asyncio
async def test_delivery_question_then_address_can_finish_quote_details() -> None:
    conv = SimpleNamespace(
        customer_name="Arina",
        metadata_={
            "quote_customer_details": {
                "name": "Arina",
                "customer_type": "individual",
                "email": "tester@example.com",
            }
        },
    )
    db = SimpleNamespace(flush=AsyncMock())
    for message in ["What cities do you deliver to?", ADDRESS, ADDRESS]:
        facts = await extract_customer_facts(message, use_fast_model=False)
        details = engine._quote_details_from_customer_facts(facts.facts)
        details.update(engine._extract_quote_customer_details(message))
        details.update(engine._extract_terse_quote_customer_details(message))
        await engine._store_extracted_quote_customer_details(db, conv, details)
    captured = engine._quote_customer_details_from_metadata(conv)
    assert captured == {
        "name": "Arina",
        "customer_type": "individual",
        "email": "tester@example.com",
        "address": ADDRESS,
    }
    assert (
        engine._missing_quote_details_for_selection_confirmation(
            captured, customer_name=conv.customer_name
        )
        == []
    )


@pytest.mark.parametrize(
    ("key", "field", "value"),
    [
        ("customer.display_name", "name", "Arina"),
        ("customer.primary_email", "email", "tester@example.com"),
    ],
)
def test_previously_saved_profile_aliases_remain_readable(
    key: str, field: str, value: str
) -> None:
    assert engine._quote_details_from_customer_facts(
        [SimpleNamespace(scope="persistent_profile", key=key, value=value)]
    ) == {field: value}


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["?", "5", "What cities do you deliver to?"])
async def test_invalid_address_cannot_overwrite_known_quote_address(
    invalid: str,
) -> None:
    conv = SimpleNamespace(
        customer_name="Arina",
        metadata_={"quote_customer_details": {"name": "Arina", "address": ADDRESS}},
    )
    db = SimpleNamespace(flush=AsyncMock())
    assert not engine._is_specific_delivery_address(invalid)
    await engine._store_extracted_quote_customer_details(db, conv, {"address": invalid})
    assert engine._quote_customer_details_from_metadata(conv)["address"] == ADDRESS


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
