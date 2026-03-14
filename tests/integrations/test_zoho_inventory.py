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


@pytest.mark.asyncio
async def test_get_sale_order_status_confirmed() -> None:
    """get_sale_order_status returns normalized status dict for confirmed order."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"test_token"

    zoho_client = ZohoInventoryClient(redis_client=redis_mock)

    import httpx

    mock_response = httpx.Response(
        200,
        json={
            "salesorder": {
                "salesorder_id": "SO001",
                "salesorder_number": "SO-00003",
                "status": "confirmed",
                "shipment_date": "2026-04-01",
                "delivery_method": "Standard",
                "total": 1500.0,
                "customer_name": "John Doe",
            }
        },
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(zoho_client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response
        result = await zoho_client.get_sale_order_status("SO001")

    assert result is not None
    assert result["salesorder_number"] == "SO-00003"
    assert result["status"] == "confirmed"
    assert result["shipment_date"] == "2026-04-01"
    assert result["delivery_method"] == "Standard"
    assert result["total"] == 1500.0
    assert result["customer_name"] == "John Doe"


@pytest.mark.asyncio
async def test_get_sale_order_status_not_found() -> None:
    """get_sale_order_status returns None when order not found (404)."""
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"test_token"

    zoho_client = ZohoInventoryClient(redis_client=redis_mock)

    import httpx

    mock_response = httpx.Response(
        404,
        json={"code": 1002, "message": "Sales Order not found"},
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(zoho_client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = httpx.HTTPStatusError(
            "Not Found", request=mock_response.request, response=mock_response
        )
        result = await zoho_client.get_sale_order_status("NONEXISTENT")

    assert result is None
