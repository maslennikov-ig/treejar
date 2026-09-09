from __future__ import annotations

import pytest

from src.core.config import settings
from src.llm.fact_extractor import (
    FAST_EXTRACTOR_INSTRUCTIONS,
    CustomerFactExtractionResult,
    ExtractedCustomerFact,
    FastCustomerFactExtractionOutput,
    FastCustomerFactExtractionRequest,
    extract_customer_facts,
    extract_delivery_address,
    is_customer_phone_detail,
    is_specific_delivery_address,
)
from src.llm.pii import PHONE_PATTERN


def _fact_by_key(
    result: CustomerFactExtractionResult,
    key: str,
) -> ExtractedCustomerFact:
    matches = [fact for fact in result.facts if fact.key == key]
    assert len(matches) == 1
    return matches[0]


def _facts_by_key(
    result: CustomerFactExtractionResult,
    key: str,
) -> list[ExtractedCustomerFact]:
    return [fact for fact in result.facts if fact.key == key]


@pytest.mark.asyncio
async def test_deterministic_extracts_compact_quote_details() -> None:
    result = await extract_customer_facts(
        "Lili, individual, 1 Dubai, lili@example.com, +971 55 123 4567",
        source_message_id="msg-compact",
        use_fast_model=False,
    )

    name = _fact_by_key(result, "customer.name")
    assert name.value == "Lili"
    assert name.scope == "persistent_profile"
    assert name.confidence == "medium"
    assert name.source == "deterministic"
    assert name.source_message_id == "msg-compact"

    customer_type = _fact_by_key(result, "customer.type")
    assert customer_type.value == "individual"
    assert customer_type.scope == "current_order"
    assert customer_type.confidence == "high"

    address = _fact_by_key(result, "delivery.address")
    assert address.value == "1 Dubai"
    assert address.scope == "current_order"
    assert address.confidence == "medium"

    email = _fact_by_key(result, "customer.email")
    assert email.value == "lili@example.com"
    assert email.scope == "persistent_profile"
    assert email.confidence == "high"

    phone = _fact_by_key(result, "customer.phone")
    assert phone.value == "+971551234567"
    assert phone.scope == "persistent_profile"
    assert phone.confidence == "high"

    assert result.trace.fast_model_called is False
    assert result.trace.deterministic_fact_count == len(result.facts)


@pytest.mark.asyncio
async def test_deterministic_compact_name_uses_last_sentence_fragment() -> None:
    result = await extract_customer_facts(
        "Please recommend ergonomic chairs. Lili, individual, 1 Dubai, lili@example.com",
        use_fast_model=False,
    )

    name = _fact_by_key(result, "customer.name")
    assert name.value == "Lili"


@pytest.mark.asyncio
async def test_deterministic_extracts_labeled_company_and_delivery_address() -> None:
    result = await extract_customer_facts(
        "company is LLD, delivery address 2 Business Bay",
        use_fast_model=False,
    )

    company = _fact_by_key(result, "customer.company")
    assert company.value == "LLD"
    assert company.scope == "persistent_profile"
    assert company.confidence == "high"

    address = _fact_by_key(result, "delivery.address")
    assert address.value == "2 Business Bay"
    assert address.scope == "current_order"
    assert address.confidence == "high"


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
    "text, expected",
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
    ],
)
def test_extract_delivery_address_stops_before_followup_instruction(
    text: str,
    expected: str,
) -> None:
    assert extract_delivery_address(text) == expected


@pytest.mark.asyncio
async def test_deterministic_extracts_multiline_customer_details_and_full_address() -> (
    None
):
    address = "8, Street 42B, Sample District, Example City, Emirate of Dubai"
    result = await extract_customer_facts(
        f"Individual\n{address}\nEmail: lili@example.com",
        use_fast_model=False,
    )

    assert _fact_by_key(result, "customer.type").value == "individual"
    assert _fact_by_key(result, "delivery.address").value == address
    assert _fact_by_key(result, "customer.email").value == "lili@example.com"


