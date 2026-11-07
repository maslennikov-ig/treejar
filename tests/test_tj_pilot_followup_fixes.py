"""Follow-up regression suite for 2026-11-05 live-pilot defects (tj-mi4g).

Covers the 4 defects discovered in the deep end-to-end review of pilot chats
*0068, *5868, and *2588:
1. *0068 (13:16 UTC) + active catalog audit: _product_model_reference and
   _referenced_product_media keep photos for products with leading dimension
   digits ("Manager Desk 1600 SKYLAND LUMA 927-16"), hyphenated/slash variant
   tokens ("927-16-Walnut", "grey\\brown"), "Chrome", parenthetical pack or
   orientation suffixes ("(2 pcs /1 ctn)", "(r)"), and hyphenated letter codes
   ("EXE-B"), plus per-price-bucket sibling disambiguation.
2. *5868 (14:11 UTC): search_products evaluates exact_media_product_keys from
   customer user_query rather than the LLM's synthesized effective_query so
   open follow-up turns ("Size as same", "Specs as similiar") do not suppress
   offered product photos before _referenced_product_media runs.
3. *2588 (13:12 UTC): _Turn.known_customer_name() honors Zoho CRM contact Name
   so returning contacts greeted by name ("Hi Sumesh...") do not also get
   ", and how should I address you?" appended by the opening guard.
4. *2588 (13:12-13:18 UTC): BASE_SYSTEM_PROMPT states clearly that Treejar is
   not wholesale-only (single items / small orders welcome) and that standalone
   replacement hardware/locks are not sold separately without asking for extra
   close-up photos of broken parts.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from pydantic_ai import RunContext
from pydantic_ai.messages import ToolReturn
from pydantic_ai.models.test import TestModel
from pydantic_ai.usage import RunUsage

from src.llm.catalog_planning import ProductMediaPayload, SalesDeps
from src.llm.engine import search_products
from src.llm.message_processor import _Turn
from src.llm.prompts import BASE_SYSTEM_PROMPT
from src.llm.response_policy import AskKind
from src.llm.response_runtime import (
    _product_model_reference,
    _referenced_product_media,
)
from src.models.conversation import Conversation
from src.schemas.product import ProductRead

UNUSED: Any = cast("Any", None)


# --- 1. *0068 manager desks & active catalog model references ----------------


@pytest.mark.parametrize(
    ("raw_reference", "expected"),
    [
        ("Manager Desk 1600 SKYLAND LUMA 927-16", ("luma", "927", "16")),
        ("Manager Desk 1600 SKYLAND LUMA 9723", ("luma", "9723")),
        ("Manager Desk 1800 SKYLAND LUMA 9723", ("luma", "9723")),
        ("Reception desk 1600 SKYLAND LUMA 9788-8", ("luma", "9788", "8")),
        ("Tea table 1200 SKYLAND LUMA 9781C", ("luma", "9781c")),
        ("Executive office chair CH 145 black Chrome", ("ch", "145")),
        ("Skyland Executive Chair CH 400 grey\\brown", ("ch", "400")),
        ("Operative Office Chair CH 500 V black (2 pcs /1 ctn)", ("ch", "500", "v")),
        (
            "Executive L-shape table, TORR, TCT 2020 (r), 2000x2000x750, oak canyon",
            ("tct", "2020"),
        ),
        ("Executive Desk – EXE-B", ("exe", "b")),
        ("Workstation – WSK-A", ("wsk", "a")),
        ("Opera Office Sofa", ()),
        ("SOFA-OPERA", ()),
    ],
)
def test_product_model_reference_extracts_pilot_and_catalog_codes(
    raw_reference: str,
    expected: tuple[str, ...],
) -> None:
    assert _product_model_reference(raw_reference) == expected


def test_pilot_0068_manager_desk_reply_keeps_all_three_offered_photos() -> None:
    luma_927 = ProductMediaPayload(
        url="https://example.com/luma-927-16.jpg",
        caption="Manager Desk 1600 SKYLAND LUMA 927-16 — 1001.33 AED",
        product_key="luma-927-16",
        reference_tokens=(
            "Manager Desk 1600 SKYLAND LUMA 927-16",
            "OF-HAI-Luma-Table-RJ 927-16-Walnut",
        ),
    )
    luma_9723_1600 = ProductMediaPayload(
        url="https://example.com/luma-9723-1600.jpg",
        caption="Manager Desk 1600 SKYLAND LUMA 9723 — 1412.00 AED",
        product_key="luma-9723-1600",
        reference_tokens=(
            "Manager Desk 1600 SKYLAND LUMA 9723",
            "OF-HAI-Luma-Table-RJ 9723 1600-Walnut",
        ),
    )
    luma_9723_1800 = ProductMediaPayload(
        url="https://example.com/luma-9723-1800.jpg",
        caption="Manager Desk 1800 SKYLAND LUMA 9723 — 1518.67 AED",
        product_key="luma-9723-1800",
        reference_tokens=(
            "Manager Desk 1800 SKYLAND LUMA 9723",
            "OF-HAI-Luma-Table-RJ 9723 1800-Walnut",
        ),
    )
    unoffered_chair = ProductMediaPayload(
        url="https://example.com/ch-270.jpg",
        caption="Operative Chair CH 270 Black — 410.00 AED",
        product_key="ch-270",
        reference_tokens=("Operative Chair CH 270 Black", "CH 270 Black"),
    )
    reply = (
        "*Here are three manager desk options*—apologies for showing workstation "
        "frames earlier.\n\n"
        "1. *LUMA 927-16 — 1600mm*\n"
        "Attached storage drawers.\n"
        "*AED 1,001.33 excl. 5% VAT / AED 1,051.40 incl. 5% VAT.*\n\n"
        "2. *LUMA 9723 — 1600mm*\n"
        "L-shaped with attached drawers and interchangeable left/right configuration.\n"
        "*AED 1,412.00 excl. 5% VAT / AED 1,482.60 incl. 5% VAT.*\n\n"
        "3. *LUMA 9723 — 1800mm*\n"
        "Larger L-shaped workspace with attached storage drawers.\n"
        "*AED 1,518.67 excl. 5% VAT / AED 1,594.60 incl. 5% VAT.*\n\n"
        "Would you prefer the *1600mm desk* or the *L-shaped design*?"
    )

    assert _referenced_product_media(
        (luma_927, luma_9723_1600, luma_9723_1800, unoffered_chair),
        reply,
    ) == (luma_927, luma_9723_1600, luma_9723_1800)


def test_distinctly_priced_model_siblings_both_stay_when_one_has_extra_descriptor() -> (
    None
):
    luma_9723_1600 = ProductMediaPayload(
        url="https://example.com/luma-9723-1600.jpg",
        caption="Manager Desk 1600 SKYLAND LUMA 9723 — 1412.00 AED",
        product_key="luma-9723-1600",
        reference_tokens=(
            "Manager Desk 1600 SKYLAND LUMA 9723",
            "OF-HAI-Luma-Table-RJ 9723 1600-Walnut",
        ),
    )
    luma_9723_1800 = ProductMediaPayload(
        url="https://example.com/luma-9723-1800.jpg",
        caption="Manager Desk 1800 SKYLAND LUMA 9723 — 1518.67 AED",
        product_key="luma-9723-1800",
        reference_tokens=(
            "Manager Desk 1800 SKYLAND LUMA 9723",
            "OF-HAI-Luma-Table-RJ 9723 1800-Walnut",
        ),
    )
    # "1.6m" has no "1600" token while "1800 mm" has "1800"; distinct quoted
    # prices still prove both siblings were offered.
    reply = (
        "1. *LUMA 9723* (1.6m) — AED 1,412.00\n2. *LUMA 9723* (1800 mm) — AED 1,518.67"
    )

    assert _referenced_product_media(
        (luma_9723_1600, luma_9723_1800),
        reply,
    ) == (luma_9723_1600, luma_9723_1800)


# --- 2. *5868 deferred media on open follow-up turns -------------------------


def _make_search_run_context(*, user_query: str) -> RunContext[SalesDeps]:
    conv = Conversation(
        id="00000000-0000-0000-0000-000000005868",
        phone="+971500005868",
        sales_stage="qualifying",
        language="en",
        metadata_={},
    )
    db = AsyncMock()
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    db.execute.return_value = empty_result
    redis = AsyncMock()
    redis.get.return_value = None
    zoho = AsyncMock()
    zoho.get_stock_bulk.return_value = []
    messaging = MagicMock()
    messaging.send_media = AsyncMock()
    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=AsyncMock(),
        zoho_inventory=zoho,
        zoho_crm=None,
        messaging_client=messaging,
        pii_map={},
        crm_context={"Segment": "Unknown"},
        user_query=user_query,
        defer_product_media=True,
    )
    return RunContext(
        deps=deps,
        retry=0,
        messages=[],
        prompt="",
        model=TestModel(),
        usage=RunUsage(),
    )


@pytest.mark.asyncio
async def test_pilot_5868_followup_turn_queues_evoq_and_novo_media_for_reply_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evoq = ProductRead(
        id="11111111-1111-1111-1111-111111111111",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="2 Seats Workstation & fix cabinet SKYLAND EVOQ 1200",
        description_en="Two-seat workstation with fixed storage cabinet",
        sku="2SWC EVOQ 1200",
        price="1240.00",
        currency="AED",
        image_url="https://example.com/2swc%20evoq%201200.jpg",
        created_at="2024-01-01T00:00:00Z",
        stock=6,
        is_active=True,
    )
    novo = ProductRead(
        id="33333333-3333-3333-3333-333333333333",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="2 Person Workstation Table SKYLAND NOVO 1200",
        description_en="Two-person workstation with privacy panels",
        sku="OF-YED-NOVO-Workstation-1200-white",
        price="1120.00",
        currency="AED",
        image_url="https://example.com/novo-1200.jpg",
        created_at="2024-01-01T00:00:00Z",
        stock=8,
        is_active=True,
    )

    class MockResults:
        products = [evoq, novo]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)
    ctx = _make_search_run_context(user_query="Specs as similiar")

    # LLM synthesized an internal query mentioning NOVO 1200 from the prior turn.
    result = await search_products(ctx, "2 person workstation SKYLAND NOVO 1200")

    assert isinstance(result, ToolReturn)
    queued_urls = [item.url for item in ctx.deps.pending_product_media]
    assert queued_urls == [
        "https://example.com/2swc%20evoq%201200.jpg",
        "https://example.com/novo-1200.jpg",
    ]

    pilot_reply = (
        "• *SKYLAND EVOQ 1200* — 2-seat workstation with fixed cabinet, matching "
        "your cabinet requirement.\n"
        "https://treejartrading.ae/product/2-seats-workstation-fix-cabinet-skyland-evoq-1200\n\n"
        "• *SKYLAND NOVO 1200* — 2-person workstation with privacy panels; "
        "cabinet inclusion is not confirmed.\n"
        "https://treejartrading.ae/product/2p-ws-table-skyland-novo-1200\n\n"
        "The EVOQ is the closer match, but exact dimensions and detailed "
        "specifications still need checking. Would you like the *EVOQ 1200 with "
        "fixed cabinet* as the reference model for your requirement?"
    )
    kept = _referenced_product_media(ctx.deps.pending_product_media, pilot_reply)
    assert [item.url for item in kept] == [
        "https://example.com/2swc%20evoq%201200.jpg",
        "https://example.com/novo-1200.jpg",
    ]


@pytest.mark.asyncio
async def test_specific_customer_modifier_still_suppresses_nearby_media(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_product = ProductRead(
        id="11111111-1111-1111-1111-111111111111",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Convertible Sleeper Skyland Chair (Beige)",
        description_en="A multifunctional chair that converts into a sleeper",
        sku="CSC-01 beige",
        price="420.00",
        currency="AED",
        image_url="https://example.com/convertible-sleeper.jpg",
        created_at="2024-01-01T00:00:00Z",
        stock=4,
        is_active=True,
    )
    nearby_product = ProductRead(
        id="33333333-3333-3333-3333-333333333333",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Visitor Chair Grey",
        description_en="Standard guest chair for reception seating",
        sku="CH-999 grey",
        price="180.00",
        currency="AED",
        image_url="https://example.com/visitor-chair.jpg",
        created_at="2024-01-01T00:00:00Z",
        stock=7,
        is_active=True,
    )

    class MockResults:
        products = [exact_product, nearby_product]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)
    ctx = _make_search_run_context(user_query="Convertible chairs")

    await search_products(ctx, "office chairs")

    queued_urls = [item.url for item in ctx.deps.pending_product_media]
    assert queued_urls == ["https://example.com/convertible-sleeper.jpg"]


# --- 3. *2588 returning Zoho CRM contact name suppression --------------------


def _make_first_turn_with_crm(crm_context: dict[str, str] | None) -> _Turn:
    conv = Conversation(
        phone="+971500002588",
        language="en",
        customer_name=None,
        metadata_={},
    )
    deps = SalesDeps(
        db=UNUSED,
        redis=UNUSED,
        conversation=conv,
        embedding_engine=UNUSED,
        zoho_inventory=UNUSED,
        zoho_crm=None,
        messaging_client=UNUSED,
        pii_map={},
        crm_context=crm_context,
        user_query="Wholesale only?",
        recent_history=["user:Wholesale only?"],
    )
    return _Turn(
        db=UNUSED,
        redis=UNUSED,
        conversation_id=uuid4(),
        embedding_engine=UNUSED,
        zoho_client=UNUSED,
        messaging_client=UNUSED,
        crm_client=None,
        source_message_id=None,
        latency_trace=None,
        context_started=None,
        conv=conv,
        crm_context=crm_context,
        pii_map={},
        history=[],
        is_first_turn=True,
        model_runtime=UNUSED,
        current_message_quote_customer_details={},
        combined_text="Wholesale only?",
        masked_text="Wholesale only?",
        recent_history=["user:Wholesale only?"],
        deps=deps,
    )


def test_pilot_2588_crm_contact_name_prevents_how_should_i_address_you_ask() -> None:
    turn = _make_first_turn_with_crm(
        {"Name": "Sumesh", "Segment": "Unknown", "Returning_Customer": "yes"}
    )

    assert turn.known_customer_name() == "Sumesh"
    assert AskKind.CUSTOMER_NAME not in turn.permitted_asks()

    draft = (
        "Hi Sumesh, Noor from Treejar here. We supply office furniture in the UAE, "
        "and single items or small orders are welcome.\n\n"
        "Are you looking for a single item or a larger order?"
    )
    rendered = turn.render_reply(
        draft,
        response_deps=turn.deps,
        provenance="model",
        model_name="test-model",
    )
    assert "how should i address you" not in rendered.text.casefold()
    assert "may i know your name" not in rendered.text.casefold()


def test_crm_placeholder_name_still_allows_customer_name_ask() -> None:
    turn = _make_first_turn_with_crm(
        {"Name": "Unknown", "Segment": "Unknown", "Returning_Customer": "no"}
    )

    assert turn.known_customer_name() == ""
    assert AskKind.CUSTOMER_NAME in turn.permitted_asks()


# --- 4. *2588 wholesale-only & standalone spare-part prompt guidance ---------


def test_base_system_prompt_covers_small_orders_and_standalone_spare_parts() -> None:
    lower = BASE_SYSTEM_PROMPT.casefold()
    assert "not wholesale-only" in lower
    assert "single" in lower
    assert "replacement" in lower
    assert "close-up photo" in lower or "close-up photos" in lower
