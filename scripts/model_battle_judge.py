"""Run the blind rubric audit for a completed model-battle round.

The judge only ever receives `sales_blind_review.json`: the synthetic scenario,
the rubric, and answers behind rotating labels. Candidate identities live in the
private reveal file, so blindness here is mechanical rather than procedural.

The judge model must not be one of the candidates. This script refuses to run
otherwise, because a candidate scoring its own answer is self-preference bias by
construction.

Isolation matches `model_battle.py`: no Treejar, Zoho, Wazzup, production
storage, or runtime configuration is touched.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx
from scripts.model_battle import (
    _BLIND_REVIEW_DIMENSIONS,
    models_for_profile,
    parse_json_content,
)

from src.core.config import settings

_JUDGE_SYSTEM_PROMPT = (
    "You are an impartial evaluator of B2B office-furniture sales replies. "
    "You receive one synthetic scenario and several anonymous candidate answers "
    "labelled with letters. Score each answer independently and only against "
    "the scenario evidence you are given. Never guess which system produced an "
    "answer, and never let answer order influence a score. Return JSON only."
)


def _answer_contract(labels: list[str]) -> str:
    dimensions = ", ".join(
        f'"{name}": <integer 1-5>' for name in sorted(_BLIND_REVIEW_DIMENSIONS)
    )
    return (
        "Return a JSON object mapping every label to its review:\n"
        "{\n"
        + ",\n".join(
            f'  "{label}": {{"scores": {{{dimensions}}}, '
            '"critical_failure": <boolean>, "critical_failure_reason": <string, '
            'empty unless critical_failure is true>, "score_out_of_30": <number '
            '0-30>, "applicable_rules": <sorted array of the rule keys you '
            "applied>}"
            for label in labels
        )
        + "\n}\n"
        "Mark critical_failure only for an invented commercial fact, a wrong "
        "action or tool outcome, a wrong required language, or materially "
        "unsafe advice."
    )


def _build_payload(
    row: dict[str, Any], *, model: str, max_tokens: int
) -> dict[str, Any]:
    labels = sorted(row["answers"])
    scenario = row["scenario"]
    user_content = json.dumps(
        {
            "scenario": {
                "system_prompt": scenario["system_prompt"],
                "conversation": scenario["conversation"],
                "user_prompt": scenario["user_prompt"],
                "tool_results": scenario["tool_results"],
            },
            "rubric": scenario["rubric"],
            "answers": {label: row["answers"][label] for label in labels},
        },
        ensure_ascii=False,
    )
    return {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": 0,
        # No `require_parameters` here. That pin exists so candidates are
        # compared under identical routing; applying it to the judge filters out
        # every endpoint that does not advertise `response_format` and leaves no
        # route at all. Fallbacks stay off so the judge endpoint is reproducible.
        "provider": {"allow_fallbacks": False},
        "usage": {"include": True},
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"{user_content}\n\n{_answer_contract(labels)}",
            },
        ],
    }


def _validate_review(review: Any, labels: list[str]) -> dict[str, Any]:
    if not isinstance(review, dict):
        raise ValueError("judge returned a non-object review")
    if sorted(review) != labels:
        raise ValueError(f"judge labels {sorted(review)} do not match {labels}")
    for label in labels:
        entry = review[label]
        if not isinstance(entry, dict):
            raise ValueError(f"label {label} is not an object")
        scores = entry.get("scores")
        if not isinstance(scores, dict) or set(scores) != _BLIND_REVIEW_DIMENSIONS:
            raise ValueError(f"label {label} has wrong rubric dimensions")
        for name, value in scores.items():
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 1 <= value <= 5
            ):
                raise ValueError(
                    f"label {label} dimension {name} must be an integer 1-5"
                )
        if not isinstance(entry.get("critical_failure"), bool):
            raise ValueError(f"label {label} lacks a boolean critical_failure")
        entry.setdefault("critical_failure_reason", "")
        if not isinstance(entry["critical_failure_reason"], str):
            raise ValueError(f"label {label} has a non-string critical_failure_reason")
        if entry["critical_failure"] and not entry["critical_failure_reason"].strip():
            raise ValueError(
                f"label {label} claims a critical failure without a reason"
            )
    return review


async def run_judge(
    *,
    blind_review_path: Path,
    output_path: Path,
    model: str,
    profile: str,
    max_tokens: int,
) -> None:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")
    candidates = set(models_for_profile(profile, "sales")) | set(
        models_for_profile(profile, "system")
        if profile.startswith("background")
        else ()
    )
    if model in candidates:
        raise SystemExit(
            f"Judge {model} is one of the candidates; blind review would be "
            "self-preference bias."
        )
    rows = json.loads(blind_review_path.read_text(encoding="utf-8"))
    scored: list[dict[str, Any]] = []
    total_cost = 0.0
    async with httpx.AsyncClient(
        base_url=settings.openrouter_base_url.rstrip("/"),
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://noor.starec.ai",
            "X-Title": "Noor Model Battle Blind Judge",
        },
    ) as client:
        for index, row in enumerate(rows, start=1):
            labels = sorted(row["answers"])
            payload = _build_payload(row, model=model, max_tokens=max_tokens)
            print(
                f"[judge {index}/{len(rows)}] {row['case_id']} "
                f"rep={row['repetition']} labels={''.join(labels)}",
                flush=True,
            )
            # A judge that reasons before answering can spend its whole budget
            # and return no content at all, so a truncated verdict is retried
            # once with a wider budget instead of being silently dropped.
            for attempt_tokens in (max_tokens, max_tokens * 2):
                payload["max_tokens"] = attempt_tokens
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
                content = choice["message"].get("content")
                if content:
                    break
                if choice.get("finish_reason") != "length":
                    raise RuntimeError(
                        f"{row['case_id']} rep={row['repetition']}: judge returned "
                        f"no content, finish_reason={choice.get('finish_reason')}"
                    )
            if not content:
                raise RuntimeError(
                    f"{row['case_id']} rep={row['repetition']}: judge verdict was "
                    f"still truncated at {max_tokens * 2} tokens"
                )
            review = _validate_review(parse_json_content(content), labels)
            scored.append(
                {
                    "case_id": row["case_id"],
                    "repetition": row["repetition"],
                    "scores": review,
                }
            )
    output_path.write_text(
        json.dumps(scored, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"judge model: {model}")
    print(f"judged rows: {len(scored)}")
    print(f"judge cost: ${total_cost:.6f}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blind-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--judge-model", required=True)
    parser.add_argument("--profile", default="core-hard-2026-08-03")
    parser.add_argument("--max-tokens", type=int, default=8000)
    args = parser.parse_args()
    asyncio.run(
        run_judge(
            blind_review_path=args.blind_review,
            output_path=args.output,
            model=args.judge_model,
            profile=args.profile,
            max_tokens=args.max_tokens,
        )
    )


if __name__ == "__main__":
    main()
