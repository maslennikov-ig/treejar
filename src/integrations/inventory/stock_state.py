"""Versioned stock generations and Redis fencing; no catalog/database writes."""

from __future__ import annotations

import json
import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)

STATE_KEY = "zoho:inventory:stock_state:v2"
LOCK_KEY = "zoho:inventory:stock_snapshot:lock"
LEGACY_KEY = "zoho:inventory:stock_snapshot:v1"
RETENTION_SECONDS = 172800
LEASE_SECONDS = 120

# Redis executes these comparisons and publication as one operation. A changed
# raw generation (including a fresh critical read) invalidates a syncing writer.
COMMIT_SCRIPT = """-- stock-generation-commit
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
if (redis.call('GET', KEYS[2]) or '') ~= ARGV[2] then return 0 end
redis.call('SET', KEYS[2], ARGV[3], 'EX', ARGV[5])
if ARGV[4] ~= '' then redis.call('SET', KEYS[3], ARGV[4], 'EX', ARGV[5]) end
return 1
"""
FRESH_COMMIT_SCRIPT = """-- stock-fresh-commit
if (redis.call('GET', KEYS[1]) or '') ~= ARGV[1] then return 0 end
redis.call('SET', KEYS[1], ARGV[2], 'EX', ARGV[3])
return 1
"""
RENEW_SCRIPT = """-- stock-lease-renew
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('EXPIRE', KEYS[1], ARGV[2])
"""
RELEASE_SCRIPT = """-- stock-lease-release
if redis.call('GET', KEYS[1]) ~= ARGV[1] then return 0 end
return redis.call('DEL', KEYS[1])
"""
COOLDOWN_SCRIPT = """-- stock-cooldown-max
local deadline = math.max(tonumber(redis.call('GET', KEYS[1])) or 0, tonumber(ARGV[1]))
redis.call('SET', KEYS[1], tostring(deadline), 'EX', math.max(1, math.ceil(deadline - tonumber(ARGV[2]))))
return tostring(deadline)
"""


def raw_text(raw: Any) -> str:
    return (
        raw.decode("utf-8")
        if isinstance(raw, bytes)
        else raw
        if isinstance(raw, str)
        else ""
    )


def timestamp(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value) if math.isfinite(value) and value > 0 else None


@dataclass
class StockState:
    items: dict[str, dict[str, Any]] = field(default_factory=dict)
    observed: dict[str, float] = field(default_factory=dict)
    generation: str = field(default_factory=lambda: uuid.uuid4().hex)
    coverage: float | None = None
    full_at: float | None = None
    delta_at: float | None = None
    coverage_evidence: str = ""

    def to_json(self) -> str:
        return json.dumps(
            {
                "version": 2,
                "generation": self.generation,
                "items": self.items,
                "observed": self.observed,
                "coverage": self.coverage,
                "full_at": self.full_at,
                "delta_at": self.delta_at,
                "coverage_evidence": self.coverage_evidence,
            },
            allow_nan=False,
        )

    @classmethod
    def from_raw(cls, raw: Any) -> StockState | None:
        try:
            data = json.loads(raw_text(raw))
            if not isinstance(data, dict) or data.get("version") != 2:
                return None
            items, observed = data["items"], data["observed"]
            if not isinstance(items, dict) or not isinstance(observed, dict):
                return None
            if not isinstance(data.get("generation"), str) or not data["generation"]:
                return None
            for item_id, item in items.items():
                if not isinstance(item, dict) or item.get("item_id") != item_id:
                    return None
                if (
                    not isinstance(item.get("sku"), str)
                    or timestamp(observed.get(item_id)) is None
                ):
                    return None
            for name in ("coverage", "full_at", "delta_at"):
                if data.get(name) is not None and timestamp(data[name]) is None:
                    return None
            if not isinstance(data.get("coverage_evidence", ""), str):
                return None
            return cls(
                **{
                    k: data[k]
                    for k in (
                        "items",
                        "observed",
                        "generation",
                        "coverage",
                        "full_at",
                        "delta_at",
                        "coverage_evidence",
                    )
                }
            )
        except (ValueError, TypeError, KeyError, UnicodeError):
            return None

    def stock_items(self, evidence: str = "") -> dict[str, dict[str, Any]]:
        covered_at = self.full_at or 0.0
        if evidence and self.coverage_evidence == evidence:
            covered_at = self.coverage or covered_at
        result: dict[str, dict[str, Any]] = {}
        for item_id, row in self.items.items():
            if row.get("status", "active") != "active" or not row["sku"].strip():
                continue
            as_of = max(self.observed[item_id], covered_at)
            result[item_id] = {
                **row,
                "stock_as_of": datetime.fromtimestamp(as_of, UTC).isoformat(),
            }
        return result


