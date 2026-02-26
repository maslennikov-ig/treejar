"""Unit tests for ZohoCRMClient."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.integrations.crm.zoho_crm import ZohoCRMClient


def _make_response(status_code: int, json_body: dict[str, object] | None = None) -> httpx.Response:
    """Build a real httpx.Response so raise_for_status() works correctly."""
    return httpx.Response(
        status_code,
        json=json_body or {},
        request=httpx.Request("GET", "https://example.com"),
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_token_uses_cached_token_on_first_get() -> None:
    """If a valid token already exists in Redis, it is returned immediately."""
    redis = AsyncMock()
    redis.get.return_value = b"cached_crm_token"

    client = ZohoCRMClient(redis)
    token = await client._ensure_token()

    assert token == "cached_crm_token"
    redis.set.assert_not_called()
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_retries_after_401() -> None:
    """On a 401 response the client must delete the cached token from Redis and retry."""
    redis = AsyncMock()
    redis.get.return_value = b"stale_token"
    redis.delete.return_value = 1

    client = ZohoCRMClient(redis)

    response_401 = _make_response(401)
    response_200 = _make_response(200, {"data": []})

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.side_effect = [response_401, response_200]

        response = await client._request("GET", "/Contacts")

    assert response.status_code == 200
    redis.delete.assert_awaited_with("zoho_crm:access_token")
    assert mock_request.call_count == 2
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_contact_by_phone_found() -> None:
    """find_contact_by_phone returns a dict if contact is found."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"
    client = ZohoCRMClient(redis)

    response_200 = _make_response(200, {"data": [{"id": "123", "Phone": "+123"}]})

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_200
        result = await client.find_contact_by_phone("+123")

    assert result == {"id": "123", "Phone": "+123"}
    mock_request.assert_awaited_once()
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_find_contact_by_phone_not_found_204() -> None:
    """find_contact_by_phone returns None if API returns 204 No Content."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"
    client = ZohoCRMClient(redis)

    response_204 = _make_response(204)  # No content

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_204
        result = await client.find_contact_by_phone("+123")

    assert result is None
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_contact() -> None:
    """create_contact payload packaging."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"
    client = ZohoCRMClient(redis)

    response_200 = _make_response(200, {"data": [{"code": "SUCCESS", "details": {"id": "456"}}]})

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_200
        result = await client.create_contact({"Last_Name": "Doe"})

    mock_request.assert_awaited_once_with(
        method="POST",
        url="/Contacts",
        params=None,
        json={"data": [{"Last_Name": "Doe"}]},
        headers={"Authorization": "Zoho-oauthtoken valid_token"},
    )
    assert result == {"code": "SUCCESS", "details": {"id": "456"}}
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_create_deal() -> None:
    """create_deal payload packaging."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"
    client = ZohoCRMClient(redis)

    response_200 = _make_response(200, {"data": [{"code": "SUCCESS", "details": {"id": "789"}}]})

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_200
        result = await client.create_deal({"Deal_Name": "Test Deal"})

    assert result == {"code": "SUCCESS", "details": {"id": "789"}}
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_update_deal() -> None:
    """update_deal payload packaging."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"
    client = ZohoCRMClient(redis)

    response_200 = _make_response(200, {"data": [{"code": "SUCCESS"}]})

    with patch.object(client.client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = response_200
        result = await client.update_deal("789", {"Stage": "Closed Won"})

    mock_request.assert_awaited_once_with(
        method="PUT",
        url="/Deals/789",
        params=None,
        json={"data": [{"Stage": "Closed Won"}]},
        headers={"Authorization": "Zoho-oauthtoken valid_token"},
    )
    assert result == {"code": "SUCCESS"}
    await client.close()
