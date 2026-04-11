from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.inventory.zoho_inventory import ZohoInventoryClient


@pytest.mark.asyncio
async def test_create_draft_sale_order() -> None:
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"test_token"

    zoho_client = ZohoInventoryClient(redis_client=redis_mock)

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

    with patch.object(
        zoho_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
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

    with patch.object(
        zoho_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = httpx.HTTPStatusError(
            "Not Found", request=mock_response.request, response=mock_response
        )
        result = await zoho_client.get_sale_order_status("NONEXISTENT")

    assert result is None


@pytest.mark.asyncio
async def test_find_customer_by_phone_returns_accessible_active_customer() -> None:
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"test_token"

    zoho_client = ZohoInventoryClient(redis_client=redis_mock)

    list_response = httpx.Response(
        200,
        json={
            "contacts": [
                {
                    "contact_id": "460000000026049",
                    "contact_name": "Bowman and Co",
                    "contact_type": "customer",
                    "status": "active",
                    "phone": "+971-50-123-4567",
                    "mobile": "+971501234567",
                }
            ]
        },
        request=httpx.Request("GET", "https://example.com/contacts"),
    )
    get_response = httpx.Response(
        200,
        json={
            "contact": {
                "contact_id": "460000000026049",
                "contact_name": "Bowman and Co",
                "contact_type": "customer",
                "status": "active",
                "contact_persons": [
                    {
                        "phone": "+971-50-123-4567",
                        "mobile": "+971501234567",
                    }
                ],
            }
        },
        request=httpx.Request("GET", "https://example.com/contacts/460000000026049"),
    )

    with patch.object(
        zoho_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [list_response, get_response]
        result = await zoho_client.find_customer_by_phone("+971501234567")

    assert result is not None
    assert result["contact_id"] == "460000000026049"
    assert mock_request.await_count == 2


@pytest.mark.asyncio
async def test_create_contact_returns_created_customer() -> None:
    redis_mock = AsyncMock()
    redis_mock.get.return_value = b"test_token"

    zoho_client = ZohoInventoryClient(redis_client=redis_mock)

    response = httpx.Response(
        200,
        json={
            "contact": {
                "contact_id": "460000000026049",
                "contact_name": "Ahmed Noor",
                "contact_type": "customer",
                "status": "active",
            }
        },
        request=httpx.Request("POST", "https://example.com/contacts"),
    )

    with patch.object(
        zoho_client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response
        result = await zoho_client.create_contact(
            {
                "contact_name": "Ahmed Noor",
                "contact_type": "customer",
                "company_name": "Treejar Trading",
                "contact_persons": [
                    {
                        "first_name": "Ahmed",
                        "last_name": "Noor",
                        "phone": "+971501234567",
                        "mobile": "+971501234567",
                        "email": "ahmed@example.com",
                        "is_primary_contact": True,
                    }
                ],
            }
        )

    assert result["contact_id"] == "460000000026049"
    _, kwargs = mock_request.call_args
    assert kwargs["json"]["contact_type"] == "customer"
    assert kwargs["json"]["contact_persons"][0]["phone"] == "+971501234567"
