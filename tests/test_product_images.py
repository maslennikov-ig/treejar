from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

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

    # Verify text reflects WhatsApp image delivery, without leaking raw URLs.
    assert "automatically sent to the customer's WhatsApp" in result
    assert "Test Table" in result
    assert "https://example.com/chair.jpg" not in result

    # Verify send_media was called once (for product1)
    mock_messaging_client.send_media.assert_called_once_with(
        chat_id="+1234567890",
        url="https://example.com/chair.jpg",
        caption="Test Chair — 100.00 AED",
        content=None,
        content_type=None,
    )


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

    assert "automatically sent to the customer's WhatsApp" in result
    assert "https://example.com/chair.jpg" not in result
    mock_messaging_client.send_media.assert_called_once()
