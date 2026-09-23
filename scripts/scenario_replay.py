"""Replay multi-turn customer scenarios through the production reply pipeline.

Runs ``src.llm.engine.process_message`` turn by turn -- decision state, tool
contracts, output guards, repair judge and deferred media selection included --
with every external dependency intercepted in-process (catalog snapshot in a
private SQLite, fake Zoho/CRM/Wazzup/Redis/Telegram). The model is either a
no-network stub (``--dry``, default) or the real OpenRouter model (``--live``),
resolved the way the runtime resolves it.

Live mode spends money. It stops before any model call that could take the
run past ``--max-cost-usd`` (default 0.05), using provider-reported cost.

Examples:
    uv run python scripts/scenario_replay.py --dry
    uv run python scripts/scenario_replay.py --live --receipt
    uv run python scripts/scenario_replay.py --live tests/fixtures/scenarios/b_*.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = REPO_ROOT / "tests" / "fixtures" / "scenarios"
DEFAULT_RECEIPT = (
    REPO_ROOT / "docs" / "reports" / "2026-09-23-tester-feedback-replay.json"
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry", action="store_true", help="stub model, no network (default)"
    )
    mode.add_argument("--live", action="store_true", help="real model via OpenRouter")
    parser.add_argument("scenarios", nargs="*", type=Path, help="scenario JSON files")
    parser.add_argument("--max-cost-usd", type=float, default=0.05)
    parser.add_argument("--model", default="openai/gpt-6-luna")
    parser.add_argument(
        "--receipt",
        nargs="?",
        const=DEFAULT_RECEIPT,
        type=Path,
        help=f"write the JSON receipt (default path {DEFAULT_RECEIPT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--price-in",
        type=float,
        default=2.0,
        help="USD per 1M input tokens, fallback estimate",
    )
    parser.add_argument(
        "--price-out",
        type=float,
        default=12.0,
        help="USD per 1M output tokens, fallback estimate",
    )
    parser.add_argument(
        "--recheck",
        type=Path,
        help="re-run the scenario checks over an existing receipt, no model calls",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def _prepare_environment(live: bool) -> None:
    """Neutralise every outbound credential before `src` reads its settings."""

    os.environ["TELEGRAM_BOT_TOKEN"] = ""
    os.environ["TELEGRAM_CHAT_ID"] = ""
    os.environ["WAZZUP_API_KEY"] = "scenario-replay-no-send"
    os.environ["WAZZUP_API_URL"] = "http://scenario-replay.invalid"
    os.environ["LOGFIRE_IGNORE_NO_CONFIG"] = "1"
    if not live:
        os.environ["OPENROUTER_API_KEY"] = "scenario-replay-stub"
    os.chdir(REPO_ROOT)
    for path in (REPO_ROOT, Path(__file__).resolve().parent):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    _prepare_environment(args.live)

    import logging

    logging.basicConfig(
        level=logging.ERROR, format="%(levelname)s %(name)s: %(message)s"
    )

    from scenario_replay.harness import Replay, ReplayConfig, recheck_receipt

    if args.recheck:
        receipt = recheck_receipt(json.loads(args.recheck.read_text(encoding="utf-8")))
        for scenario in receipt["scenarios"]:
            for check in scenario["checks"]:
                print(f"{scenario['id']} {check['type']}: {check['status']}")
        args.recheck.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return 0

    if args.live:
        from src.core.config import settings

        if not settings.openrouter_api_key or settings.openrouter_api_key == "test-key":
            print("OPENROUTER_API_KEY is not configured in .env", file=sys.stderr)
            return 2

    paths = [p.resolve() for p in args.scenarios] or sorted(SCENARIO_DIR.glob("*.json"))
    config = ReplayConfig(
        scenario_paths=paths,
        mode="live" if args.live else "stub",
        max_cost_usd=args.max_cost_usd,
        model=args.model,
        price_in_per_mtok=args.price_in,
        price_out_per_mtok=args.price_out,
        echo=not args.quiet,
    )
    receipt = asyncio.run(Replay(config).run())
    run = receipt["run"]
    print(
        f"\nTOTAL cost ${run['total_cost_usd']:.6f} of cap ${run['max_cost_usd']:.2f} "
        f"({run['model_calls']} model calls, sources {run['cost_sources']})"
    )
    if run["stopped_by_budget"]:
        print(f"STOPPED BY BUDGET: {run['stopped_by_budget']}")
    if run["network_blocked"]:
        print(f"NETWORK BLOCKED: {run['network_blocked']}")
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"receipt: {args.receipt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
