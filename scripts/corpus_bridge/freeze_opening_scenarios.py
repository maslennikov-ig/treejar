#!/usr/bin/env python3
"""Freeze a seeded length-stratified set of real natural customer openings."""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import statistics
import sys
from collections import Counter, defaultdict
from typing import Any

_ATTACHMENT_EXTENSIONS = {
    ".doc",
    ".docx",
    ".gif",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".webp",
    ".xls",
    ".xlsx",
}
_TEMPLATE_PREFIX_CHARS = 48


def _normalized(text: object) -> str:
    return " ".join(str(text or "").split())


def _attachment_only(message: dict[str, Any], opening: str) -> bool:
    if message.get("type") != "text":
        return True
    suffix = pathlib.PurePosixPath(opening.casefold()).suffix
    return suffix in _ATTACHMENT_EXTENSIONS


def _customer_follow_up(messages: list[dict[str, Any]], opening_index: int) -> str:
    """What this customer said next, after the seller answered their opening.

    Every measured round in this project is twenty first turns, so the guards
    that only run on a selling turn have never appeared in one, and rules 14
    and 15 -- confirm the next step, agree the next contact -- were reported as
    unobservable rather than as zero. The corpus already holds the answer: the
    customer's own second message.

    A follow-up only counts once a seller has replied. A customer sending two
    messages in a row is still their opening turn, split.
    """

    seen_seller = False
    for message in messages[opening_index + 1 :]:
        role = message.get("role")
        if role == "seller":
            seen_seller = True
            continue
        if role != "client" or not seen_seller:
            continue
        if message.get("type") != "text":
            return ""
        text = _normalized(message.get("text"))
        if text and not _attachment_only(message, text):
            return text
        return ""
    return ""


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def _cluster_baseline_interval(
    selected: list[dict[str, Any]], *, samples: int, seed: int
) -> list[float] | None:
    by_manager: dict[str, list[int]] = defaultdict(list)
    for item in selected:
        by_manager[item["manager"]].append(item["stored_human_raw_total"])
    names = sorted(by_manager)
    if not names or samples <= 0:
        return None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(samples):
        scores = [score for _ in names for score in by_manager[rng.choice(names)]]
        means.append(statistics.fmean(scores))
    return [round(_percentile(means, 0.025), 2), round(_percentile(means, 0.975), 2)]


