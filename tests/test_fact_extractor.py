from __future__ import annotations

import pytest

from src.core.config import settings
from src.llm.fact_extractor import (
    CustomerFactExtractionResult,
    ExtractedCustomerFact,
    FastCustomerFactExtractionOutput,
    FastCustomerFactExtractionRequest,
    extract_customer_facts,
)


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


@pytest.mark.asyncio
async def test_deterministic_does_not_treat_plain_city_as_specific_address() -> None:
    result = await extract_customer_facts("Lili, Dubai", use_fast_model=False)

    assert _facts_by_key(result, "delivery.address") == []


@pytest.mark.asyncio
async def test_deterministic_extracts_sku_quantity_and_plain_quantity() -> None:
    result = await extract_customer_facts(
        "same as last time but 8 chairs. Also I need 6 CH 616",
        use_fast_model=False,
    )

    past_order = _fact_by_key(result, "past_order.reuse_request")
    assert past_order.scope == "past_order_reference"
    assert past_order.value == {"reference": "last_order"}
    assert past_order.needs_confirmation is True

    items = _facts_by_key(result, "order.item")
    assert {"description": "chairs", "quantity": 8} in [item.value for item in items]
    assert {"sku": "CH 616", "quantity": 6} in [item.value for item in items]
    assert all(item.scope == "current_order" for item in items)


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
