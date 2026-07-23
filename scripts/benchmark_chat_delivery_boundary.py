#!/usr/bin/env python3
"""Measure the local scheduling boundary moved out of text-delivery latency.

This is a controlled timing harness. It does not call Noor dependencies and
must not be interpreted as live provider or production latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from statistics import median
from time import perf_counter
from typing import Any


async def _run_sample(
    *,
    summary_before_delivery: bool,
    model_ms: float,
    persist_ms: float,
    summary_ms: float,
    outbound_ms: float,
) -> float:
    started_at = perf_counter()
    await asyncio.sleep(model_ms / 1000.0)
    await asyncio.sleep(persist_ms / 1000.0)
    if summary_before_delivery:
        await asyncio.sleep(summary_ms / 1000.0)
    await asyncio.sleep(outbound_ms / 1000.0)
    delivered_at = perf_counter()
    if not summary_before_delivery:
        await asyncio.sleep(summary_ms / 1000.0)
    return (delivered_at - started_at) * 1000.0


async def _benchmark(args: argparse.Namespace) -> dict[str, Any]:
    legacy_samples: list[float] = []
    current_samples: list[float] = []
    for _ in range(args.samples):
        legacy_samples.append(
            await _run_sample(
                summary_before_delivery=True,
                model_ms=args.model_ms,
                persist_ms=args.persist_ms,
                summary_ms=args.summary_ms,
                outbound_ms=args.outbound_ms,
            )
        )
        current_samples.append(
            await _run_sample(
                summary_before_delivery=False,
                model_ms=args.model_ms,
                persist_ms=args.persist_ms,
                summary_ms=args.summary_ms,
                outbound_ms=args.outbound_ms,
            )
        )

    legacy_p50 = median(legacy_samples)
    current_p50 = median(current_samples)
    return {
        "evidence_kind": "controlled_local_scheduling_boundary",
        "samples_per_variant": args.samples,
        "configured_phase_ms": {
            "model": args.model_ms,
            "persist": args.persist_ms,
            "summary_refresh_enqueue": args.summary_ms,
            "outbound": args.outbound_ms,
        },
        "to_text_delivery_ms": {
            "legacy_summary_before_send_p50": round(legacy_p50, 3),
            "current_summary_after_send_p50": round(current_p50, 3),
            "p50_reduction": round(legacy_p50 - current_p50, 3),
        },
        "proves": (
            "moving independent summary scheduling after text send removes that "
            "phase from the user-visible delivery boundary"
        ),
        "does_not_prove": (
            "live OpenRouter, Wazzup, Zoho, database, Redis, or production latency"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=9)
    parser.add_argument("--model-ms", type=float, default=20.0)
    parser.add_argument("--persist-ms", type=float, default=5.0)
    parser.add_argument("--summary-ms", type=float, default=30.0)
    parser.add_argument("--outbound-ms", type=float, default=5.0)
    args = parser.parse_args()
    if args.samples < 1:
        parser.error("--samples must be positive")
    if any(
        value < 0
        for value in (
            args.model_ms,
            args.persist_ms,
            args.summary_ms,
            args.outbound_ms,
        )
    ):
        parser.error("phase durations must be non-negative")
    print(json.dumps(asyncio.run(_benchmark(args)), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