def _load_dialogs(path: pathlib.Path) -> list[dict[str, Any]]:
    dialogs: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: expected an object")
            dialogs.append(payload)
    return dialogs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, required=True)
    parser.add_argument("--protected-root", type=pathlib.Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--count", type=int, default=20)
    parser.add_argument("--strata", type=int, default=4)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument(
        "--with-follow-up",
        action="store_true",
        help=(
            "keep only dialogs where the customer answered the seller, and "
            "record what they said. This is the set a selling turn can be "
            "measured on at all."
        ),
    )
    args = parser.parse_args()

    try:
        if not args.corpus.is_file():
            raise ValueError(f"corpus does not exist: {args.corpus}")
        if args.count <= 0 or args.strata <= 0 or args.count % args.strata:
            raise ValueError("count must be positive and divisible by strata")
        if "/" in args.run_id or args.run_id in {".", ".."}:
            raise ValueError("run-id must be one path component")

        dialogs = _load_dialogs(args.corpus)
        openings: list[dict[str, Any]] = []
        prefixes: Counter[str] = Counter()
        for dialog in dialogs:
            messages = list(dialog.get("messages") or [])
            opening_index = next(
                (
                    index
                    for index, message in enumerate(messages)
                    if message.get("role") == "client"
                ),
                None,
            )
            if opening_index is None:
                continue
            first_client = messages[opening_index]
            opening = _normalized(first_client.get("text"))
            item = {
                "dialog_id": int(dialog["dialog_id"]),
                "manager": str(dialog.get("manager") or "unattributed"),
                "opening": opening,
                "follow_up": _customer_follow_up(messages, opening_index),
                "message": first_client,
                "evaluation": dialog.get("evaluation"),
            }
            openings.append(item)
            if (
                first_client.get("type") == "text"
                and len(opening) >= _TEMPLATE_PREFIX_CHARS
            ):
                prefixes[opening[:_TEMPLATE_PREFIX_CHARS].casefold()] += 1
        template_prefix = prefixes.most_common(1)[0][0] if prefixes else ""

        template_count = 0
        attachment_count = 0
        natural: list[dict[str, Any]] = []
        for item in openings:
            opening = item["opening"]
            if (
                template_prefix
                and opening[:_TEMPLATE_PREFIX_CHARS].casefold() == template_prefix
            ):
                template_count += 1
            elif _attachment_only(item["message"], opening):
                attachment_count += 1
            else:
                natural.append(item)

        evaluated = [item for item in natural if isinstance(item["evaluation"], dict)]
        without_follow_up = sum(1 for item in evaluated if not item["follow_up"])
        if args.with_follow_up:
            evaluated = [item for item in evaluated if item["follow_up"]]
        ranked = sorted(
            evaluated, key=lambda item: (len(item["opening"]), item["dialog_id"])
        )
        by_stratum: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for index, item in enumerate(ranked):
            stratum = min(args.strata - 1, index * args.strata // len(ranked)) + 1
            item["length_stratum"] = stratum
            by_stratum[stratum].append(item)

        per_stratum = args.count // args.strata
        selected: list[dict[str, Any]] = []
        for stratum in range(1, args.strata + 1):
            candidates = by_stratum[stratum]
            if len(candidates) < per_stratum:
                raise ValueError(
                    f"stratum {stratum} has {len(candidates)} candidates, needs {per_stratum}"
                )
            selected.extend(
                random.Random(args.seed + stratum).sample(candidates, per_stratum)
            )
        selected.sort(key=lambda item: (item["length_stratum"], item["dialog_id"]))

        protected_root = args.protected_root.resolve()
        protected_root.mkdir(parents=True, mode=0o700, exist_ok=True)
        protected_root.chmod(0o700)
        run_dir = protected_root / args.run_id
        if run_dir.exists():
            raise ValueError(f"protected run already exists: {run_dir}")
        run_dir.mkdir(mode=0o700)
        protected_path = run_dir / "scenarios.json"
        protected_document = {
            "schema_version": (
                "treejar-real-turns/v1"
                if args.with_follow_up
                else "treejar-real-openings/v1"
            ),
            "selection_seed": args.seed,
            "scenarios": [
                {
                    "dialog_id": item["dialog_id"],
                    "opening": item["opening"],
                    "opener_chars": len(item["opening"]),
                    "length_stratum": item["length_stratum"],
                    "stored_human_raw_total": int(item["evaluation"]["total_score"]),
                    "manager": item["manager"],
                    **({"follow_up": item["follow_up"]} if args.with_follow_up else {}),
                }
                for item in selected
            ],
        }
        protected_path.write_text(
            json.dumps(protected_document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        protected_path.chmod(0o600)

        scores = [int(item["evaluation"]["total_score"]) for item in selected]
        public_selection = [
            {
                "dialog_id": item["dialog_id"],
                "opener_chars": len(item["opening"]),
                "length_stratum": item["length_stratum"],
                "stored_human_raw_total": int(item["evaluation"]["total_score"]),
            }
            for item in selected
        ]
        result = {
            "schema_version": "treejar-real-openings-public-manifest/v1",
            "selection_seed": args.seed,
            "population": {
                "with_customer_opening": len(openings),
                "template": template_count,
                "attachment_only": attachment_count,
                "natural_text": len(natural),
                "evaluated_natural_text": len(evaluated),
                # Reported either way, so the cost of requiring a second turn
                # is visible before anybody pays for a round on it.
                "evaluated_without_follow_up": without_follow_up,
                "natural_text_median_chars": statistics.median(
                    len(item["opening"]) for item in natural
                ),
            },
            "selection": public_selection,
            "baseline": {
                "kind": "stored_client_judge_human_dialogue_raw_total",
                "dialogues": len(selected),
                "managers": len({item["manager"] for item in selected}),
                "mean_raw_total": round(statistics.fmean(scores), 2),
                "manager_cluster_ci95": _cluster_baseline_interval(
                    [
                        {
                            "manager": item["manager"],
                            "stored_human_raw_total": int(
                                item["evaluation"]["total_score"]
                            ),
                        }
                        for item in selected
                    ],
                    samples=args.bootstrap_samples,
                    seed=args.seed,
                ),
                "bootstrap_samples": args.bootstrap_samples,
                "bootstrap_seed": args.seed,
            },
        }
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"cannot freeze opening scenarios: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