@pytest.mark.asyncio
async def test_labeled_address_keeps_commas_and_stops_before_other_details() -> None:
    result = await extract_customer_facts(
        "Victor, individual, delivery address Office 1905, JLT Dubai, "
        "email victor@example.com, phone +971501112233",
        use_fast_model=False,
    )

    assert _fact_by_key(result, "delivery.address").value == "Office 1905, JLT Dubai"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "What cities do you deliver to?",
        "What is your delivery address?",
        "Do you deliver to all emirates?",
    ],
)
async def test_deterministic_rejects_address_questions(text: str) -> None:
    result = await extract_customer_facts(text, use_fast_model=False)

    assert extract_delivery_address(text) is None
    assert _facts_by_key(result, "delivery.address") == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "What is your company name?",
        "Do you offer company discounts?",
    ],
)
async def test_deterministic_rejects_company_questions(text: str) -> None:
    result = await extract_customer_facts(text, use_fast_model=False)

    assert _facts_by_key(result, "customer.company") == []


@pytest.mark.asyncio
async def test_deterministic_rejects_punctuation_only_company() -> None:
    result = await extract_customer_facts("Company: ?", use_fast_model=False)

    assert _facts_by_key(result, "customer.company") == []


@pytest.mark.asyncio
async def test_company_name_label_is_not_also_a_customer_name() -> None:
    result = await extract_customer_facts(
        "Company name: Acme LLC",
        use_fast_model=False,
    )

    assert _fact_by_key(result, "customer.company").value == "Acme LLC"
    assert _facts_by_key(result, "customer.name") == []


@pytest.mark.asyncio
async def test_spaced_company_name_label_is_not_also_a_customer_name() -> None:
    result = await extract_customer_facts(
        "Company  name: Acme LLC",
        use_fast_model=False,
    )

    assert _fact_by_key(result, "customer.company").value == "Acme LLC"
    assert _facts_by_key(result, "customer.name") == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Office 5, Dubai, name: Arina",
        "Address: Office 5, Dubai, name: Arina",
    ],
)
async def test_address_stops_before_standalone_name_label(text: str) -> None:
    result = await extract_customer_facts(text, use_fast_model=False)

    assert _fact_by_key(result, "delivery.address").value == "Office 5, Dubai"
    assert _fact_by_key(result, "customer.name").value == "Arina"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text, contact_key",
    [
        (
            "Can you deliver to Business Bay, email arina@example.com?",
            "customer.email",
        ),
        (
            "Do you deliver to Business Bay, phone +971501234567?",
            "customer.phone",
        ),
    ],
)
async def test_delivery_question_with_contact_does_not_create_address_or_name(
    text: str,
    contact_key: str,
) -> None:
    result = await extract_customer_facts(text, use_fast_model=False)

    assert _facts_by_key(result, "delivery.address") == []
    assert _facts_by_key(result, "customer.name") == []
    assert _facts_by_key(result, contact_key)


def test_address_assertion_survives_separate_followup_question() -> None:
    text = "My address is Office 5. Can you deliver tomorrow?"

    assert extract_delivery_address(text) == "Office 5"