class StockStore:
    def __init__(self, redis: Any) -> None:
        self.redis = redis

    async def read(self) -> tuple[StockState | None, str]:
        raw = raw_text(await self.redis.get(STATE_KEY))
        return StockState.from_raw(raw), raw

    async def acquire(self) -> str | None:
        owner = uuid.uuid4().hex
        return (
            owner
            if await self.redis.set(LOCK_KEY, owner, ex=LEASE_SECONDS, nx=True)
            else None
        )

    async def renew(self, owner: str) -> None:
        if await self.redis.eval(RENEW_SCRIPT, 1, LOCK_KEY, owner, LEASE_SECONDS) != 1:
            raise RuntimeError("Stock sync lease lost")

    async def release(self, owner: str) -> None:
        await self.redis.eval(RELEASE_SCRIPT, 1, LOCK_KEY, owner)

    async def commit(
        self, owner: str, raw: str, state: StockState, legacy: str = ""
    ) -> bool:
        return bool(
            await self.redis.eval(
                COMMIT_SCRIPT,
                3,
                LOCK_KEY,
                STATE_KEY,
                LEGACY_KEY,
                owner,
                raw,
                state.to_json(),
                legacy,
                RETENTION_SECONDS,
            )
            == 1
        )

    async def update_fresh(self, rows: list[tuple[dict[str, Any], float]]) -> bool:
        # A critical read need not wait behind a full download. CAS changes its
        # generation, so that download must restart instead of overwriting it.
        for _ in range(3):
            state, raw = await self.read()
            state = state or StockState()
            for row, observed_at in rows:
                item_id = row["item_id"]
                if state.observed.get(item_id, 0) <= observed_at:
                    state.items[item_id] = row
                    state.observed[item_id] = observed_at
            state.generation = uuid.uuid4().hex
            if (
                await self.redis.eval(
                    FRESH_COMMIT_SCRIPT,
                    1,
                    STATE_KEY,
                    raw,
                    state.to_json(),
                    RETENTION_SECONDS,
                )
                == 1
            ):
                return True
        return False


class StockMetrics:
    """Shared one-second counters, retained seven days; UTC [start, end)."""

    def __init__(self, redis: Any) -> None:
        self.redis = redis

    async def record(
        self,
        event: str,
        operation: str,
        status: str,
        *,
        count: int = 1,
        detail: str = "unknown",
    ) -> None:
        now = int(time.time())
        day = datetime.fromtimestamp(now, UTC).strftime("%Y-%m-%d")
        key = f"zoho:inventory:metrics:v1:{day}"
        try:
            await self.redis.hincrby(
                key, f"{now}|{event}|{operation}|{status}|{detail}", count
            )
            await self.redis.expire(key, 7 * 86400)
        except Exception as exc:
            # Metrics failure never authorizes using an incomplete stock read.
            logger.warning("Inventory counter unavailable error=%s", type(exc).__name__)

    async def report(self, start: int, end: int) -> dict[str, int]:
        if end <= start or end - start > 7 * 86400:
            raise ValueError("Choose an explicit interval of up to seven days")
        result: dict[str, int] = {}
        for midnight in range(start - start % 86400, end, 86400):
            day = datetime.fromtimestamp(midnight, UTC).strftime("%Y-%m-%d")
            values = await self.redis.hgetall(f"zoho:inventory:metrics:v1:{day}")
            for raw_field, value in values.items():
                second, field = raw_text(raw_field).split("|", 1)
                if start <= int(second) < end:
                    result[field] = result.get(field, 0) + int(value)
        return result
