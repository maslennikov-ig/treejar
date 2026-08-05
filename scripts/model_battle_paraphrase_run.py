"""Run the paraphrase checker over the probe set, one call per claim.

Isolation matches the rest of the battle harness: no Treejar storage, no Zoho,
no Wazzup, no production runtime configuration is touched. The only external
call is to the provider, one per probe.

Latency is recorded per call because `tj-feet.9` has to report the cost of
adoption in milliseconds as well as in dollars: this checker would sit on the
customer's turn, not in a batch.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from scripts.model_battle_paraphrase import (
    CHECKER_INSTRUCTION,
    CHECKER_VERSION,
    PROBE_SET,
    PROBE_SET_VERSION,
    ParaphraseProbe,
    checker_payload,
)

from src.core.config import settings


def _messages(probe: ParaphraseProbe) -> list[dict[str, Any]]:
    payload = json.dumps(
        checker_payload(probe), ensure_ascii=False, separators=(",", ":")
    )
    return [
        {"role": "system", "content": CHECKER_INSTRUCTION},
        {"role": "user", "content": payload},
    ]


def _read_verdict(output: str) -> tuple[bool | None, str]:
    """A checker that will not answer in the contract must not be counted as one."""
    text = str(output).strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[-1] if "\n" in text else text
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return None, ""
    if not isinstance(parsed, dict) or not isinstance(parsed.get("supported"), bool):
        return None, ""
    return bool(parsed["supported"]), str(parsed.get("added") or "")


async def run_probe_set(
    *,
    model: str,
    output_path: Path,
    repetitions: int,
    max_tokens: int,
) -> None:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    results: list[dict[str, Any]] = []
    total_cost = 0.0
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://noor.starec.ai",
            "X-Title": "Noor Paraphrase Checker",
        },
    ) as client:
        for repetition in range(1, repetitions + 1):
            for index, probe in enumerate(PROBE_SET, start=1):
                payload = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": 0,
                    "provider": {"allow_fallbacks": False},
                    "usage": {"include": True},
                    "messages": _messages(probe),
                }
                print(
                    f"[probe {index}/{len(PROBE_SET)} rep={repetition}] "
                    f"{probe.probe_id} {probe.label}",
                    flush=True,
                )
                started = time.monotonic()
                response = await client.post(
                    "/chat/completions", json=payload, timeout=300.0
                )
                elapsed_ms = (time.monotonic() - started) * 1000.0
                response.raise_for_status()
                body = response.json()
                usage = body.get("usage") or {}
                cost = usage.get("cost")
                if cost is not None:
                    total_cost += float(cost)
                choices = body.get("choices")
                if not choices:
                    # A provider-side error body carries no choices. Losing the
                    # whole run to one of them would cost more than the row.
                    print(f"  no choices: {str(body.get('error'))[:120]}", flush=True)
                    results.append(
                        {
                            "probe_id": probe.probe_id,
                            "language": probe.language,
                            "label": probe.label,
                            "repetition": repetition,
                            "model": model,
                            "supported": None,
                            "blocked": None,
                            "added": "",
                            "latency_ms": round(elapsed_ms, 1),
                            "raw": "",
                            "provider_error": True,
                            "cost_usd": None,
                        }
                    )
                    continue
                choice = choices[0]
                supported, added = _read_verdict(choice["message"].get("content") or "")
                results.append(
                    {
                        "probe_id": probe.probe_id,
                        "probe_set_version": PROBE_SET_VERSION,
                        "checker_version": CHECKER_VERSION,
                        "language": probe.language,
                        "label": probe.label,
                        "repetition": repetition,
                        "model": model,
                        "supported": supported,
                        "blocked": None if supported is None else not supported,
                        "added": added,
                        "latency_ms": round(elapsed_ms, 1),
                        "raw": choice["message"].get("content") or "",
                        "finish_reason": choice.get("finish_reason"),
                        "cost_usd": float(cost) if cost is not None else None,
                    }
                )
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latencies = sorted(row["latency_ms"] for row in results)
    print(f"model: {model}")
    print(f"verdicts: {len(results)}")
    print(f"unparseable: {sum(1 for row in results if row['supported'] is None)}")
    print(f"median latency: {latencies[len(latencies) // 2]:.0f} ms")
    print(f"cost: ${total_cost:.6f}")
    print(f"cost per claim: ${total_cost / max(len(results), 1):.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=200)
    args = parser.parse_args()
    asyncio.run(
        run_probe_set(
            model=args.model,
            output_path=args.output,
            repetitions=args.repetitions,
            max_tokens=args.max_tokens,
        )
    )


if __name__ == "__main__":
    main()