@pytest.mark.parametrize(
    "value, expected",
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


@pytest.mark.asyncio
async def test_invoice_number_is_not_a_customer_phone() -> None:
    text = "The invoice number is 1234567890"
    match = next(iter(PHONE_PATTERN.finditer(text)))

    assert is_customer_phone_detail(text, match) is False
    result = await extract_customer_facts(text, use_fast_model=False)
    assert _facts_by_key(result, "customer.phone") == []


@pytest.mark.asyncio
async def test_deterministic_does_not_treat_plain_city_as_specific_address() -> None:
    result = await extract_customer_facts("Lili, Dubai", use_fast_model=False)

    assert _facts_by_key(result, "delivery.address") == []


@pytest.mark.asyncio
async def test_deterministic_does_not_treat_product_delivery_need_as_address() -> None:
    result = await extract_customer_facts(
        "Hi Noor, I need 2 CH 616 chairs with delivery and assembly.",
        use_fast_model=False,
    )

    assert _facts_by_key(result, "delivery.address") == []
    order_items = _fact_by_key(result, "order.items")
    assert order_items.value == [
        {
            "catalog_ref": "CH-616",
            "quantity": 2,
            "source_text": "CH 616 chairs",
        }
    ]
    assert _facts_by_key(result, "order.item") == []
    assert _fact_by_key(result, "order.delivery_required").value is True
    assert _fact_by_key(result, "order.assembly_required").value is True


@pytest.mark.asyncio
async def test_deterministic_ignores_synthetic_markers_for_profile_facts() -> None:
    result = await extract_customer_facts(
        "Hi, I need a quotation: 5 x CH 620\n[e2emarker20260616103817sales_order1]",
        use_fast_model=False,
    )

    assert _facts_by_key(result, "customer.name") == []
    assert _facts_by_key(result, "customer.phone") == []
    order_items = _fact_by_key(result, "order.items")
    assert order_items.value == [
        {
            "catalog_ref": "CH-620",
            "quantity": 5,
            "source_text": "CH 620",
        }
    ]


@pytest.mark.asyncio
async def test_deterministic_does_not_use_greeting_as_compact_name_with_phone() -> None:
    result = await extract_customer_facts(
        "Hi, I need a quotation for 5 x CH 620. Phone +971501234567",
        use_fast_model=False,
    )

    assert _facts_by_key(result, "customer.name") == []
    phone = _fact_by_key(result, "customer.phone")
    assert phone.value == "+971501234567"
    order_items = _fact_by_key(result, "order.items")
    assert order_items.value == [
        {
            "catalog_ref": "CH-620",
            "quantity": 5,
            "source_text": "CH 620",
        }
    ]


@pytest.mark.asyncio
async def test_deterministic_extracts_customer_label_as_name() -> None:
    result = await extract_customer_facts(
        "Quotation for 1 x CH 620 grey. Customer: Amina Complete. Individual. "
        "Delivery: Business Bay Dubai. Email: amina.complete@example.com. "
        "Phone: +971501112255.",
        use_fast_model=False,
    )

    name = _fact_by_key(result, "customer.name")
    assert name.value == "Amina Complete"
    assert name.confidence == "high"


@pytest.mark.asyncio
async def test_deterministic_extracts_repeatable_order_items_snapshot() -> None:
    result = await extract_customer_facts(
        "I need 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs",
        use_fast_model=False,
    )

    order_items = _fact_by_key(result, "order.items")

    assert order_items.scope == "current_order"
    assert order_items.value == [
        {
            "catalog_ref": "SKYLAND NOVO 2400",
            "quantity": 2,
            "source_text": "SKYLAND NOVO 2400 Meeting Table",
        },
        {
            "catalog_ref": "CH-616",
            "quantity": 4,
            "source_text": "CH 616 chairs",
        },
    ]
    assert _facts_by_key(result, "order.item") == []


@pytest.mark.asyncio
async def test_deterministic_extracts_single_runtime_order_item_snapshot() -> None:
    result = await extract_customer_facts(
        "I need 2 SKYLAND NOVO 2400",
        use_fast_model=False,
    )

    order_items = _fact_by_key(result, "order.items")

    assert order_items.value == [
        {
            "catalog_ref": "SKYLAND NOVO 2400",
            "quantity": 2,
            "source_text": "SKYLAND NOVO 2400",
        }
    ]
    assert _facts_by_key(result, "order.item") == []


@pytest.mark.asyncio
async def test_deterministic_order_items_evidence_is_item_only() -> None:
    result = await extract_customer_facts(
        "Victor, email victor@example.com, delivery address 2 street. "
        "I need 2 SKYLAND NOVO 2400 and 4 CH 616",
        use_fast_model=False,
    )

    order_items = _fact_by_key(result, "order.items")

    assert order_items.evidence == "2 x SKYLAND NOVO 2400; 4 x CH-616"
    assert "victor@example.com" not in order_items.evidence
    assert "2 street" not in order_items.evidence


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "How much is 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs?",
        "Do you have availability for 2 SKYLAND NOVO 2400 and 4 CH 616?",
        "What is the stock for 2 SKYLAND NOVO 2400 and 4 CH 616?",
        "Please check price for 2 CH 616 chairs",
    ],
)
async def test_deterministic_does_not_store_order_items_for_stock_price_inquiries(
    text: str,
) -> None:
    result = await extract_customer_facts(text, use_fast_model=False)

    assert _facts_by_key(result, "order.items") == []
    assert _facts_by_key(result, "order.item") == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "Can you compare 2 CH 616 and 4 CH 620?",
        "ما هو سعر 2 CH 616؟",
        "هل يتوفر 2 CH 616 في المخزون؟",
    ],
)
async def test_deterministic_does_not_store_order_items_for_comparison_or_arabic_inquiries(
    text: str,
) -> None:
    result = await extract_customer_facts(text, use_fast_model=False)

    assert _facts_by_key(result, "order.items") == []
    assert _facts_by_key(result, "order.item") == []


