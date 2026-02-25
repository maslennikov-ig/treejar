from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.inventory.sync import sync_products_from_zoho
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient


@pytest.fixture
def mock_redis() -> AsyncMock:
    redis = AsyncMock()
    # Mock token already existing
    redis.get.return_value = b"fake_token"
    return redis

@pytest.mark.asyncio
@pytest.mark.unit
async def test_zoho_client_get_items(mock_redis: AsyncMock) -> None:
    client = ZohoInventoryClient(mock_redis)
    import httpx
    mock_response = httpx.Response(
        200,
        json={
            "items": [{"item_id": "1", "sku": "SKU1"}],
            "page_context": {"has_more_page": False}
        },
        request=httpx.Request("GET", "https://example.com")
    )
    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        result = await client.get_items(page=1)
        assert "items" in result
        assert result["items"][0]["sku"] == "SKU1"
        assert not result["page_context"]["has_more_page"]
    await client.close()

@pytest.mark.asyncio
@pytest.mark.unit
async def test_sync_products_job(mock_redis: AsyncMock) -> None:
    ctx: dict[str, Any] = {"redis": mock_redis}
    mock_api_items = [
        {
            "item_id": "zoho_1",
            "sku": "CHAIR-01",
            "name": "Office Chair",
            "group_name": "Seating",
            "rate": 150.0,
            "stock_on_hand": 50,
            "image_document_id": "doc123",
            "status": "active"
        }
    ]
    with patch("src.integrations.inventory.sync.ZohoInventoryClient") as MockClient:
        instance = MockClient.return_value
        instance.get_items = AsyncMock(return_value={
            "items": mock_api_items,
            "page_context": {"has_more_page": False}
        })
        instance.close = AsyncMock()
        with patch("src.integrations.inventory.sync._upsert_items_batch", new_callable=AsyncMock) as mock_upsert:
            result = await sync_products_from_zoho(ctx)
            assert mock_upsert.called
            assert "synced" in result
            assert "errors" in result
