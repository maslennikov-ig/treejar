from unittest.mock import AsyncMock, patch

import pytest

from src.integrations.inventory.zoho_inventory import ZohoInventoryClient


@pytest.mark.asyncio
async def test_create_draft_sale_order() -> None:
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"test_token"

    zoho_client = ZohoInventoryClient(redis_client=redis_mock)

    from unittest.mock import MagicMock

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={"saleorder": {"salesorder_id": "123", "status": "draft"}}
    )

    with patch("httpx.AsyncClient.request", return_value=mock_response) as mock_req:
        result = await zoho_client.create_sale_order(
            customer_id="customer123",
            items=[{"item_id": "item123", "quantity": 2}],
            status="draft",
        )

        assert result["saleorder"]["status"] == "draft"
        assert result["saleorder"]["salesorder_id"] == "123"

        # Verify request parameters
        mock_req.assert_called_once()
        _, kwargs = mock_req.call_args
        assert kwargs["json"]["customer_id"] == "customer123"
        assert kwargs["json"]["line_items"][0]["item_id"] == "item123"
        assert kwargs["json"]["status"] == "draft"
