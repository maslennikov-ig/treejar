"""Price the `tj-feet.10` extra call: one claim pass per catalog turn.

The widened scope costs one additional model call on every turn that retrieved
a catalog row. `tj-feet.10` cannot be accepted on a design argument, because the
whole question the owner reserved is what that call costs in seconds and in
dollars on a WhatsApp turn.

So this sends the exact payload the runtime sends — the same contract directive,
the same `candidate_response` plus `retrieved_rows` shape, built by the product
functions rather than restated here — over stored counter-set replies, and
records latency and cost per turn.

Isolation matches the rest of the battle harness: no Treejar storage, no Zoho,
no Wazzup, no production runtime configuration is touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from scripts.model_battle_counterset import COUNTER_SET

from src.core.config import settings
from src.dialogue.claim_contract import row_from_catalog_product


def _rows_for_case(case: Any) -> dict[str, dict[str, str]]:
    """The retrieved rows of this case, flattened exactly as the runtime does."""
    rows: dict[str, dict[str, str]] = {}
    for evidence in case.evidence:
        extras = {
            key: value
            for key, value in evidence.items()
            if key not in {"sku", "specifications"} and value is not None
        }
        row = row_from_catalog_product(
            sku=str(evidence["sku"]),
            attributes={"specifications": evidence.get("specifications") or {}},
            extras=extras,
        )
        rows[row.sku] = dict(sorted(row.fields.items()))
    return rows


def _turns(results_path: Path) -> list[dict[str, Any]]:
    stored = json.load(results_path.open(encoding="utf-8"))
    by_case = {case.case_id: case for case in COUNTER_SET}
    turns: list[dict[str, Any]] = []
    for row in stored:
        case = by_case.get(row["case_id"])
        if case is None or not case.evidence or not row.get("response"):
            continue
        turns.append(
            {
                "case_id": row["case_id"],
                "language": row["language"],
                "repetition": row["repetition"],
                "candidate_response": row["response"],
                "retrieved_rows": _rows_for_case(case),
            }
        )
    return turns


async def run_claim_pass(
    *,
    model: str,
    results_path: Path,
    output_path: Path,
    max_tokens: int,
) -> None:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    # Imported here because the engine builds a provider at import time.
    from src.llm.engine import _claim_contract_directive

    turns = _turns(results_path)
    measured: list[dict[str, Any]] = []
    total_cost = 0.0
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://noor.starec.ai",
            "X-Title": "Noor Claim Pass",
        },
    ) as client:
        for index, turn in enumerate(turns, start=1):
            payload_json = json.dumps(
                {
                    "candidate_response": turn["candidate_response"],
                    "retrieved_rows": turn["retrieved_rows"],
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            directive = _claim_contract_directive(payload_json)
            request = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": 0,
                "provider": {"allow_fallbacks": False},
                "usage": {"include": True},
                "messages": [{"role": "system", "content": directive}],
            }
            print(
                f"[claim pass {index}/{len(turns)}] "
                f"{turn['case_id']} rep={turn['repetition']}",
                flush=True,
            )
            started = time.monotonic()
            response = await client.post(
                "/chat/completions", json=request, timeout=300.0
            )
            elapsed_ms = (time.monotonic() - started) * 1000.0
            response.raise_for_status()
            body = response.json()
            usage = body.get("usage") or {}
            cost = usage.get("cost")
            if cost is not None:
                total_cost += float(cost)
            choices = body.get("choices") or [{}]
            output = (choices[0].get("message") or {}).get("content") or ""
            parsed: Any = None
            try:
                parsed = json.loads(output.strip())
            except (TypeError, ValueError):
                parsed = None
            measured.append(
                {
                    "case_id": turn["case_id"],
                    "language": turn["language"],
                    "repetition": turn["repetition"],
                    "model": model,
                    "directive_chars": len(directive),
                    "latency_ms": round(elapsed_ms, 1),
                    "contract_followed": isinstance(parsed, dict)
                    and isinstance(parsed.get("answer"), str)
                    and bool(str(parsed.get("answer")).strip()),
                    "claim_count": (
                        len(parsed.get("claims") or [])
                        if isinstance(parsed, dict)
                        else None
                    ),
                    "raw": output,
                    "cost_usd": float(cost) if cost is not None else None,
                }
            )
    output_path.write_text(
        json.dumps(measured, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latencies = sorted(row["latency_ms"] for row in measured)
    followed = sum(1 for row in measured if row["contract_followed"])
    print(f"model: {model}")
    print(f"turns: {len(measured)}")
    print(f"contract followed: {followed}/{len(measured)}")
    print(f"latency median: {latencies[len(latencies) // 2]:.0f} ms")
    print(f"latency p90: {latencies[int(len(latencies) * 0.9)]:.0f} ms")
    print(f"cost: ${total_cost:.6f}")
    print(f"cost per turn: ${total_cost / max(len(measured), 1):.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-tokens", type=int, default=1200)
    args = parser.parse_args()
    asyncio.run(
        run_claim_pass(
            model=args.model,
            results_path=args.results,
            output_path=args.output,
            max_tokens=args.max_tokens,
        )
    )


if __name__ == "__main__":
    main()
