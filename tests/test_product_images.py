import asyncio
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import ToolReturn

from src.core.config import settings
from src.llm.engine import SalesDeps, search_products
from src.models.conversation import Conversation
from src.schemas.product import ProductRead

pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_messaging_client() -> MagicMock:
    client = MagicMock()
    client.send_media = AsyncMock()
    return client


@pytest.fixture
def run_context(mock_messaging_client: MagicMock) -> Any:
    deps = SalesDeps(
        db=AsyncMock(),
        redis=AsyncMock(),
        conversation=Conversation(
            id="00000000-0000-0000-0000-000000000000",
            phone="+1234567890",
            sales_stage="greeting",
            language="en",
        ),
        embedding_engine=AsyncMock(),
        zoho_inventory=AsyncMock(),
        zoho_crm=AsyncMock(),
        messaging_client=mock_messaging_client,
        pii_map={},
        crm_context={"Segment": "Unknown"},
    )

    @dataclass
    class _FakeRunContext:
        deps: SalesDeps

    return _FakeRunContext(deps=deps)


@pytest.fixture
def restore_media_url_settings() -> Any:
    original_env = settings.app_env
    original_domain = settings.domain
    yield
    settings.app_env = original_env
    settings.domain = original_domain


async def test_search_products_sends_image_if_present(
    run_context: Any,
    monkeypatch: pytest.MonkeyPatch,
    mock_messaging_client: MagicMock,
) -> None:
    # Mock rag_search_products to return a product with an image_url
    product1 = ProductRead(
        id="11111111-1111-1111-1111-111111111111",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Test Chair",
        description_en="A great chair",
        sku="CHAIR-01",
        price="100.00",
        currency="AED",
        image_url="https://example.com/chair.jpg",
        created_at="2024-01-01T00:00:00Z",
        stock=10,
        is_active=True,
    )
    product2 = ProductRead(
        id="33333333-3333-3333-3333-333333333333",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Test Table",
        description_en="A great table",
        sku="TABLE-01",
        price="200.00",
        currency="AED",
        image_url=None,
        created_at="2024-01-01T00:00:00Z",
        stock=5,
        is_active=True,
    )

    class MockResults:
        products = [product1, product2]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)

    result = await search_products(run_context, "furniture")
    assert isinstance(result, ToolReturn)

    # Verify text reflects WhatsApp image delivery, without leaking raw URLs.
    assert "automatically sent to the customer's WhatsApp" in result.return_value
    assert "Test Table" in result.return_value
    assert "https://example.com/chair.jpg" not in result.return_value

    # Verify send_media was called once (for product1)
    mock_messaging_client.send_media.assert_called_once_with(
        chat_id="+1234567890",
        url="https://example.com/chair.jpg",
        caption="Test Chair — 100.00 AED",
        content=None,
        content_type=None,
        crm_message_id=(
            "product:00000000-0000-0000-0000-000000000000:"
            "11111111-1111-1111-1111-111111111111:media"
        ),
        caption_crm_message_id=(
            "product:00000000-0000-0000-0000-000000000000:"
            "11111111-1111-1111-1111-111111111111:caption"
        ),
    )
    run_context.deps.db.commit.assert_awaited_once()


async def test_search_products_shows_catalog_only_customer_facing_option(
    run_context: Any,
    monkeypatch: pytest.MonkeyPatch,
    mock_messaging_client: MagicMock,
) -> None:
    product = ProductRead(
        id="66666666-6666-6666-6666-666666666666",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Catalog Truth Chair",
        description_en="Catalog item shown from the public catalog only",
        sku="00-07024023",
        price="264.00",
        currency="AED",
        image_url=None,
        zoho_item_id=None,
        created_at="2024-01-01T00:00:00Z",
        stock=12,
        is_active=True,
    )

    class MockResults:
        products = [product]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)

    result = await search_products(run_context, "00-07024023")

    assert isinstance(result, ToolReturn)
    assert "00-07024023" in result.return_value
    assert "264.00 AED" in result.return_value
    assert "customer-facing catalog price" in result.return_value.lower()
    assert "zoho" not in result.return_value.lower()
    mock_messaging_client.send_media.assert_not_called()


