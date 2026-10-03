"""Real, disposable Redis and synthetic provider transport for stock acceptance."""

from __future__ import annotations

import subprocess
import time
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

import httpx
import pytest
import pytest_asyncio
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError

from src.core.config import settings
from src.integrations.inventory.stock_state import STATE_KEY, StockState
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient


@pytest.fixture(scope="session")
def stock_redis_url() -> Iterator[str]:
    name = f"treejar-tj-uvld-test-{uuid.uuid4().hex[:12]}"
    # Docker pulls this public test image on clean runners. Failure is fatal;
    # there is no production service fallback or silent race-test skip.
    subprocess.run(
        [
            "docker",
            "run",
            "--detach",
            "--rm",
            "--name",
            name,
            "--publish",
            "127.0.0.1::6379",
            "redis:7.2-alpine",
            "redis-server",
            "--save",
            "",
            "--appendonly",
            "no",
        ],
        check=True,
        capture_output=True,
    )
    try:
        port = (
            subprocess.run(
                ["docker", "port", name, "6379/tcp"],
                check=True,
                capture_output=True,
                text=True,
            )
            .stdout.strip()
            .split(":")[-1]
        )
        yield f"redis://127.0.0.1:{port}/0"
    finally:
        subprocess.run(["docker", "stop", name], check=True, capture_output=True)


@pytest_asyncio.fixture(loop_scope="function")
async def stock_redis(stock_redis_url: str) -> AsyncIterator[Redis]:
    redis = Redis.from_url(stock_redis_url, decode_responses=True)
    for _ in range(100):
        try:
            await redis.ping()
            break
        except RedisConnectionError:
            import asyncio

            await asyncio.sleep(0.05)
    else:
        raise AssertionError("Disposable Redis did not start")
    await redis.flushdb()  # Only this session's exact task-owned container.
    await redis.set("zoho:access_token", "synthetic-token")
    try:
        yield redis
    finally:
        await redis.aclose()


@pytest.fixture
def eligible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "zoho_stock_incremental_enabled", True)
    monkeypatch.setattr(
        settings, "zoho_stock_coverage_evidence", "synthetic-coverage-not-live"
    )
    monkeypatch.setattr(settings, "zoho_stock_bulk_size", 2)
    monkeypatch.setattr(
        settings, "zoho_stock_bulk_evidence", "synthetic-boundary-not-live"
    )


def item(
    sku: str = "A", stock: Any = 10, *, item_id: str | None = None, **extra: Any
) -> dict[str, Any]:
    return {
        "item_id": item_id or f"id-{sku}",
        "sku": sku,
        "stock_on_hand": stock,
        "rate": 10,
        "status": "active",
        **extra,
    }


def page(
    items: list[dict[str, Any]], more: bool = False, **extra: Any
) -> dict[str, Any]:
    return {"code": 0, "items": items, "page_context": {"has_more_page": more}, **extra}


async def seed(
    redis: Redis,
    rows: list[dict[str, Any]] | None = None,
    *,
    age: float = 0,
    evidence: str = "synthetic-coverage-not-live",
) -> StockState:
    rows = rows if rows is not None else [item("A", 10), item("B", 5)]
    at = time.time() - age
    state = StockState(
        items={row["item_id"]: row for row in rows},
        observed={row["item_id"]: at for row in rows},
        coverage=at,
        full_at=at,
        coverage_evidence=evidence,
    )
    await redis.set(STATE_KEY, state.to_json(), ex=172800)
    return state


def client_with_transport(redis: Redis, handler: Any) -> ZohoInventoryClient:
    client = ZohoInventoryClient(redis)
    # Close the unused pool via its lifetime below; both clients have no open
    # sockets yet. The sole HTTP transport accepts synthetic requests only.
    client.client = httpx.AsyncClient(
        base_url="https://inventory.invalid", transport=httpx.MockTransport(handler)
    )
    return client