@pytest.mark.asyncio
async def test_deterministic_extracts_runtime_sku_and_skips_ambiguous_plain_quantity() -> (
    None
):
    result = await extract_customer_facts(
        "same as last time but 8 chairs. Also I need 6 CH 616",
        use_fast_model=False,
    )

    past_order = _fact_by_key(result, "past_order.reuse_request")
    assert past_order.scope == "past_order_reference"
    assert past_order.value == {"reference": "last_order"}
    assert past_order.needs_confirmation is True

    order_items = _fact_by_key(result, "order.items")
    assert order_items.value == [
        {
            "catalog_ref": "CH-616",
            "quantity": 6,
            "source_text": "CH 616",
        }
    ]
    assert _facts_by_key(result, "order.item") == []


@pytest.mark.asyncio
async def test_deterministic_does_not_treat_spaced_sku_number_as_plain_quantity() -> (
    None
):
    result = await extract_customer_facts(
        "Hi Noor, I need 2 CH 616 chairs with delivery and assembly. "
        "My name is Victor, individual, delivery address Office 1905, JLT Dubai, "
        "email victor.memory.e2e@example.com.",
        use_fast_model=False,
    )

    order_items = _fact_by_key(result, "order.items")
    assert order_items.value == [
        {
            "catalog_ref": "CH-616",
            "quantity": 2,
            "source_text": "CH 616 chairs",
        }
    ]
    assert _facts_by_key(result, "order.item") == []
    names = _facts_by_key(result, "customer.name")
    assert [name.value for name in names] == ["Victor"]


@pytest.mark.asyncio
async def test_deterministic_labeled_name_with_details_has_no_name_conflict() -> None:
    result = await extract_customer_facts(
        "I need 2 CH 616 black chairs. My name is Victor Memory Final, "
        "individual, delivery address Office 1204, One Business Bay, Dubai, "
        "email victor.memory.final@example.com, phone +971501112233",
        use_fast_model=False,
    )

    names = _facts_by_key(result, "customer.name")
    assert [name.value for name in names] == ["Victor Memory Final"]
    assert all(name.confidence == "high" for name in names)


@pytest.mark.asyncio
async def test_deterministic_extracts_past_order_query() -> None:
    result = await extract_customer_facts(
        "What did I order last time?",
        use_fast_model=False,
    )

    query = _fact_by_key(result, "past_order.query")
    assert query.scope == "past_order_reference"
    assert query.value == {"reference": "last_order"}
    assert query.needs_confirmation is False


@pytest.mark.asyncio
async def test_deterministic_extracts_preferences_and_quote_status() -> None:
    result = await extract_customer_facts(
        "Need delivery and assembly, black color, budget under 3,000 AED. I agree.",
        use_fast_model=False,
    )

    assert _fact_by_key(result, "order.delivery_required").value is True
    assert _fact_by_key(result, "order.assembly_required").value is True
    assert _fact_by_key(result, "order.color_preference").value == "black"
    assert _fact_by_key(result, "order.budget").value == {
        "amount": 3000,
        "currency": "AED",
        "qualifier": "under",
    }

    status = _fact_by_key(result, "quote.status")
    assert status.value == "accepted"
    assert status.confidence == "high"


@pytest.mark.asyncio
async def test_deterministic_extracts_arabic_agreement_and_refusal() -> None:
    accepted = await extract_customer_facts("موافق على العرض", use_fast_model=False)
    refused = await extract_customer_facts("لا شكرا السعر غالي", use_fast_model=False)

    assert _fact_by_key(accepted, "quote.status").value == "accepted"
    assert _fact_by_key(refused, "quote.status").value == "refused"


