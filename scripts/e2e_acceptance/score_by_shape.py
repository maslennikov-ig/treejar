#!/usr/bin/env python3
"""Report acceptance split by conversation shape, with the denominator visible.

Why this exists, 2026-08-09. The transactional/project fork made rules 6, 10 and
13 correctly not applicable to an ordinary short order. That is the right
rubric, and it broke the number: `calculate_weighted_score` normalises the
earned points back up to /30 over whatever applied, so removing the hard rules
raises the score. Two conversations scored a perfect 30 on the eight easy rules
alone -- 1, 2, 3, 4, 5, 7, 8, 9 -- with 6, 10, 11, 13, 14 and 15 all n/a.

There is no arithmetic that fixes this, because the premise is wrong: a score
over eight rules and a score over fifteen are not the same measurement and
should never have shared a threshold. Both research reports of 2026-08-09 said
the same thing from the other direction -- the analytical split that matters is
by conversation shape, not by anything else.

So this tool refuses to print one number. It prints one per shape, always with
the applicable-rule count beside it, and it never compares across shapes.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import statistics
import sys
from collections.abc import Sequence

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.quality.schemas import (  # noqa: E402
    CriterionScore,
    calculate_weighted_score,
)

PROJECT_SIGNAL = "project_scope"


def _score_file(path: pathlib.Path) -> tuple[float, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    criteria = [
        CriterionScore(
            rule_number=item["rule_number"],
            rule_name=str(item["rule_number"]),
            score=item["score"],
            comment="",
            applicable=item["applicable"],
            n_a=item["n_a"],
            evidence=[],
        )
        for item in payload["criteria"]
    ]
    total, _ = calculate_weighted_score(criteria)
    return total, sum(criterion.applicable for criterion in criteria)


def _shape_of(packet: pathlib.Path) -> str:
    payload = json.loads(packet.read_text(encoding="utf-8"))
    applicability = payload.get("applicability") or {}
    # Rules 6, 10 and 13 are the fork's own signature: charged on a project,
    # not on an ordinary order. Reading them back is more robust than
    # re-deriving the signal from the transcript here.
    forked_on = sum(bool(applicability.get(rule)) for rule in ("6", "10", "13"))
    return "project" if forked_on >= 2 else "transactional"


def _interval(values: Sequence[float]) -> float:
    if len(values) < 2:
        return float("nan")
    return 1.96 * statistics.stdev(values) / math.sqrt(len(values))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packets", type=pathlib.Path, required=True)
    parser.add_argument("--scores", type=pathlib.Path, required=True)
    args = parser.parse_args()

    by_packet: dict[str, list[float]] = {}
    coverage: dict[str, int] = {}
    for reader_dir in sorted(p for p in args.scores.iterdir() if p.is_dir()):
        for path in sorted(reader_dir.glob("*.json")):
            total, applicable = _score_file(path)
            by_packet.setdefault(path.stem, []).append(total)
            coverage[path.stem] = applicable

    shapes: dict[str, dict[str, list[float]]] = {}
    for packet_name, totals in by_packet.items():
        packet = args.packets / f"{packet_name}.json"
        if not packet.exists():
            continue
        scenario = packet_name.split("-")[0]
        shapes.setdefault(_shape_of(packet), {}).setdefault(scenario, []).append(
            statistics.fmean(totals)
        )

    gaps = [
        abs(values[0] - values[1]) for values in by_packet.values() if len(values) == 2
    ]

    for shape in sorted(shapes):
        scenarios = shapes[shape]
        means = [statistics.fmean(rounds) for rounds in scenarios.values()]
        rules = [coverage[name] for name in coverage if name.split("-")[0] in scenarios]
        print(f"\n=== {shape}")
        print(f"{'scenario':<10}{'mean /30':>10}{'runs':>6}{'rules':>7}")
        for scenario in sorted(scenarios):
            applicable = next(
                coverage[name] for name in coverage if name.split("-")[0] == scenario
            )
            print(
                f"{scenario:<10}{statistics.fmean(scenarios[scenario]):>10.2f}"
                f"{len(scenarios[scenario]):>6}{applicable:>7}"
            )
        print(
            f"{'mean':<10}{statistics.fmean(means):>10.2f}"
            f"{'':>6}{statistics.fmean(rules):>7.1f}"
        )
        interval = _interval(means)
        if not math.isnan(interval):
            print(
                f"{'':<10}{'+/- ' + format(interval, '.2f'):>10} (95% over scenarios)"
            )

    if gaps:
        print(
            f"\nreader disagreement: mean |A-B| = {statistics.fmean(gaps):.2f} "
            f"(max {max(gaps):.1f}, n={len(gaps)})"
        )
    print(
        "\nScores from different applicable-rule counts are different "
        "measurements. Compare a shape with itself over time, never one shape "
        "with another, and never either with a figure predating the fork."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
