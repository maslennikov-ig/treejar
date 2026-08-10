#!/usr/bin/env python3
"""Measure reply coverage and first-reply time without emitting message text."""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

_REPEAT_RE = re.compile(r"^(?P<scenario>.+?)-r\d+$")


def _normalized(text: object) -> str:
    return " ".join(str(text or "").split()).casefold()


def _timestamp(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("cannot take a percentile of an empty list")
    index = round((len(ordered) - 1) * quantile)
    return ordered[index]


def _bootstrap_interval(
    clusters: dict[str, list[tuple[int, int, list[float]]]],
    *,
    samples: int,
    seed: int,
    metric: str,
) -> list[float] | None:
    names = sorted(clusters)
    if not names or samples <= 0:
        return None
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        selected = [rng.choice(names) for _ in names]
        rows = [row for name in selected for row in clusters[name]]
        if metric == "coverage":
            denominator = sum(row[0] for row in rows)
            if denominator:
                estimates.append(100 * sum(row[1] for row in rows) / denominator)
        elif metric == "median_seconds":
            durations = [value for row in rows for value in row[2]]
            if durations:
                estimates.append(statistics.median(durations))
        else:
            raise ValueError(f"unknown metric: {metric}")
    if not estimates:
        return None
    return [
        round(_percentile(estimates, 0.025), 2),
        round(_percentile(estimates, 0.975), 2),
    ]


def _load_dialogs(path: pathlib.Path) -> list[dict[str, Any]]:
    dialogs: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            payload = json.loads(line)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: expected an object")
            dialogs.append(payload)
    return dialogs


def _corpus_metrics(
    dialogs: list[dict[str, Any]],
    *,
    boilerplate_min_dialogues: int,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, object]:
    seller_text_dialogs: dict[str, set[int]] = defaultdict(set)
    for dialog in dialogs:
        dialog_id = int(dialog["dialog_id"])
        for message in dialog["messages"]:
            if message.get("role") == "seller" and message.get("type") == "text":
                seller_text_dialogs[_normalized(message.get("text"))].add(dialog_id)
    boilerplates = {
        text
        for text, dialog_ids in seller_text_dialogs.items()
        if len(dialog_ids) >= boilerplate_min_dialogues
        and "<phone>" in text
        and len(text) >= 200
    }

    customer_messages = 0
    answered_messages = 0
    first_reply_durations: list[float] = []
    first_reply_eligible = 0
    excluded_boilerplate = 0
    continuity = Counter()
    cluster_rows: dict[str, list[tuple[int, int, list[float]]]] = defaultdict(list)
    manager_dialogs = Counter()

    for dialog in dialogs:
        manager = str(dialog.get("manager") or "unattributed")
        manager_dialogs[manager] += 1
        flags = dialog.get("continuity") or {}
        for key in (
            "ends_client_no_seller_answer",
            "ends_seller_no_client_reply",
            "boilerplate_call_footer",
        ):
            continuity[key] += bool(flags.get(key))

        messages = list(dialog.get("messages") or [])
        substantive_seller_indexes: list[int] = []
        for index, message in enumerate(messages):
            if message.get("role") != "seller":
                continue
            normalized = _normalized(message.get("text"))
            if message.get("type") == "text" and normalized in boilerplates:
                excluded_boilerplate += 1
                continue
            if message.get("type") == "text" and normalized:
                substantive_seller_indexes.append(index)

        customer_indexes = [
            index
            for index, message in enumerate(messages)
            if message.get("role") == "client"
        ]
        dialog_answered = sum(
            any(
                seller_index > customer_index
                for seller_index in substantive_seller_indexes
            )
            for customer_index in customer_indexes
        )
        customer_messages += len(customer_indexes)
        answered_messages += dialog_answered

        durations: list[float] = []
        if customer_indexes:
            first_reply_eligible += 1
            first_customer = customer_indexes[0]
            first_seller = next(
                (
                    index
                    for index in substantive_seller_indexes
                    if index > first_customer
                ),
                None,
            )
            if first_seller is not None:
                elapsed = (
                    _timestamp(messages[first_seller]["sent_at"])
                    - _timestamp(messages[first_customer]["sent_at"])
                ).total_seconds()
                if elapsed >= 0:
                    durations.append(elapsed)
                    first_reply_durations.append(elapsed)
        cluster_rows[manager].append(
            (len(customer_indexes), dialog_answered, durations)
        )

    coverage = 100 * answered_messages / customer_messages if customer_messages else 0.0
    first_reply_median = (
        statistics.median(first_reply_durations) if first_reply_durations else None
    )
    largest_manager = max(manager_dialogs.values(), default=0)
    return {
        "dialogs": len(dialogs),
        "managers": len(manager_dialogs),
        "largest_manager_dialogues": largest_manager,
        "largest_manager_share_pct": round(100 * largest_manager / len(dialogs), 2)
        if dialogs
        else 0.0,
        "customer_messages": customer_messages,
        "answered_customer_messages": answered_messages,
        "coverage_pct": round(coverage, 2),
        "coverage_cluster_ci95_pct": _bootstrap_interval(
            cluster_rows,
            samples=bootstrap_samples,
            seed=seed,
            metric="coverage",
        ),
        "first_reply_eligible_dialogues": first_reply_eligible,
        "first_reply_observed_dialogues": len(first_reply_durations),
        "first_reply_median_seconds": round(first_reply_median, 2)
        if first_reply_median is not None
        else None,
        "first_reply_cluster_ci95_seconds": _bootstrap_interval(
            cluster_rows,
            samples=bootstrap_samples,
            seed=seed + 1,
            metric="median_seconds",
        ),
        "ends_client_no_seller_answer": continuity["ends_client_no_seller_answer"],
        "ends_seller_no_client_reply": continuity["ends_seller_no_client_reply"],
        "boilerplate_flagged_dialogues": continuity["boilerplate_call_footer"],
        "excluded_boilerplate_messages": excluded_boilerplate,
        "boilerplate_distinct_texts": len(boilerplates),
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": seed,
    }


def _scenario(packet: str) -> str:
    match = _REPEAT_RE.match(packet)
    return match.group("scenario") if match else packet


def _bot_metrics(
    packets: pathlib.Path, *, bootstrap_samples: int, seed: int
) -> dict[str, object]:
    packet_count = 0
    customer_messages = 0
    answered_messages = 0
    first_reply_durations: list[float] = []
    cluster_rows: dict[str, list[tuple[int, int, list[float]]]] = defaultdict(list)

    for path in sorted(packets.glob("*.json")):
        packet_count += 1
        payload = json.loads(path.read_text(encoding="utf-8"))
        turns = list(payload.get("turns") or [])
        answered = sum(
            bool(_normalized((turn.get("assistant") or {}).get("content")))
            for turn in turns
        )
        durations: list[float] = []
        if turns and _normalized((turns[0].get("assistant") or {}).get("content")):
            duration = float(turns[0]["duration_seconds"])
            durations.append(duration)
            first_reply_durations.append(duration)
        customer_messages += len(turns)
        answered_messages += answered
        cluster_rows[_scenario(path.stem)].append((len(turns), answered, durations))

    coverage = 100 * answered_messages / customer_messages if customer_messages else 0.0
    median = statistics.median(first_reply_durations) if first_reply_durations else None
    return {
        "packets": packet_count,
        "scenarios": len(cluster_rows),
        "customer_messages": customer_messages,
        "answered_customer_messages": answered_messages,
        "coverage_pct": round(coverage, 2),
        "coverage_cluster_ci95_pct": _bootstrap_interval(
            cluster_rows,
            samples=bootstrap_samples,
            seed=seed,
            metric="coverage",
        ),
        "first_reply_observed_packets": len(first_reply_durations),
        "first_reply_median_seconds": round(median, 2) if median is not None else None,
        "first_reply_cluster_ci95_seconds": _bootstrap_interval(
            cluster_rows,
            samples=bootstrap_samples,
            seed=seed + 1,
            metric="median_seconds",
        ),
        "bootstrap_samples": bootstrap_samples,
        "bootstrap_seed": seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=pathlib.Path, required=True)
    parser.add_argument("--packets", type=pathlib.Path, required=True)
    parser.add_argument("--boilerplate-min-dialogues", type=int, default=100)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260810)
    args = parser.parse_args()
    try:
        if not args.corpus.is_file() or not args.packets.is_dir():
            raise ValueError("corpus file and packet directory must exist")
        dialogs = _load_dialogs(args.corpus)
        result = {
            "schema_version": "treejar-corpus-response-metrics/v1",
            "definition": {
                "coverage": "a client message has a later substantive seller reply in the same dialogue",
                "first_reply": "first client message to first later substantive seller text",
                "boilerplate": "repeated seller text in at least the configured number of dialogues, containing <PHONE>, at least 200 characters",
                "corpus_clusters": "manager",
                "bot_clusters": "scenario",
            },
            "corpus": _corpus_metrics(
                dialogs,
                boilerplate_min_dialogues=args.boilerplate_min_dialogues,
                bootstrap_samples=args.bootstrap_samples,
                seed=args.seed,
            ),
            "bot": _bot_metrics(
                args.packets,
                bootstrap_samples=args.bootstrap_samples,
                seed=args.seed,
            ),
        }
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"cannot compute response metrics: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
