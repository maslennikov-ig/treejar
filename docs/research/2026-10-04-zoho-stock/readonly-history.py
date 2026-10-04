"""Read-only history availability diagnostic; never certifies stock coverage.

Run via stdin in the existing app container. At most 16 sequential cached-token
Inventory GETs; Redis GET only; no OAuth refresh, retries, configuration or data
writes. Payloads remain in memory. Output contains counts and valid dates only.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import time
from datetime import UTC, datetime, timedelta

import httpx
from redis.asyncio import Redis


def dates(rows, field):
    values = []
    for row in rows:
        raw = row.get(field)
        if not isinstance(raw, str):
            continue
        try:
            value = datetime.fromisoformat(raw)
        except ValueError:
            continue
        values.append(value.isoformat())
    return {
        "present": len(values),
        "min": min(values, default=None),
        "max": max(values, default=None),
    }


def summarize(rows):
    return {
        "rows": len(rows),
        "dates": {
            field: dates(rows, field)
            for field in ("date", "created_time", "last_modified_time")
        },
        "numeric_stock_rows": sum(
            isinstance(row.get("stock_on_hand"), (int, float))
            and not isinstance(row.get("stock_on_hand"), bool)
            and math.isfinite(row["stock_on_hand"])
            for row in rows
        ),
        "line_items_present": sum(
            isinstance(row.get("line_items"), list) for row in rows
        ),
    }


async def audit():
    redis = Redis.from_url(
        os.environ.get("REDIS_URL", "redis://redis:6379/0"), decode_responses=True
    )
    result = {
        "measured_at_utc": datetime.now(UTC).isoformat(),
        "read_only": True,
        "max_inventory_gets": 16,
        "requests": [],
        "provider_coverage_verified": False,
        "limitations": [
            "Bounded history samples are not complete histories.",
            "No before/after stock observations or causal operation proof.",
            "No item lifecycle operations were performed.",
        ],
    }
    try:
        token = await redis.get("zoho:access_token")
        org = os.environ.get("ZOHO_INVENTORY_ORG_ID", "")
        if not token or not org:
            result["stopped"] = "cached_token_or_org_absent_no_refresh"
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

            async def get(path, params, label):
                if "stopped" in result:
                    return None
                cooldown = await redis.get("zoho:inventory:rate_limited_until")
                if cooldown and float(cooldown) > time.time():
                    result["stopped"] = "active_cooldown"
                    return None
                if len(result["requests"]) >= 16:
                    result["stopped"] = "request_cap"
                    return None
                entry = {"operation": label}
                result["requests"].append(entry)
                response = await client.get(
                    path,
                    params={**params, "organization_id": org},
                    headers={"Authorization": f"Zoho-oauthtoken {token}"},
                )
                entry["status"] = response.status_code
                if response.status_code in (401, 429):
                    result["stopped"] = (
                        f"http_{response.status_code}_no_refresh_or_retry"
                    )
                    return None
                if response.status_code != 200:
                    entry["evidence"] = "endpoint_unavailable_no_access_expansion"
                    return None
                data = response.json()
                if not isinstance(data, dict) or data.get("code") != 0:
                    result["stopped"] = "malformed_or_provider_error"
                    return None
                return data

            latest = await get(
                "/items",
                {
                    "page": 1,
                    "per_page": 3,
                    "sort_column": "last_modified_time",
                    "sort_order": "D",
                },
                "recent_item_metadata_sample",
            )
            if latest is not None and isinstance(latest.get("items"), list):
                result["recent_item_metadata_sample"] = summarize(latest["items"])
            boundary = (datetime.now(UTC) - timedelta(days=1)).strftime(
                "%Y-%m-%dT%H:%M:%S%z"
            )
            result["delta_boundary_utc"] = boundary
            delta_ids = set()
            for page in range(1, 4):
                data = await get(
                    "/items",
                    {
                        "page": page,
                        "per_page": 3,
                        "last_modified_time": boundary,
                        "sort_column": "last_modified_time",
                        "sort_order": "A",
                    },
                    f"last24h_delta_page_{page}",
                )
                if data is None:
                    break
                rows, context = data.get("items"), data.get("page_context")
                if not isinstance(rows, list) or not all(
                    isinstance(row, dict) for row in rows
                ):
                    result["stopped"] = "malformed_items"
                    break
                result["requests"][-1]["summary"] = summarize(rows)
                delta_ids.update(
                    row.get("item_id") for row in rows if row.get("item_id")
                )
                if not isinstance(context, dict) or not isinstance(
                    context.get("has_more_page"), bool
                ):
                    result["stopped"] = "malformed_delta_page_context"
                    break
                if not context["has_more_page"]:
                    result["delta_list_complete"] = True
                    break
            result["delta_distinct_items"] = len(delta_ids)
            if "delta_list_complete" not in result:
                result["delta_list_complete"] = False

            resources = (
                (
                    "inventoryadjustments",
                    "inventory_adjustments",
                    "inventory_adjustment_id",
                    "inventory_adjustment",
                ),
                (
                    "purchasereceives",
                    "purchasereceives",
                    "receive_id",
                    "purchasereceive",
                ),
                ("salesreturns", "salesreturns", "salesreturn_id", "salesreturn"),
                (
                    "transferorders",
                    "transfer_orders",
                    "transfer_order_id",
                    "transfer_order",
                ),
                ("packages", "package", "package_id", "package"),
            )
            for path, list_key, id_key, detail_key in resources:
                data = await get(
                    "/" + path, {"page": 1, "per_page": 3}, path + "_sample"
                )
                if data is None:
                    continue
                rows = data.get(list_key)
                if not isinstance(rows, list) or not all(
                    isinstance(row, dict) for row in rows
                ):
                    result[path] = {
                        "evidence": "unexpected_list_shape_no_empty_inference"
                    }
                    continue
                result[path] = summarize(rows)
                if rows and str(rows[0].get(id_key, "")).isdigit():
                    detail = await get(
                        "/" + path + "/" + str(rows[0][id_key]),
                        {},
                        path + "_detail_sample",
                    )
                    if detail is not None and isinstance(detail.get(detail_key), dict):
                        result[path]["detail_sample"] = summarize([detail[detail_key]])
            result.setdefault(
                "stopped", "bounded_readonly_history_check_complete_coverage_unproved"
            )
            return result
    except Exception as exc:
        result["stopped"] = "unavailable"
        result["error_type"] = type(exc).__name__
        return result
    finally:
        await redis.aclose()


if __name__ == "__main__":
    print(json.dumps(asyncio.run(audit()), indent=2))
