"""Read shared Inventory counters for an explicit UTC [start, end) interval."""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from redis.asyncio import Redis

from src.core.config import settings
from src.integrations.inventory.stock_state import StockMetrics, StockStore


def utc_second(value: str) -> int:
    at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if at.tzinfo is None or at.microsecond:
        raise argparse.ArgumentTypeError("Use an aware timestamp with whole seconds")
    return int(at.timestamp())


async def report(start: int, end: int) -> dict:
    redis = Redis.from_url(str(settings.redis_url), decode_responses=True)
    try:
        counters = await StockMetrics(redis).report(start, end)
        state, _ = await StockStore(redis).read()
        return {
            "window_start_utc": datetime.fromtimestamp(start, UTC).isoformat(),
            "window_end_exclusive_utc": datetime.fromtimestamp(end, UTC).isoformat(),
            "window_start_moscow": datetime.fromtimestamp(
                start, ZoneInfo("Europe/Moscow")
            ).isoformat(),
            "window_end_exclusive_moscow": datetime.fromtimestamp(
                end, ZoneInfo("Europe/Moscow")
            ).isoformat(),
            "measurement_status": "counters_present"
            if counters
            else "no_counter_evidence",
            "http_attempts": sum(
                n for key, n in counters.items() if key.startswith("attempt|")
            )
            if counters
            else None,
            "counters": counters,
            "current_state": None
            if state is None
            else {
                "items": len(state.items),
                "coverage_age_seconds": time.time() - state.coverage
                if state.coverage
                else None,
                "last_full_utc": datetime.fromtimestamp(state.full_at, UTC).isoformat()
                if state.full_at
                else None,
                "last_delta_utc": datetime.fromtimestamp(
                    state.delta_at, UTC
                ).isoformat()
                if state.delta_at
                else None,
            },
            "limitations": [
                "Only Noor Inventory calls; outside account consumers and OAuth are excluded.",
                "Second precision; current state is read now, not reconstructed at the interval end.",
                "Counters expire after seven days; Redis/counter failure is a measurement gap, not zero account usage.",
            ],
        }
    finally:
        await redis.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, type=utc_second)
    parser.add_argument("--end", required=True, type=utc_second)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(report(args.start, args.end)), indent=2))