async def test_search_products_sends_multiple_images_sequentially(
    run_context: Any,
    monkeypatch: pytest.MonkeyPatch,
    mock_messaging_client: MagicMock,
) -> None:
    products = [
        ProductRead(
            id="11111111-1111-1111-1111-111111111111",
            category_id="22222222-2222-2222-2222-222222222222",
            name_en="Test Chair",
            description_en="A great chair",
            sku="CHAIR-01",
            price="100.00",
            currency="AED",
            image_url="https://example.com/chair.jpg",
            created_at="2024-01-01T00:00:00Z",
            stock=10,
            is_active=True,
        ),
        ProductRead(
            id="33333333-3333-3333-3333-333333333333",
            category_id="22222222-2222-2222-2222-222222222222",
            name_en="Test Sofa",
            description_en="A great sofa",
            sku="SOFA-01",
            price="300.00",
            currency="AED",
            image_url="https://example.com/sofa.jpg",
            created_at="2024-01-01T00:00:00Z",
            stock=3,
            is_active=True,
        ),
    ]

    class MockResults:
        pass

    MockResults.products = products

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    in_send = False
    concurrent_entries = 0

    async def send_media_side_effect(**kwargs: Any) -> str:
        nonlocal in_send, concurrent_entries
        if in_send:
            concurrent_entries += 1
        in_send = True
        await asyncio.sleep(0)
        in_send = False
        return f"wz-msg-{mock_messaging_client.send_media.await_count}"

    mock_messaging_client.send_media.side_effect = send_media_side_effect
    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)

    result = await search_products(run_context, "furniture")

    assert isinstance(result, ToolReturn)
    assert mock_messaging_client.send_media.await_count == 2
    assert concurrent_entries == 0
    assert run_context.deps.db.commit.await_count == 2


async def test_search_products_graceful_fallback(
    run_context: Any,
    monkeypatch: pytest.MonkeyPatch,
    mock_messaging_client: MagicMock,
) -> None:
    product1 = ProductRead(
        id="11111111-1111-1111-1111-111111111111",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Test Chair",
        description_en="A great chair",
        sku="CHAIR-01",
        price="100.00",
        currency="AED",
        image_url="https://example.com/chair.jpg",
        created_at="2024-01-01T00:00:00Z",
        stock=10,
        is_active=True,
    )

    class MockResults:
        products = [product1]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)

    # Force send_media to raise exception
    mock_messaging_client.send_media.side_effect = Exception("Network error")

    # Should not raise
    result = await search_products(run_context, "furniture")
    assert isinstance(result, ToolReturn)

    assert "automatically sent to the customer's WhatsApp" in result.return_value
    assert "https://example.com/chair.jpg" not in result.return_value
    mock_messaging_client.send_media.assert_called_once()


async def test_search_products_uses_signed_proxy_for_zoho_images(
    run_context: Any,
    monkeypatch: pytest.MonkeyPatch,
    mock_messaging_client: MagicMock,
    restore_media_url_settings: Any,
) -> None:
    settings.app_env = "production"
    settings.domain = ""

    product = ProductRead(
        id="44444444-4444-4444-4444-444444444444",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Focus Pod",
        description_en="Acoustic pod",
        sku="POD-01",
        price="25000.00",
        currency="AED",
        image_url="https://inventory.zoho.eu/api/v1/documents/abc",
        zoho_item_id="ZOHO-ITEM-1",
        created_at="2024-01-01T00:00:00Z",
        stock=2,
        is_active=True,
    )

    class MockResults:
        products = [product]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    run_context.deps.zoho_inventory.get_item_image = AsyncMock(
        return_value=(b"fake-image", "image/jpeg")
    )
    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)

    result = await search_products(run_context, "acoustic pod")
    assert isinstance(result, ToolReturn)

    _, kwargs = mock_messaging_client.send_media.call_args
    assert kwargs["chat_id"] == "+1234567890"
    assert kwargs["url"].startswith(
        "https://noor.starec.ai/api/v1/public-media/products/ZOHO-ITEM-1?token="
    )
    assert kwargs["content"] is None
    assert kwargs["content_type"] is None
    run_context.deps.zoho_inventory.get_item_image.assert_not_awaited()


async def test_search_products_skips_zoho_media_when_domain_missing_in_non_production(
    run_context: Any,
    monkeypatch: pytest.MonkeyPatch,
    mock_messaging_client: MagicMock,
    restore_media_url_settings: Any,
) -> None:
    settings.app_env = "development"
    settings.domain = ""

    product = ProductRead(
        id="55555555-5555-5555-5555-555555555555",
        category_id="22222222-2222-2222-2222-222222222222",
        name_en="Silent Pod",
        description_en="Acoustic pod",
        sku="POD-02",
        price="26000.00",
        currency="AED",
        image_url="https://inventory.zoho.eu/api/v1/documents/xyz",
        zoho_item_id="ZOHO-ITEM-2",
        created_at="2024-01-01T00:00:00Z",
        stock=1,
        is_active=True,
    )

    class MockResults:
        products = [product]

    async def mock_rag_search(*args: Any, **kwargs: Any) -> MockResults:
        return MockResults()

    monkeypatch.setattr("src.llm.engine.rag_search_products", mock_rag_search)

    result = await search_products(run_context, "acoustic pod")
    assert isinstance(result, ToolReturn)
    mock_messaging_client.send_media.assert_not_called()
