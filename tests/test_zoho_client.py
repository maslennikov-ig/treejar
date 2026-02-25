"""Unit tests for ZohoInventoryClient covering token lock timeout,
401-triggered refresh, and 429 rate-limit backoff (TCG-01, TCG-02, TCG-03)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.integrations.inventory.zoho_inventory import ZohoInventoryClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_body: dict[str, object] | None = None) -> httpx.Response:
    """Build a real httpx.Response so raise_for_status() works correctly."""
    return httpx.Response(
        status_code,
        json=json_body or {},
        request=httpx.Request("GET", "https://example.com"),
    )


# ---------------------------------------------------------------------------
# TCG-01: Token lock timeout
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_token_timeout_when_lock_held() -> None:
    """When the lock is held by another worker and the token never appears,
    _ensure_token must raise RuntimeError after exhausting all retries."""
    redis = AsyncMock()

    # redis.get always returns None — no token present
    redis.get.return_value = None
    # redis.set returns False — lock not acquired (another worker holds it)
    redis.set.return_value = False

    client = ZohoInventoryClient(redis)

    # Patch asyncio.sleep so the test does not actually wait 10 seconds
    with (
        patch("src.integrations.inventory.zoho_inventory.asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        pytest.raises(RuntimeError, match="Timeout waiting for Zoho token refresh lock"),
    ):
        await client._ensure_token()

    # sleep must have been called exactly 20 times (the retry loop)
    assert mock_sleep.call_count == 20

    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_token_returns_when_token_appears_during_wait() -> None:
    """When another worker refreshes the token mid-wait, _ensure_token returns it."""
    redis = AsyncMock()

    # First get: no token; lock not acquired; subsequent get: token present
    redis.get.side_effect = [None, None, b"refreshed_token"]
    redis.set.return_value = False  # lock held by other worker

    client = ZohoInventoryClient(redis)

    with patch("src.integrations.inventory.zoho_inventory.asyncio.sleep", new_callable=AsyncMock):
        token = await client._ensure_token()

    assert token == "refreshed_token"
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_token_uses_cached_token_on_first_get() -> None:
    """If a valid token already exists in Redis, it is returned immediately."""
    redis = AsyncMock()
    redis.get.return_value = b"cached_token"

    client = ZohoInventoryClient(redis)
    token = await client._ensure_token()

    assert token == "cached_token"
    # Lock should never be attempted
    redis.set.assert_not_called()
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_ensure_token_refreshes_and_caches_when_lock_acquired() -> None:
    """When no token exists and we win the lock, _ensure_token fetches and
    caches a new OAuth token from Zoho."""
    redis = AsyncMock()
    # First get (before lock): no token; second get (double-check inside lock): no token
    redis.get.return_value = None
    # Lock acquired
    redis.set.return_value = True
    redis.delete.return_value = 1

    new_token_response = _make_response(
        200,
        {"access_token": "brand_new_token", "expires_in": 3600},
    )

    client = ZohoInventoryClient(redis)

    with patch("httpx.AsyncClient") as MockHttpxClient:
        mock_ctx = MockHttpxClient.return_value.__aenter__.return_value
        mock_ctx.post = AsyncMock(return_value=new_token_response)

        token = await client._ensure_token()

    assert token == "brand_new_token"
    # Token should have been stored in Redis
    redis.set.assert_awaited()
    # Lock should have been released
    redis.delete.assert_awaited_with("zoho:access_token:lock")
    await client.close()


# ---------------------------------------------------------------------------
# TCG-02: 401 triggers token delete + retry
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_retries_after_401() -> None:
    """On a 401 response the client must delete the cached token from Redis
    and retry the request.  The second attempt returns 200."""
    redis = AsyncMock()
    redis.get.return_value = b"stale_token"
    redis.delete.return_value = 1

    client = ZohoInventoryClient(redis)

    response_401 = _make_response(401)
    response_200 = _make_response(200, {"items": [], "page_context": {}})

    with patch.object(
        client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [response_401, response_200]

        response = await client._request("GET", "/items")

    assert response.status_code == 200
    # Token must have been deleted after the 401
    redis.delete.assert_awaited_with("zoho:access_token")
    # Two HTTP requests made: the failing 401 and the successful retry
    assert mock_request.call_count == 2
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_raises_after_three_consecutive_401s() -> None:
    """If every attempt returns 401 (max_retries=3), the last raise_for_status()
    must propagate an HTTPStatusError."""
    redis = AsyncMock()
    redis.get.return_value = b"bad_token"
    redis.delete.return_value = 1

    client = ZohoInventoryClient(redis)

    response_401 = _make_response(401)

    with patch.object(
        client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.return_value = response_401

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client._request("GET", "/items")

    assert exc_info.value.response.status_code == 401
    # Token delete called on each 401 attempt (attempts 1 and 2, not on last one
    # because the loop doesn't continue after attempt == max_retries)
    assert redis.delete.call_count >= 1
    await client.close()


# ---------------------------------------------------------------------------
# TCG-03: 429 rate-limit triggers exponential backoff
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_backs_off_on_429_then_succeeds() -> None:
    """A 429 response on the first attempt causes asyncio.sleep(2**1) == 2 s
    backoff, then the second attempt returns 200."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"

    client = ZohoInventoryClient(redis)

    response_200 = _make_response(200, {"ok": True})

    def _make_429_error() -> httpx.HTTPStatusError:
        resp_429 = _make_response(429)
        return httpx.HTTPStatusError("Rate limited", request=resp_429.request, response=resp_429)

    with patch.object(
        client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [_make_429_error(), response_200]

        with patch(
            "src.integrations.inventory.zoho_inventory.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            response = await client._request("GET", "/items")

    assert response.status_code == 200
    # Backoff sleep must have been called: 2**1 == 2 seconds on attempt 1
    mock_sleep.assert_awaited_once_with(2)
    assert mock_request.call_count == 2
    await client.close()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_request_raises_after_repeated_429_exhausts_retries() -> None:
    """If every attempt returns 429 and we run out of retries, the last
    HTTPStatusError must propagate."""
    redis = AsyncMock()
    redis.get.return_value = b"valid_token"

    client = ZohoInventoryClient(redis)

    def _make_429_error() -> httpx.HTTPStatusError:
        resp_429 = _make_response(429)
        return httpx.HTTPStatusError("Rate limited", request=resp_429.request, response=resp_429)

    with patch.object(
        client.client, "request", new_callable=AsyncMock
    ) as mock_request:
        mock_request.side_effect = [_make_429_error(), _make_429_error(), _make_429_error()]

        with patch(
            "src.integrations.inventory.zoho_inventory.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep, pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client._request("GET", "/items")

    assert exc_info.value.response.status_code == 429
    # Backoff called for attempts 1 and 2 (not after the last failure)
    assert mock_sleep.call_count == 2
    # Exponential backoff values: 2**1=2, 2**2=4
    calls = [c.args[0] for c in mock_sleep.call_args_list]
    assert calls == [2, 4]
    await client.close()
