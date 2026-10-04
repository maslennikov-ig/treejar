"""Offline transport/Redis guards; never live proof or an OAuth exchange."""

import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import httpx

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "self_client_probe", ROOT / "self-client-readonly-probe.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_client = httpx.AsyncClient


async def check(
    *,
    error=None,
    get_status=200,
    cooldown=False,
    later_cooldown=False,
    mismatched=False,
    history_sample=False,
    examine_adjustment=False,
    detail_status=200,
    wrong_detail_identity=False,
    wrong_item_identity=False,
    cooldown_after=None,
    **extra,
):
    sent = []

    class ReadOnlyRedis:
        def __init__(self):
            self.cooldown_reads = 0

        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def get(self, key):
            assert key in ("zoho:access_token", "zoho:inventory:rate_limited_until")
            if key == "zoho:access_token":
                return "original-cached-token-do-not-emit"
            self.cooldown_reads += 1
            return (
                "9999999999"
                if cooldown
                or later_cooldown
                and self.cooldown_reads > 1
                or cooldown_after is not None
                and self.cooldown_reads >= cooldown_after
                else None
            )

        async def aclose(self):
            pass

    def handler(request):
        sent.append(request)
        if request.method == "POST":
            assert request.url == "https://accounts.zoho.eu/oauth/v2/token"
            body = request.content.decode()
            assert "grant_type=client_credentials" in body
            assert (
                "grant_type=refresh_token" not in body
                and "authorization_code" not in body
            )
            assert "soid=ZohoInventory.offline-org" in body
            assert all(scope.endswith(".READ") for scope in module.SCOPES)
            if error:
                return httpx.Response(200, json={"error": error})
            return httpx.Response(
                200,
                json={
                    "access_token": "temporary-token-do-not-emit",
                    "expires_in": 3600,
                    "api_domain": "https://www.zohoapis.eu",
                    "scope": ",".join(module.SCOPES),
                    **extra,
                },
            )
        assert request.method == "GET"
        assert (
            request.headers["Authorization"]
            == "Zoho-oauthtoken temporary-token-do-not-emit"
        )
        if request.url.path == "/inventory/v1/inventoryadjustments/123":
            data = {
                "code": 0,
                "inventory_adjustment": {
                    "inventory_adjustment_id": "999"
                    if wrong_detail_identity
                    else "123",
                    "adjustment_type": "quantity",
                    "status": "adjusted",
                    "created_time": "2026-10-04T10:00:00+04:00",
                    "line_items": [{"item_id": "456", "quantity_adjusted": -2}],
                },
            }
            return httpx.Response(detail_status, json=data)
        if request.url.path == "/inventory/v1/items/456":
            data = {
                "code": 0,
                "item": {
                    "item_id": "999" if wrong_item_identity else "456",
                    "stock_on_hand": 8,
                    "last_modified_time": "2026-10-02T14:00:00+04:00",
                },
            }
        elif request.url.path == "/inventory/v1/items":
            data = {"code": 0, "items": [], "page_context": {"has_more_page": False}}
        else:
            keys = {
                "inventoryadjustments": "inventory_adjustments",
                "purchasereceives": "purchasereceives",
                "salesreturns": "salesreturns",
                "transferorders": "transfer_orders",
                "packages": "package",
            }
            data = {"code": 0, keys[request.url.path.rsplit("/", 1)[-1]]: []}
            if examine_adjustment and request.url.path.endswith(
                "/inventoryadjustments"
            ):
                data["inventory_adjustments"] = [{"inventory_adjustment_id": "123"}]
        return httpx.Response(get_status, json=data)

    def intercepted_client(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(handler))

    with (
        patch.object(module, "Redis", ReadOnlyRedis),
        patch.object(
            module, "EXPECTED_ORG", hashlib.sha256(b"offline-org").hexdigest()[:16]
        ),
        patch.object(
            module,
            "EXPECTED_CLIENT",
            "wrong"
            if mismatched
            else hashlib.sha256(b"offline-client").hexdigest()[:16],
        ),
        patch.dict(
            os.environ,
            {
                "ZOHO_INVENTORY_ORG_ID": "offline-org",
                "ZOHO_INVENTORY_CLIENT_ID": "offline-client",
                "ZOHO_INVENTORY_CLIENT_SECRET": "secret-do-not-emit",
            },
        ),
        patch.object(module.httpx, "AsyncClient", intercepted_client),
        patch("redis.asyncio.Redis", ReadOnlyRedis),
    ):
        result = await module.probe(
            (ROOT / "readonly-history.py").read_text() if history_sample else None,
            examine_adjustment=examine_adjustment,
        )
    assert result["redis_writes"] == result["oauth_refreshes"] == 0
    assert result["provider_coverage_verified"] is False
    assert len(sent) <= 17
    assert (
        sum(r.method == "POST" for r in sent) == result["oauth_exchange_attempts"] <= 1
    )
    assert sum(r.method == "GET" for r in sent) == result["inventory_gets"] <= 16
    assert not any(
        secret in json.dumps(result)
        for secret in (
            "secret-do-not-emit",
            "temporary-token-do-not-emit",
            "original-cached-token-do-not-emit",
        )
    )
    if cooldown or mismatched or history_sample and examine_adjustment:
        assert len(sent) == 0
    else:
        assert result["production_cached_token_unchanged"] is True
        if error or extra or later_cooldown:
            assert len(sent) == 1
        elif examine_adjustment:
            if cooldown_after == 3:
                assert len(sent) == 2
            elif detail_status != 200 or wrong_detail_identity or cooldown_after == 4:
                assert len(sent) == 3
            else:
                assert len(sent) == 4
                if not wrong_item_identity:
                    observation = result["adjustment_observation"]
                    assert observation["old_quantity_verified"] is False
                    assert observation["causal_stock_delta_coverage_verified"] is False
                    assert observation["current_stock_on_hand"] == 8
                    assert (
                        observation["created_time_utc"] == "2026-10-04T06:00:00+00:00"
                    )
                    assert '"item_id":' not in json.dumps(observation)
                    assert '"456"' not in json.dumps(observation)
                    assert '"123"' not in json.dumps(observation)
        elif history_sample:
            assert len(sent) == 9 and result["inventory_gets"] == 8
            assert result["history_read_verified"] is True
            assert result["history_audit"]["provider_coverage_verified"] is False
        else:
            assert len(sent) == 2 and result["inventory_status"] == get_status
    return {
        "passed": True,
        "posts": result["oauth_exchange_attempts"],
        "gets": result["inventory_gets"],
        "stopped": result["stopped"],
    }


async def main():
    cases = []
    for args in (
        {},
        {"get_status": 401},
        {"get_status": 429},
        {"cooldown": True},
        {"later_cooldown": True},
        {"mismatched": True},
        {"error": "invalid_scope"},
        {"error": "missing_org_info"},
        {"refresh_token": "forbidden-offline-grant"},
        {"api_domain": "https://other-host.invalid"},
        {"expires_in": True},
        {"scope": "ZohoInventory.FullAccess.all"},
        {"history_sample": True},
        {"examine_adjustment": True},
        {"examine_adjustment": True, "detail_status": 401},
        {"examine_adjustment": True, "detail_status": 429},
        {"examine_adjustment": True, "wrong_detail_identity": True},
        {"examine_adjustment": True, "wrong_item_identity": True},
        {"examine_adjustment": True, "cooldown_after": 3},
        {"examine_adjustment": True, "cooldown_after": 4},
        {"history_sample": True, "examine_adjustment": True},
    ):
        cases.append(await check(**args))
    print(
        json.dumps(
            {
                "evidence_kind": "offline_http_and_redis_interception",
                "provider_live_proof": False,
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
