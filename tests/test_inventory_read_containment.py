"""Unavailable reads remain tool evidence; mutations are never retried blindly."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from pydantic_ai import Agent
from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart, ToolReturnPart
from pydantic_ai.models.function import FunctionModel

from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.llm import engine
from src.llm.inventory_read import InventoryReadUnavailable, inventory_read
from tests.test_model_search_intent import _context


def rate_limit(retry_after: str | None = "30"):
    request = httpx.Request("GET", "https://inventory.example/items")
    headers = {"retry-after": retry_after} if retry_after else {}
    response = httpx.Response(429, request=request, headers=headers)
    return httpx.HTTPStatusError("rate limit", request=request, response=response)


@pytest.mark.asyncio
@pytest.mark.parametrize("catalog_item", [None, SimpleNamespace(zoho_item_id="item-1")])
async def test_stock_429_is_honest_tool_result_without_fabricated_snapshot(
    catalog_item,
):
    ctx = _context("Check the stock")
    ctx.deps.zoho_inventory.get_item.side_effect = rate_limit()
    ctx.deps.zoho_inventory.get_stock.side_effect = rate_limit()
    with patch.object(
        engine, "_find_catalog_product_by_sku", AsyncMock(return_value=catalog_item)
    ):
        result = await engine.get_stock(ctx, "NOVO")
    assert result.return_value["status"] == "temporarily_unavailable"
    assert result.return_value["reason"] == "rate_limited"
    assert result.return_value["retry_after_seconds"] == 30
    assert result.return_value["stock_confirmed"] is False
    assert ctx.deps.stock_snapshots == {}
    assert ctx.deps.inventory_confirmed is False
    assert not ctx.deps.quotation_created
    ctx.deps.messaging_client.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_read_failure_reaches_model_for_a_contextual_answer():
    ctx = _context("Is NOVO available?")
    ctx.deps.zoho_inventory.get_stock.side_effect = rate_limit()

    def model(messages, info):
        returns = [
            part
            for message in messages
            for part in message.parts
            if isinstance(part, ToolReturnPart)
        ]
        if not returns:
            return ModelResponse(parts=[ToolCallPart("get_stock", {"sku": "NOVO"})])
        assert returns[-1].content["stock_confirmed"] is False
        return ModelResponse(
            parts=[TextPart("I cannot confirm NOVO availability yet.")]
        )

    agent = Agent(
        FunctionModel(model), deps_type=engine.SalesDeps, tools=[engine.get_stock]
    )
    with patch.object(
        engine, "_find_catalog_product_by_sku", AsyncMock(return_value=None)
    ):
        result = await agent.run("Is NOVO available?", deps=ctx.deps)
    assert result.output == "I cannot confirm NOVO availability yet."


@pytest.mark.asyncio
async def test_inventory_read_does_not_mask_unrelated_http_errors():
    request = httpx.Request("GET", "https://inventory.example/items")
    error = httpx.HTTPStatusError(
        "forbidden", request=request, response=httpx.Response(403, request=request)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await inventory_read(AsyncMock(side_effect=error))
    result = InventoryReadUnavailable(
        status_code=429, retry_after="provider secret"
    ).tool_result("NOVO")
    assert result.return_value["retry_after_seconds"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("method,attempts", [("GET", 3), ("POST", 1)])
@pytest.mark.parametrize("failure", ["429", "timeout"])
async def test_only_idempotent_inventory_reads_are_retried(method, attempts, failure):
    redis = AsyncMock()
    redis.get.return_value = b"token"
    client = ZohoInventoryClient(redis_client=redis)
    # A 429 without Retry-After uses the bounded 2s/4s backoff; a longer
    # Retry-After ends the request at once (covered in test_zoho_rate_limit).
    error = (
        rate_limit(retry_after=None)
        if failure == "429"
        else httpx.ReadTimeout("unknown outcome")
    )
    try:
        with (
            patch.object(
                client.client, "request", AsyncMock(side_effect=error)
            ) as request,
            patch(
                "src.integrations.inventory.zoho_inventory.asyncio.sleep", AsyncMock()
            ) as sleep,
            pytest.raises(type(error)),
        ):
            await client._request(method, "/items")
        assert request.await_count == attempts
        assert sleep.await_count == attempts - 1
    finally:
        await client.client.aclose()


@pytest.mark.asyncio
async def test_notification_failure_is_not_misreported_as_an_inventory_read():
    ctx = _context("Check NOVO")
    ctx.deps.zoho_inventory.get_stock.return_value = None
    with (
        patch.object(
            engine,
            "_find_catalog_product_by_sku",
            AsyncMock(return_value=SimpleNamespace(zoho_item_id=None)),
        ),
        patch.object(
            engine,
            "_record_catalog_mismatch_and_alert",
            AsyncMock(side_effect=rate_limit()),
        ),
        pytest.raises(httpx.HTTPStatusError),
    ):
        await engine.get_stock(ctx, "NOVO")
