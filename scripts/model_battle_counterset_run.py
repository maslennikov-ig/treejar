"""Generate one response per counter-set case, once, for the paired comparison.

The guards of `tj-feet.2` and `tj-feet.3` are deterministic code. Running the
counter-set twice — once before them and once after — would pay twice and mix
the guard delta with generation noise. So generation happens once here, and the
guards are then applied to the same text under two configurations.

Isolation matches the rest of the battle harness: no Treejar storage, no Zoho,
no Wazzup, no production runtime configuration is touched. The only external
call is to the provider, one per case.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from scripts.model_battle_counterset import COUNTER_SET, CounterCase

from src.core.config import settings

_SYSTEM_PROMPT = (
    "You are a UAE office-furniture sales assistant. Reply in the customer's "
    "language and use only the catalog evidence given in this case. Never invent "
    "price, stock, discount, delivery, payment, warranty or product claims. "
    "Catalog evidence is descriptive; only an operational inventory rate may "
    "confirm availability. Do not say a quotation was created unless a tool "
    "confirms it. Be concise and helpful, and end with a concrete low-pressure "
    "next step."
)

_DECLINED_QUOTE_HISTORY = (
    {"role": "user", "content": "Would you quote these?"},
    {"role": "assistant", "content": "I can prepare a quotation whenever you want."},
    {"role": "user", "content": "No quotation, thank you."},
    {"role": "assistant", "content": "Understood. No quotation."},
)


def _messages(case: CounterCase, *, turn_directives: bool) -> list[dict[str, Any]]:
    evidence = json.dumps(
        {"catalog_evidence": list(case.evidence)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    system = f"{_SYSTEM_PROMPT}\n\n{evidence}"
    if turn_directives:
        # The product runtime's own function, over the customer request, so the
        # measured text is the shipped text rather than a paraphrase of it.
        # Imported here because the engine builds a provider at import time.
        from src.llm.engine import _turn_runtime_directives

        earned = _turn_runtime_directives(case.request)
        if earned:
            block = "\n".join(f"- {directive}" for directive in earned)
            system += f"\n\n[RUNTIME DIRECTIVES]\n{block}"
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
    if case.category == "renewed_quotation_request":
        messages.extend(dict(turn) for turn in _DECLINED_QUOTE_HISTORY)
    messages.append({"role": "user", "content": case.request})
    return messages


async def run_counter_set(
    *,
    model: str,
    output_path: Path,
    repetitions: int,
    max_tokens: int,
    turn_directives: bool,
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
            "X-Title": "Noor Counter Set",
        },
    ) as client:
        for repetition in range(1, repetitions + 1):
            for index, case in enumerate(COUNTER_SET, start=1):
                payload = {
                    "model": model,
                    "max_tokens": max_tokens,
                    "temperature": 0,
                    "provider": {"allow_fallbacks": False},
                    "usage": {"include": True},
                    "messages": _messages(case, turn_directives=turn_directives),
                }
                print(
                    f"[counter-set {index}/{len(COUNTER_SET)} rep={repetition}] "
                    f"{case.case_id} {case.category}",
                    flush=True,
                )
                response = await client.post(
                    "/chat/completions", json=payload, timeout=300.0
                )
                response.raise_for_status()
                body = response.json()
                usage = body.get("usage") or {}
                cost = usage.get("cost")
                if cost is not None:
                    total_cost += float(cost)
                choice = body["choices"][0]
                results.append(
                    {
                        "case_id": case.case_id,
                        "turn_directives": turn_directives,
                        "category": case.category,
                        "language": case.language,
                        "repetition": repetition,
                        "model": model,
                        "is_control": case.is_control,
                        "missing_fields": list(case.missing_fields),
                        "response": choice["message"].get("content") or "",
                        "finish_reason": choice.get("finish_reason"),
                        "cost_usd": float(cost) if cost is not None else None,
                    }
                )
    output_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"model: {model}")
    print(f"turn_directives: {turn_directives}")
    print(f"responses: {len(results)}")
    print(f"cost: ${total_cost:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument(
        "--turn-directives",
        action="store_true",
        help="add the per-turn runtime directives the product runtime would add",
    )
    args = parser.parse_args()
    asyncio.run(
        run_counter_set(
            model=args.model,
            output_path=args.output,
            repetitions=args.repetitions,
            max_tokens=args.max_tokens,
            turn_directives=args.turn_directives,
        )
    )


if __name__ == "__main__":
    main()