@pytest.mark.asyncio
async def test_price_objection_is_not_terminal_quote_refusal() -> None:
    result = await extract_customer_facts(
        "The chairs feel too expensive. Can you adjust the price?",
        use_fast_model=False,
    )

    assert all(fact.key != "quote.status" for fact in result.facts)
    objection = _fact_by_key(result, "quote.objection")
    assert objection.value == "price"
    assert objection.scope == "current_order"


@pytest.mark.asyncio
async def test_explicit_no_thanks_with_price_objection_is_quote_refusal() -> None:
    result = await extract_customer_facts(
        "No thanks, too expensive.",
        use_fast_model=False,
    )

    assert _fact_by_key(result, "quote.status").value == "refused"


@pytest.mark.asyncio
async def test_fast_extractor_boundary_uses_fast_model_and_merges_structured_facts() -> (
    None
):
    seen_requests: list[FastCustomerFactExtractionRequest] = []

    async def fake_fast_extractor(
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        seen_requests.append(request)
        return FastCustomerFactExtractionOutput(
            facts=[
                ExtractedCustomerFact(
                    scope="persistent_profile",
                    key="customer.company",
                    value="LLD",
                    confidence="medium",
                    source="fast_model",
                    evidence="LLD",
                )
            ],
            trace_note="parsed compact unlabeled company",
        )

    result = await extract_customer_facts(
        "Lili from LLD",
        fast_extractor=fake_fast_extractor,
    )

    assert len(seen_requests) == 1
    assert seen_requests[0].model == settings.openrouter_model_fast
    assert seen_requests[0].message_text == "Lili from LLD"
    assert seen_requests[0].deterministic_facts
    assert settings.openrouter_model_main not in seen_requests[0].model
    assert _fact_by_key(result, "customer.company").source == "fast_model"
    assert result.trace.fast_model_called is True
    assert result.trace.fast_model_model == settings.openrouter_model_fast
    assert result.trace.fast_model_failed is False
    assert result.trace.fast_model_note == "parsed compact unlabeled company"


@pytest.mark.asyncio
async def test_fast_extractor_prompt_redacts_contact_pii() -> None:
    seen_requests: list[FastCustomerFactExtractionRequest] = []

    async def fake_fast_extractor(
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        seen_requests.append(request)
        return FastCustomerFactExtractionOutput(facts=[])

    await extract_customer_facts(
        "Lili from LLD, email lili@example.com, phone +971 55 123 4567",
        fast_extractor=fake_fast_extractor,
    )

    assert len(seen_requests) == 1
    request = seen_requests[0]
    request_dump = request.model_dump_json()
    assert "lili@example.com" not in request.message_text
    assert "+971 55 123 4567" not in request.message_text
    assert "lili@example.com" not in request_dump
    assert "+971551234567" not in request_dump


@pytest.mark.asyncio
async def test_fast_extractor_drops_authoritative_order_items() -> None:
    async def fake_fast_extractor(
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        return FastCustomerFactExtractionOutput(
            facts=[
                ExtractedCustomerFact(
                    scope="current_order",
                    key="order.items",
                    value=[{"catalog_ref": "BAD-SKU", "quantity": 99}],
                    confidence="high",
                    source="fast_model",
                    evidence="hallucinated order",
                ),
                ExtractedCustomerFact(
                    scope="current_order",
                    key="order.item",
                    value={"sku": "BAD-SKU", "quantity": 1},
                    confidence="high",
                    source="fast_model",
                    evidence="legacy singular order item",
                ),
                ExtractedCustomerFact(
                    scope="persistent_profile",
                    key="customer.company",
                    value="LLD",
                    confidence="medium",
                    source="fast_model",
                    evidence="LLD",
                ),
            ]
        )

    result = await extract_customer_facts(
        "Lili from LLD",
        fast_extractor=fake_fast_extractor,
    )

    assert _facts_by_key(result, "order.items") == []
    assert _facts_by_key(result, "order.item") == []
    assert _fact_by_key(result, "customer.company").value == "LLD"


@pytest.mark.asyncio
async def test_fast_extractor_normalizes_explicit_profile_and_address_aliases() -> None:
    address = "8, Street 42B, Sample District, Example City, Emirate of Dubai"

    async def fake_fast_extractor(
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        return FastCustomerFactExtractionOutput(
            facts=[
                ExtractedCustomerFact(
                    scope="persistent_profile",
                    key="delivery_address",
                    value=f"{address}; confidence=high",
                    confidence="high",
                    source="fast_model",
                    evidence="parsed delivery_address",
                ),
                ExtractedCustomerFact(
                    scope="current_order",
                    key="customer.display_name",
                    value="Lili",
                    confidence="high",
                    source="fast_model",
                    evidence="Lili",
                ),
                ExtractedCustomerFact(
                    scope="current_order",
                    key="customer.primary_email",
                    value="lili@example.com",
                    confidence="high",
                    source="fast_model",
                    evidence="lili@example.com",
                ),
                ExtractedCustomerFact(
                    scope="current_order",
                    key="order.delivery_window",
                    value="morning",
                    confidence="medium",
                    source="fast_model",
                    evidence="morning delivery",
                ),
            ]
        )

    result = await extract_customer_facts(
        f"Lili, individual, {address}, lili@example.com, morning delivery",
        fast_extractor=fake_fast_extractor,
    )

    assert _fact_by_key(result, "delivery.address").value == address
    name = _fact_by_key(result, "customer.name")
    assert name.scope == "persistent_profile"
    assert name.value == "Lili"
    email = _fact_by_key(result, "customer.email")
    assert email.scope == "persistent_profile"
    assert email.value == "lili@example.com"
    dynamic = _fact_by_key(result, "order.delivery_window")
    assert dynamic.scope == "current_order"
    assert dynamic.value == "morning"


def test_fast_extractor_instructions_name_canonical_keys() -> None:
    assert "delivery.address" in FAST_EXTRACTOR_INSTRUCTIONS
    assert "customer.name" in FAST_EXTRACTOR_INSTRUCTIONS
    assert "customer.email" in FAST_EXTRACTOR_INSTRUCTIONS


@pytest.mark.asyncio
async def test_fast_extractor_failure_returns_deterministic_facts_and_bounded_trace() -> (
    None
):
    async def failing_fast_extractor(
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        raise RuntimeError("x" * 500)

    result = await extract_customer_facts(
        "lili@example.com",
        fast_extractor=failing_fast_extractor,
    )

    assert _fact_by_key(result, "customer.email").value == "lili@example.com"
    assert result.trace.fast_model_called is True
    assert result.trace.fast_model_failed is True
    assert result.trace.fast_model_failure is not None
    assert len(result.trace.fast_model_failure) <= 160


def test_pydantic_fact_contract_defaults_and_validation() -> None:
    fact = ExtractedCustomerFact(
        scope="current_order",
        key="delivery.address",
        value={"line": "1 Dubai"},
        confidence="high",
        source="deterministic",
        evidence="delivery address 1 Dubai",
    )

    assert fact.needs_confirmation is False
    assert fact.conflicts_with is None
    assert fact.source_message_id is None


@pytest.mark.asyncio
async def test_no_fast_model_call_when_disabled() -> None:
    async def unexpected_fast_extractor(
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        raise AssertionError("fast extractor should not be called")

    result = await extract_customer_facts(
        "lili@example.com",
        fast_extractor=unexpected_fast_extractor,
        use_fast_model=False,
    )

    assert _fact_by_key(result, "customer.email").value == "lili@example.com"
    assert result.trace.fast_model_called is False


@pytest.mark.asyncio
async def test_bare_delivery_coverage_question_is_not_name_or_address() -> None:
    result = await extract_customer_facts(
        "Is Business Bay covered, email arina@example.com?", use_fast_model=False
    )
    assert not _facts_by_key(result, "delivery.address")
    assert not _facts_by_key(result, "customer.name")


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["Will Smith", "May West"])
async def test_compact_customer_names_are_not_question_auxiliaries(name: str) -> None:
    result = await extract_customer_facts(
        f"{name}, individual, 1 Dubai", use_fast_model=False
    )
    assert _fact_by_key(result, "customer.name").value == name
