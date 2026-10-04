"""Offline observer regressions; all Redis/provider transport intercepted."""

import asyncio
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from src.integrations.inventory.stock_state import STATE_KEY, StockState

spec = importlib.util.spec_from_file_location(
    "stock_watch", Path(__file__).with_name("snapshot-watch.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_client = httpx.AsyncClient


def state(full_at, quantity):
    return StockState(
        items={
            "101": {
                "item_id": "101",
                "sku": "offline-secret-sku",
                "stock_on_hand": quantity,
            },
            "202": {"item_id": "202", "sku": "offline-other-sku", "stock_on_hand": 4},
        },
        observed={"101": full_at, "202": full_at},
        full_at=full_at,
        coverage=full_at,
    ).to_json()


async def check(case):
    events, requests = [], []
    snapshots = [state(900, True if case == "unknown" else 10), state(1000, 2)]
    if case == "unchanged":
        snapshots[1] = state(1000, 10)
    if case == "rewound":
        snapshots[1] = state(800, 2)
    clock = SimpleNamespace(elapsed=0)

    async def sleep(seconds):
        clock.elapsed += seconds

    class ReadOnlyRedis:
        def __init__(self):
            self.reads = 0

        @classmethod
        def from_url(cls, *args, **kwargs):
            return cls()

        async def get(self, key):
            assert key in (
                STATE_KEY,
                "zoho:access_token",
                "zoho:inventory:rate_limited_until",
            )
            if key == STATE_KEY:
                value = snapshots[min(self.reads, len(snapshots) - 1)]
                self.reads += 1
                return value
            if key == "zoho:access_token":
                return "offline-cached-secret-token"
            return "9999999999" if case == "cooldown" else None

        async def aclose(self):
            pass

    def handler(request):
        requests.append(request)
        assert request.method == "GET"
        assert request.url.host == "www.zohoapis.eu"
        assert (
            request.headers["Authorization"]
            == "Zoho-oauthtoken offline-cached-secret-token"
        )
        if case in ("401", "429"):
            return httpx.Response(int(case), json={"code": 57})
        if request.url.path == "/inventory/v1/items/101":
            return httpx.Response(
                200,
                json={
                    "code": 0,
                    "item": {
                        "item_id": "999" if case == "wrong_item" else "101",
                        "stock_on_hand": 3 if case == "moved_again" else 2,
                    },
                },
            )
        assert request.url.path == "/inventory/v1/items"
        assert request.url.params["last_modified_time"] == "1970-01-01T00:13:00+0000"
        page = int(request.url.params["page"])
        if case == "page_cap":
            rows, more = [{"item_id": str(700 + page)}], True
        elif case == "missing":
            rows, more = [{"item_id": "202"}], False
        elif case == "repeated":
            rows, more = [{"item_id": "101"}], page == 1
        else:
            rows, more = [{"item_id": "101" if page == 1 else "202"}], page == 1
        payload = {
            "code": 0,
            "items": rows,
            "page_context": {"page": page, "has_more_page": more},
        }
        if case == "bad_context":
            payload.pop("page_context")
        return httpx.Response(200, json=payload)

    def factory(**kwargs):
        return original_client(**kwargs, transport=httpx.MockTransport(handler))

    with (
        patch.object(module, "Redis", ReadOnlyRedis),
        patch.object(module, "emit", events.append),
        patch.object(
            module,
            "time",
            SimpleNamespace(
                time=lambda: 1000 + clock.elapsed, monotonic=lambda: clock.elapsed
            ),
        ),
        patch.object(module.asyncio, "sleep", sleep),
        patch.object(module.httpx, "AsyncClient", factory),
        patch.object(
            module, "EXPECTED_ORG", hashlib.sha256(b"offline-org").hexdigest()[:16]
        ),
        patch.dict(os.environ, {"ZOHO_INVENTORY_ORG_ID": "offline-org"}),
    ):
        await module.watch(60, 30)
    serialized = json.dumps(events)
    assert "offline-cached-secret-token" not in serialized
    assert "offline-secret-sku" not in serialized
    assert '"item_id":' not in serialized and '"101"' not in serialized
    assert len(requests) <= 16
    if case in ("unchanged", "unknown", "rewound"):
        assert not requests
        assert events[-1]["event"] == "stopped"
    else:
        result = events[-1]
        assert result["event"] == "quantity_change_comparison"
        assert (
            result["provider_coverage_verified"]
            is result["operation_types_verified"]
            is False
        )
        assert result["oauth_exchanges"] == 0
        assert result["inventory_gets"] == len(requests)
        if case == "cooldown":
            assert not requests and result["stopped"] == "active_cooldown_no_request"
        elif case in ("401", "429", "bad_context"):
            assert len(requests) == 1
        elif case == "repeated":
            assert len(requests) == 2 and result["delta_complete"] is False
        elif case == "page_cap":
            assert len(requests) == 15 and result["delta_complete"] is False
        elif case == "wrong_item":
            assert result["stopped"] == "selected_identity_mismatch"
        else:
            selected = result["selected_observation"]
            assert selected["before_quantity"] == 10 and selected["after_quantity"] == 2
            assert result["delta_complete"] is True
            assert selected["in_delta"] is (case != "missing")
            assert selected["current_matches_after"] is (case != "moved_again")
    return {"case": case, "passed": True, "inventory_gets": len(requests)}


async def main():
    results = []
    for case in (
        "unchanged",
        "unknown",
        "rewound",
        "success",
        "missing",
        "401",
        "429",
        "cooldown",
        "bad_context",
        "repeated",
        "page_cap",
        "wrong_item",
        "moved_again",
    ):
        results.append(await check(case))
    print(
        json.dumps(
            {
                "evidence_kind": "offline_transport_interception",
                "provider_live_proof": False,
                "cases": results,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
