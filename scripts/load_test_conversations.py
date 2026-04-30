"""Bounded local/mock conversation load harness.

This script does not send HTTP, Wazzup, Zoho, OpenRouter, or customer traffic.
It measures the local queue/worker envelope for synthetic inbound batches so
final-readiness claims can cite a reproducible, capped concurrency run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from typing import NamedTuple, TypedDict

MAX_CONVERSATIONS = 200
MAX_MESSAGES_PER_CONVERSATION = 10
MAX_CONCURRENCY = 25


class HarnessConfig(NamedTuple):
    conversations: int = 50
    messages_per_conversation: int = 3
    concurrency: int = 10
    processing_delay_ms: float = 25.0
    ack_budget_ms: float = 50.0
    p95_budget_ms: float = 1_000.0


class ConversationResult(TypedDict):
    ack_ms: float
    total_ms: float
    messages: int
    ok: bool


class HarnessResult(TypedDict):
    mode: str
    conversations: int
    messages: int
    concurrency: int
    processing_delay_ms: float
    max_in_flight: int
    failed: int
    p50_ack_ms: float
    p95_ack_ms: float
    p50_total_ms: float
    p95_total_ms: float
    total_wall_ms: float
    ack_budget_ms: float
    p95_budget_ms: float
    passed: bool


def validate_limits(config: HarnessConfig) -> None:
    if not 1 <= config.conversations <= MAX_CONVERSATIONS:
        raise ValueError(
            f"conversations must be between 1 and {MAX_CONVERSATIONS}; "
            f"got {config.conversations}"
        )
    if not 1 <= config.messages_per_conversation <= MAX_MESSAGES_PER_CONVERSATION:
        raise ValueError(
            "messages_per_conversation must be between 1 and "
            f"{MAX_MESSAGES_PER_CONVERSATION}; got {config.messages_per_conversation}"
        )
    if not 1 <= config.concurrency <= MAX_CONCURRENCY:
        raise ValueError(
            f"concurrency must be between 1 and {MAX_CONCURRENCY}; "
            f"got {config.concurrency}"
        )
    if config.processing_delay_ms < 0:
        raise ValueError("processing_delay_ms must be non-negative")
    if config.ack_budget_ms <= 0 or config.p95_budget_ms <= 0:
        raise ValueError("budgets must be positive")


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(ordered[index], 3)


def _mock_messages(conversation_index: int, count: int) -> list[dict[str, object]]:
    chat_id = f"load-test-{conversation_index:04d}"
    return [
        {
            "messageId": f"{chat_id}-{message_index}",
            "chatId": chat_id,
            "chatType": "whatsapp",
            "type": "text",
            "text": f"Mock message {message_index}",
            "timestamp": 1_777_000_000 + message_index,
            "channelId": "local-mocked-channel",
        }
        for message_index in range(count)
    ]


async def run_harness(config: HarnessConfig) -> HarnessResult:
    validate_limits(config)

    semaphore = asyncio.Semaphore(config.concurrency)
    lock = asyncio.Lock()
    in_flight = 0
    max_in_flight = 0
    wall_start = time.perf_counter()

    async def run_one(conversation_index: int) -> ConversationResult:
        nonlocal in_flight, max_in_flight

        start = time.perf_counter()
        messages = _mock_messages(
            conversation_index,
            config.messages_per_conversation,
        )
        queue_item = {
            "chat_id": messages[0]["chatId"],
            "messages": messages,
        }
        del queue_item
        await asyncio.sleep(0)
        ack_ms = (time.perf_counter() - start) * 1_000

        try:
            async with semaphore:
                async with lock:
                    in_flight += 1
                    max_in_flight = max(max_in_flight, in_flight)
                try:
                    await asyncio.sleep(config.processing_delay_ms / 1_000)
                finally:
                    async with lock:
                        in_flight -= 1
            total_ms = (time.perf_counter() - start) * 1_000
            return {
                "ack_ms": round(ack_ms, 3),
                "total_ms": round(total_ms, 3),
                "messages": len(messages),
                "ok": True,
            }
        except Exception:
            total_ms = (time.perf_counter() - start) * 1_000
            return {
                "ack_ms": round(ack_ms, 3),
                "total_ms": round(total_ms, 3),
                "messages": len(messages),
                "ok": False,
            }

    results = await asyncio.gather(
        *(run_one(index) for index in range(config.conversations))
    )
    ack_values = [result["ack_ms"] for result in results]
    total_values = [result["total_ms"] for result in results]
    failed = sum(1 for result in results if not result["ok"])
    p95_ack_ms = _percentile(ack_values, 0.95)
    p95_total_ms = _percentile(total_values, 0.95)

    passed = (
        failed == 0
        and p95_ack_ms <= config.ack_budget_ms
        and p95_total_ms <= config.p95_budget_ms
    )

    return {
        "mode": "local-mocked",
        "conversations": config.conversations,
        "messages": sum(result["messages"] for result in results),
        "concurrency": config.concurrency,
        "processing_delay_ms": config.processing_delay_ms,
        "max_in_flight": max_in_flight,
        "failed": failed,
        "p50_ack_ms": _percentile(ack_values, 0.50),
        "p95_ack_ms": p95_ack_ms,
        "p50_total_ms": _percentile(total_values, 0.50),
        "p95_total_ms": p95_total_ms,
        "total_wall_ms": round((time.perf_counter() - wall_start) * 1_000, 3),
        "ack_budget_ms": config.ack_budget_ms,
        "p95_budget_ms": config.p95_budget_ms,
        "passed": passed,
    }


def parse_args(argv: list[str] | None = None) -> HarnessConfig:
    parser = argparse.ArgumentParser(
        description="Run a bounded local/mock inbound conversation load harness."
    )
    parser.add_argument("--conversations", type=int, default=50)
    parser.add_argument("--messages-per-conversation", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--processing-delay-ms", type=float, default=25.0)
    parser.add_argument("--ack-budget-ms", type=float, default=50.0)
    parser.add_argument("--p95-budget-ms", type=float, default=1_000.0)
    args = parser.parse_args(argv)
    config = HarnessConfig(
        conversations=args.conversations,
        messages_per_conversation=args.messages_per_conversation,
        concurrency=args.concurrency,
        processing_delay_ms=args.processing_delay_ms,
        ack_budget_ms=args.ack_budget_ms,
        p95_budget_ms=args.p95_budget_ms,
    )
    validate_limits(config)
    return config


def print_result(result: HarnessResult) -> None:
    print(json.dumps(result, indent=2, sort_keys=True))


async def async_main(argv: list[str] | None = None) -> int:
    try:
        config = parse_args(argv)
    except ValueError as exc:
        print(f"Invalid load harness config: {exc}", file=sys.stderr)
        return 2

    result = await run_harness(config)
    print_result(result)
    return 0 if result["passed"] else 1


def main() -> None:
    raise SystemExit(asyncio.run(async_main()))


if __name__ == "__main__":
    main()
