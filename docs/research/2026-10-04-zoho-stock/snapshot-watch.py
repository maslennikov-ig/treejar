"""Bounded read-only comparison of natural stock changes; never enables delta.

Keep snapshots/IDs/token in app memory. Redis GET only, no OAuth/refresh/write.
No Inventory HTTP until an observed quantity changes between full snapshots.
Then <=16 GETs, no retry, cooldown/401/429 stops, one selected-item confirmation.
Stop after the first comparison or <=24h. Only anonymous evidence on stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import time
from datetime import UTC, datetime

import httpx
from redis.asyncio import Redis

from src.integrations.inventory.stock_state import STATE_KEY, StockState

EXPECTED_ORG = "544f8528f9db448a"
API = "https://www.zohoapis.eu/inventory/v1"


def number(value):
    return (
        float(value)
        if isinstance(value, (float, int))
        and not isinstance(value, bool)
        and math.isfinite(value)
        else None
    )


def utc(value):
    return datetime.fromtimestamp(value, UTC).isoformat()


def emit(event):
    print(json.dumps(event, allow_nan=False), flush=True)


def quantities(state):
    return {
        item_id: quantity
        for item_id, row in state.items.items()
        if (quantity := number(row.get("stock_on_hand"))) is not None
    }


def changes(before, after):
    old, new = quantities(before), quantities(after)
    return {
        item_id: (old[item_id], new[item_id])
        for item_id in old.keys() & new.keys()
        if old[item_id] != new[item_id]
    }


async def compare(redis, org, before, after, changed):
    result = {
        "inventory_gets": 0,
        "oauth_exchanges": 0,
        "provider_coverage_verified": False,
        "delta_complete": False,
        "stock_source": "two_published_full_snapshots",
        "operation_types_verified": False,
        "before_full_utc": utc(before.full_at),
        "after_full_utc": utc(after.full_at),
        "changed_quantities": len(changed),
    }
    boundary = before.full_at - 120
    result["delta_boundary_utc"] = utc(boundary)
    token = await redis.get("zoho:access_token")
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        result["stopped"] = "cached_token_missing_no_oauth"
        return result
    records = {}
    async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:

        async def get(path, params):
            cooldown = await redis.get("zoho:inventory:rate_limited_until")
            if cooldown and float(cooldown) > time.time():
                result["stopped"] = "active_cooldown_no_request"
                return None
            if result["inventory_gets"] >= 16:
                result["stopped"] = "request_cap_incomplete"
                return None
            result["inventory_gets"] += 1
            response = await client.get(
                API + path,
                params={"organization_id": org, **params},
                headers={"Authorization": "Zoho-oauthtoken " + token},
            )
            result.setdefault("http_statuses", []).append(response.status_code)
            if response.status_code != 200:
                result["stopped"] = "provider_unavailable_no_retry"
                return None
            data = response.json()
            if not isinstance(data, dict) or data.get("code") != 0:
                result["stopped"] = "invalid_provider_payload"
                return None
            return data

        # Reserve one GET for the current selected item; never widen the cap.
        for page in range(1, 16):
            data = await get(
                "/items",
                {
                    "page": page,
                    "per_page": 200,
                    "last_modified_time": datetime.fromtimestamp(
                        boundary, UTC
                    ).strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "sort_column": "last_modified_time",
                    "sort_order": "A",
                },
            )
            if data is None:
                return result
            rows, context = data.get("items"), data.get("page_context")
            if (
                not isinstance(rows, list)
                or not isinstance(context, dict)
                or not isinstance(context.get("has_more_page"), bool)
                or context.get("page", page) != page
            ):
                result["stopped"] = "invalid_delta_page_incomplete"
                return result
            for row in rows:
                if not isinstance(row, dict):
                    result["stopped"] = "invalid_delta_identity_incomplete"
                    return result
                item_id = row.get("item_id")
                if (
                    not isinstance(item_id, str)
                    or not item_id.isdigit()
                    or len(item_id) > 32
                    or item_id in records
                ):
                    result["stopped"] = "invalid_or_repeated_delta_identity"
                    return result
                records[item_id] = row
            if not context["has_more_page"]:
                result["delta_complete"] = True
                break
        if not result["delta_complete"]:
            result["stopped"] = "page_cap_incomplete"
            return result
        result["delta_rows"] = len(records)
        result["changed_in_delta"] = sum(item_id in records for item_id in changed)
        result["changed_absent_from_complete_delta"] = sum(
            item_id not in records for item_id in changed
        )
        selected = sorted(changed)[0]
        if not selected.isdigit() or len(selected) > 32:
            result["stopped"] = "invalid_selected_identity"
            return result
        current = await get("/items/" + selected, {})
        if current is None:
            return result
        item = current.get("item")
        if not isinstance(item, dict) or item.get("item_id") != selected:
            result["stopped"] = "selected_identity_mismatch"
            return result
        current_quantity = number(item.get("stock_on_hand"))
        old_quantity, new_quantity = changed[selected]
        result["selected_observation"] = {
            "identity_fingerprint": hashlib.sha256(
                (org + ":" + selected).encode()
            ).hexdigest()[:16],
            "before_quantity": old_quantity,
            "after_quantity": new_quantity,
            "current_http_quantity": current_quantity,
            "current_matches_after": current_quantity == new_quantity,
            "in_delta": selected in records,
            "before_observed_utc": utc(before.observed[selected]),
            "after_observed_utc": utc(after.observed[selected]),
        }
        result["stopped"] = "comparison_complete_coverage_not_certified"
        return result


async def watch(duration=86400, interval=60):
    if not 60 <= duration <= 86400 or not 30 <= interval <= 300:
        raise ValueError("out_of_bounds_observation")
    redis = Redis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"),
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    started = time.monotonic()
    baseline = None
    read_count = 0
    observed_fulls = 0
    try:
        org = os.environ.get("ZOHO_INVENTORY_ORG_ID", "")
        if hashlib.sha256(org.encode()).hexdigest()[:16] != EXPECTED_ORG:
            emit({"event": "stopped", "reason": "unexpected_organization_no_read"})
            return
        emit(
            {
                "event": "started",
                "at_utc": utc(time.time()),
                "deadline_utc": utc(time.time() + duration),
                "read_only": True,
                "max_duration_seconds": duration,
                "interval_seconds": interval,
                "max_inventory_gets": 16,
                "oauth_exchanges": 0,
                "redis_writes": 0,
                "provider_coverage_verified": False,
            }
        )
        while time.monotonic() - started < duration:
            read_count += 1
            state = StockState.from_raw(await redis.get(STATE_KEY))
            if (
                state is None
                or state.full_at is None
                or state.delta_at is not None
                or state.coverage != state.full_at
                or state.coverage_evidence
                or not 0 <= time.time() - state.full_at <= 600
            ):
                if baseline is not None:
                    emit({"event": "stopped", "reason": "full_source_unusable"})
                    return
            elif baseline is None:
                if not quantities(state):
                    emit({"event": "stopped", "reason": "no_numeric_stock_baseline"})
                    return
                baseline = state
                observed_fulls = 1
                emit(
                    {
                        "event": "baseline",
                        "full_utc": utc(state.full_at),
                        "numeric_stock_rows": len(quantities(state)),
                    }
                )
            elif state.full_at > baseline.full_at:
                observed_fulls += 1
                changed = changes(baseline, state)
                emit(
                    {
                        "event": "full_snapshot_compared",
                        "full_utc": utc(state.full_at),
                        "changed_quantities": len(changed),
                        "added_rows": len(state.items.keys() - baseline.items.keys()),
                        "removed_rows": len(baseline.items.keys() - state.items.keys()),
                        "inventory_gets": 0,
                    }
                )
                if changed:
                    emit(
                        {
                            "event": "quantity_change_comparison",
                            "at_utc": utc(time.time()),
                            **await compare(redis, org, baseline, state, changed),
                        }
                    )
                    return
                baseline = state
            elif state.full_at < baseline.full_at:
                emit({"event": "stopped", "reason": "full_source_rewound"})
                return
            remaining = duration - (time.monotonic() - started)
            if remaining <= 0:
                break
            await asyncio.sleep(min(interval, remaining))
        emit(
            {
                "event": "stopped",
                "reason": "deadline_no_observed_quantity_change",
                "full_snapshots": observed_fulls,
                "redis_snapshot_reads": read_count,
                "inventory_gets": 0,
                "provider_coverage_verified": False,
            }
        )
    except Exception as exc:
        emit(
            {
                "event": "stopped",
                "reason": "unavailable",
                "error_type": type(exc).__name__,
            }
        )
    finally:
        await redis.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration-seconds", type=int, default=86400)
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    try:
        asyncio.run(watch(args.duration_seconds, args.interval_seconds))
    except Exception as exc:
        emit(
            {
                "event": "stopped",
                "reason": "unavailable",
                "error_type": type(exc).__name__,
            }
        )
