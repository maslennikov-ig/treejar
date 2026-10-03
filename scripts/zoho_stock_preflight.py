"""Bounded cached-token GET diagnostic. Never refresh OAuth or write Redis/business data.

Run candidate code through stdin in the existing app container:
  ssh noor-server 'cd /opt/noor && docker compose exec -T app python -' < scripts/zoho_stock_preflight.py
Default maximum: 6 Inventory GETs, concurrency 1. Stops on 401/429, any malformed
response or incomplete identity/stock result. Output contains counts only.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import math
import os
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from redis.asyncio import Redis


async def preflight(*, delta_only: bool = False) -> dict[str, Any]:
    # Environment is read inside the existing container; no credential is
    # returned, printed or put in shell arguments.
    redis = Redis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    result: dict[str, Any] = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "read_only": True,
        "requests": [],
        "provider_coverage_verified": False,
        "bulk_numeric_verified_size": 0,
    }
    try:
        cooldown = await redis.get("zoho:inventory:rate_limited_until")
        if cooldown and float(cooldown) > time.time():
            result["stopped"] = "active_cooldown"
            result["cooldown_remaining_seconds"] = math.ceil(
                float(cooldown) - time.time()
            )
            return result
        token = await redis.get("zoho:access_token")
        if not token:
            result["stopped"] = "cached_token_absent_no_refresh"
            return result
        org = os.environ.get("ZOHO_INVENTORY_ORG_ID", "")
        if not org:
            result["stopped"] = "organization_absent"
            return result
        result["organization_fingerprint"] = hashlib.sha256(org.encode()).hexdigest()[
            :16
        ]
        base = os.environ.get(
            "ZOHO_INVENTORY_API_URL", "https://www.zohoapis.eu/inventory/v1"
        )
        async with httpx.AsyncClient(
            base_url=base, timeout=8, follow_redirects=False
        ) as client:

            async def get(
                path: str, params: dict[str, Any], label: str
            ) -> dict[str, Any] | None:
                # Re-read the shared cooldown before every probe, including a
                # refusal from a concurrently running app/worker.
                raw = await redis.get("zoho:inventory:rate_limited_until")
                if raw and float(raw) > time.time():
                    result["stopped"] = "active_cooldown"
                    return None
                response = await client.get(
                    path,
                    params={**params, "organization_id": org},
                    headers={"Authorization": f"Zoho-oauthtoken {token}"},
                )
                entry: dict[str, Any] = {
                    "operation": label,
                    "status": response.status_code,
                }
                result["requests"].append(entry)
                if response.status_code in (401, 429):
                    result["stopped"] = (
                        f"http_{response.status_code}_no_refresh_or_retry"
                    )
                    return None
                if response.status_code != 200:
                    with contextlib.suppress(ValueError, TypeError):
                        error = response.json()
                        entry["provider_code"] = error.get("code")
                        message = str(error.get("message", "")).lower()
                        entry["error_parameter"] = next(
                            (
                                name
                                for name in (
                                    "last_modified_time",
                                    "sort_column",
                                    "sort_order",
                                    "item_ids",
                                    "per_page",
                                )
                                if name in message
                            ),
                            "unknown",
                        )
                    result["stopped"] = "provider_interface_unavailable"
                    return None
                data = response.json()
                if (
                    not isinstance(data, dict)
                    or data.get("code", 0) != 0
                    or not isinstance(data.get("items"), list)
                ):
                    result["stopped"] = "malformed_or_error_response"
                    return None
                entry["items"] = len(data["items"])
                entry["numeric_top_level_stock"] = sum(
                    numeric(row.get("stock_on_hand"))
                    for row in data["items"]
                    if isinstance(row, dict)
                )
                context = data.get("page_context")
                entry["has_valid_page_context"] = isinstance(
                    context, dict
                ) and isinstance(context.get("has_more_page"), bool)
                return data

            ids = []
            if not delta_only:
                listed = await get(
                    "/items",
                    {"page": 1, "per_page": 8, "status": "active"},
                    "list_sample",
                )
                if listed is None:
                    return result
                ids = [
                    row["item_id"]
                    for row in listed["items"]
                    if isinstance(row, dict) and isinstance(row.get("item_id"), str)
                ]
                if not ids:
                    result["stopped"] = "sample_no_valid_ids"
                    return result
            boundary = (datetime.now(UTC) - timedelta(hours=1)).strftime(
                "%Y-%m-%dT%H:%M:%S%z"
            )
            if (
                await get(
                    "/items",
                    {
                        "last_modified_time": boundary,
                        "sort_column": "last_modified_time",
                        "sort_order": "A",
                        "page": 1,
                        "per_page": 3,
                    },
                    "delta_interface_sorted_offset",
                )
                is None
            ):
                return result
            if delta_only:
                result["stopped"] = "sorted_delta_interface_verified_coverage_unproved"
                return result
            for size in (1, 2, 4, 8):
                if size > len(ids):
                    break
                batch = ids[:size]
                data = await get(
                    "/itemdetails", {"item_ids": ",".join(batch)}, f"bulk_size_{size}"
                )
                if data is None:
                    return result
                rows = data["items"]
                valid = (
                    len(rows) == size
                    and {row.get("item_id") for row in rows if isinstance(row, dict)}
                    == set(batch)
                    and all(
                        isinstance(row, dict)
                        and isinstance(row.get("sku"), str)
                        and numeric(row.get("stock_on_hand"))
                        for row in rows
                    )
                )
                if not valid:
                    result["stopped"] = "bulk_identity_or_numeric_stock_incomplete"
                    return result
                result["bulk_numeric_verified_size"] = size
            result["stopped"] = (
                "bounded_interface_probe_complete_coverage_still_unproved"
            )
            return result
    except Exception as exc:
        result["stopped"] = "unavailable"
        result["error_type"] = type(exc).__name__
        return result
    finally:
        await redis.aclose()


def numeric(value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value))
    except (ValueError, TypeError):
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--delta-only", action="store_true", help="One sorted modified-since GET only"
    )
    args = parser.parse_args()
    print(json.dumps(asyncio.run(preflight(delta_only=args.delta_only)), indent=2))
