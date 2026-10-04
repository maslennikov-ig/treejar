"""Offline safety checks; no provider or Redis connection, no live proof."""

import asyncio
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "audit_under_test", ROOT / "readonly-history.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_client = httpx.AsyncClient


async def check(*, status=200, cooldown=False, malformed=False, many=False):
    sent = []

    class ReadonlyRedis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def get(self, key):
            assert key in {"zoho:access_token", "zoho:inventory:rate_limited_until"}
            if key == "zoho:access_token":
                return "do-not-emit-secret"
            return "9999999999" if cooldown else None

        async def aclose(self):
            pass

    def handler(request):
        assert request.method == "GET"
        sent.append(request)
        if status != 200:
            return httpx.Response(status, json={"code": 57})
        if malformed:
            return httpx.Response(200, json={"code": 0, "items": False})
        if request.url.path.endswith("/items"):
            rows = (
                [{"item_id": "123", "sku": "do-not-emit-sku", "stock_on_hand": 2}]
                if many
                else []
            )
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "items": rows,
                    "page_context": {"page": 1, "has_more_page": many},
                },
            )
        keys = {
            "inventoryadjustments": "inventory_adjustments",
            "purchasereceives": "purchasereceives",
            "salesreturns": "salesreturns",
            "transferorders": "transfer_orders",
            "packages": "package",
        }
        return httpx.Response(
            200, json={"code": 0, keys[request.url.path.rsplit("/", 1)[-1]]: []}
        )

    def client(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(handler))

    with (
        patch.object(module, "Redis", ReadonlyRedis),
        patch.object(module.httpx, "AsyncClient", client),
        patch.dict(os.environ, {"ZOHO_INVENTORY_ORG_ID": "do-not-emit-org"}),
    ):
        result = await module.audit()
    assert len(sent) == len(result["requests"]) <= 16
    assert result["provider_coverage_verified"] is False
    assert all(
        secret not in json.dumps(result)
        for secret in (
            "do-not-emit-secret",
            "do-not-emit-sku",
            "do-not-emit-org",
            "123",
        )
    )
    if status in (401, 429):
        assert (
            len(sent) == 1 and result["stopped"] == f"http_{status}_no_refresh_or_retry"
        )
    if cooldown:
        assert len(sent) == 0 and result["stopped"] == "active_cooldown"
    if malformed:
        assert len(sent) == 2 and result["stopped"] == "malformed_items"
    if many:
        assert not result["delta_list_complete"] and len(sent) == 9
    if status == 200 and not cooldown and not malformed and not many:
        assert len(sent) == 7 and result["delta_list_complete"]
    return {
        "status": status,
        "cooldown": cooldown,
        "malformed": malformed,
        "page_cap": many,
        "sent_gets": len(sent),
        "passed": True,
    }


async def main():
    results = []
    for args in (
        {},
        {"status": 401},
        {"status": 429},
        {"cooldown": True},
        {"malformed": True},
        {"many": True},
    ):
        results.append(await check(**args))
    receipt = {
        "evidence_kind": "offline_http_and_redis_interception",
        "provider_live_proof": False,
        "cases": results,
    }
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
