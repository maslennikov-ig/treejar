#!/usr/bin/env python3
"""Report a panel run on the client's convention: all fifteen, nothing dropped.

Two rulers exist. `score_by_shape.py` reports the normalised axis, where rules
that did not apply are removed and the surviving blocks stretch back to /30;
that is the right ruler for comparing one build with another. The client scores
every criterion on every dialogue and lets an unearned one stand at zero. Their
1400 human dialogues average 6.05 on that ruler.

Our published 20.02 and their 6.05 were never the same measurement. This module
is the bridge: it re-reads stored reader files through `raw_total` so both sides
land on one axis.

Two things it refuses to do, both for the same reason -- a number is only worth
what its denominator is.

**It clusters by scenario, not by packet.** A run of 53 packets is 19 scenarios,
seventeen of them repeated three times and two run once because they have
irreversible external effects. Treating repeats as independent observations
would shrink the interval by a factor it has not earned, so the estimator here
is the same `RunEstimate` the normalised axis uses: pooled within-scenario judge
noise, degrees of freedom from the repeats, mean over scenarios.

**It prints the applicability rate beside every criterion.** On the run this was
written for, rules 12, 14 and 15 -- collect contacts, close the deal, agree the
next contact -- were applicable in 2 reads of 106. Under this convention each of
those becomes a scored zero. A reader who was handed a frozen map saying "not
applicable" never went looking, so those zeros are unexamined rather than
earned, and any gap computed from them is a claim about openings, not selling.

Usage:

    uv run python -m scripts.e2e_acceptance.score_raw_convention \\
        --scores <panel-dir>/scores [--label 8b75888]
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from collections import defaultdict
from statistics import fmean

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.e2e_acceptance.score_uncertainty import (  # noqa: E402
    RunEstimate,
    ScenarioSamples,
    t_critical_95,
)

from src.quality.schemas import (  # noqa: E402
    RULE_NAMES,
    CriterionScore,
    raw_total,
)

_PACKET_RE = re.compile(r"^(?P<scenario>.+?)-r\d+$")

# The client's own axis. Their note reports 6.05 over 1247 evaluated dialogues,
# scored by anthropic/claude-haiku-4.5. It is printed here for orientation only:
# a different judge read a different genre, and this tool will not do the
# subtraction for you.
CLIENT_HUMAN_MEAN = 6.05
CLIENT_EVALUATED_DIALOGUES = 1247


def _read(
    path: pathlib.Path, *, require_map_free: bool = False
) -> list[CriterionScore]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload["criteria"]
    rule_numbers = [int(item["rule_number"]) for item in items]
    if len(items) != 15 or sorted(rule_numbers) != list(range(1, 16)):
        raise ValueError(f"{path}: expected exactly one criterion for rules 1-15")
    if require_map_free and any(
        "applicable" in item or "n_a" in item for item in items
    ):
        raise ValueError(f"{path}: map-free scores must omit applicable and n_a fields")
    return [
        CriterionScore(
            rule_number=int(item["rule_number"]),
            rule_name=RULE_NAMES[int(item["rule_number"])],
            score=int(item["score"]),
            comment="",
            applicable=bool(item.get("applicable", True)),
            n_a=bool(item.get("n_a", False)),
            evidence=[],
        )
        for item in items
    ]


def _scenario_of(packet: str) -> str:
    match = _PACKET_RE.match(packet)
    return match.group("scenario") if match else packet


def _load_reads(
    scores: pathlib.Path, *, require_map_free: bool = False
) -> dict[str, dict[str, list[CriterionScore]]]:
    reads: dict[str, dict[str, list[CriterionScore]]] = defaultdict(dict)
    for reader in sorted(path for path in scores.iterdir() if path.is_dir()):
        for score_file in sorted(reader.glob("*.json")):
            reads[score_file.stem][reader.name] = _read(
                score_file, require_map_free=require_map_free
            )
    return reads


def _packet_totals(
    reads: dict[str, dict[str, list[CriterionScore]]],
) -> dict[str, float]:
    return {
        packet: fmean(raw_total(criteria) for criteria in by_reader.values())
        for packet, by_reader in reads.items()
    }


def _estimate(label: str, packet_totals: dict[str, float]) -> RunEstimate:
    by_scenario: dict[str, list[float]] = defaultdict(list)
    for packet, total in packet_totals.items():
        by_scenario[_scenario_of(packet)].append(total)
    return RunEstimate(
        label=label,
        scenarios=tuple(
            ScenarioSamples(scenario=scenario, scores=tuple(sorted(totals)))
            for scenario, totals in sorted(by_scenario.items())
        ),
    )


def _another_scenario_half_width(estimate: RunEstimate) -> tuple[float, float] | None:
    scenario_means = [sample.mean for sample in estimate.scenarios]
    if len(scenario_means) <= 1:
        return None
    centre = fmean(scenario_means)
    spread = (
        sum((value - centre) ** 2 for value in scenario_means)
        / (len(scenario_means) - 1)
    ) ** 0.5
    return centre, t_critical_95(len(scenario_means) - 1) * spread / len(
        scenario_means
    ) ** 0.5


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", type=pathlib.Path, required=True)
    parser.add_argument("--label", default="run")
    parser.add_argument("--require-map-free", action="store_true")
    parser.add_argument("--baseline-scores", type=pathlib.Path)
    args = parser.parse_args()

    if not args.scores.is_dir():
        print(f"no such scores directory: {args.scores}", file=sys.stderr)
        return 2

    # packet -> reader -> the fifteen criteria that reader recorded
    try:
        reads = _load_reads(args.scores, require_map_free=args.require_map_free)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"invalid reader score file: {exc}", file=sys.stderr)
        return 2

    if not reads:
        print(f"no reader score files under {args.scores}", file=sys.stderr)
        return 2

    packet_totals = _packet_totals(reads)
    estimate = _estimate(args.label, packet_totals)

    read_count = sum(len(by_reader) for by_reader in reads.values())
    half_width = estimate.half_width
    judge_sd = estimate.judge_sd

    print(f"{args.label}: the client's convention, all fifteen criteria, /30")
    print(
        f"  {len(reads)} packets over {len(estimate.scenarios)} scenarios, "
        f"{read_count} blind reads"
    )
    if args.require_map_free:
        criterion_count = read_count * 15
        print(
            f"  map-free schema: {criterion_count}/{criterion_count} criteria "
            "scored; applicable/n_a absent"
        )
    interval = f" +/- {half_width:.2f}" if half_width is not None else " (no repeats)"
    print(f"  mean over packets:   {fmean(packet_totals.values()):.2f}")
    if judge_sd is not None:
        print(f"  pooled judge sd:     {judge_sd:.2f}")

    # Two intervals, because they answer two different questions and only one of
    # them is right for the comparison at hand.
    #
    #   re-read   what the mean would do if the judge read this same set again.
    #             Right for build-versus-build: the scenario set is fixed, so the
    #             between-scenario spread is identical on both sides and cancels.
    #
    #   scenario  what the mean would do on a different draw of scenarios. Right
    #             for anything said about the client's dialogue population, which
    #             we did not draw our scenarios from.
    #
    # Quoting the first where the second belongs is how a number gets ten times
    # more confident than the evidence allows.
    print(f"  interval, re-read of this set:   {estimate.mean:.2f}{interval}")
    scenario_interval = _another_scenario_half_width(estimate)
    if scenario_interval is not None:
        centre, across = scenario_interval
        scenario_means = [sample.mean for sample in estimate.scenarios]
        spread = (
            sum((value - centre) ** 2 for value in scenario_means)
            / (len(scenario_means) - 1)
        ) ** 0.5
        print(
            f"  interval, another scenario draw: {centre:.2f} +/- {across:.2f} "
            f"(scenario sd {spread:.2f})"
        )

    if args.baseline_scores is not None:
        if not args.baseline_scores.is_dir():
            print(
                f"no such baseline scores directory: {args.baseline_scores}",
                file=sys.stderr,
            )
            return 2
        try:
            baseline_reads = _load_reads(args.baseline_scores)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            print(f"invalid baseline reader score file: {exc}", file=sys.stderr)
            return 2
        baseline_totals = _packet_totals(baseline_reads)
        if set(baseline_totals) != set(packet_totals):
            print(
                "paired baseline must contain exactly the same packets as scores",
                file=sys.stderr,
            )
            return 2
        deltas = {
            packet: total - baseline_totals[packet]
            for packet, total in packet_totals.items()
        }
        delta_estimate = _estimate("paired-delta", deltas)
        delta_interval = (
            f" +/- {delta_estimate.half_width:.2f}"
            if delta_estimate.half_width is not None
            else " (no repeats)"
        )
        print(
            f"  paired baseline: {fmean(baseline_totals.values()):.2f}/30 "
            f"over the same {len(baseline_totals)} packets"
        )
        print(
            f"  paired delta, re-read of this set: {delta_estimate.mean:+.2f}"
            f"{delta_interval}"
        )
        delta_scenario_interval = _another_scenario_half_width(delta_estimate)
        if delta_scenario_interval is not None:
            delta_centre, delta_across = delta_scenario_interval
            print(
                "  paired delta, another scenario draw: "
                f"{delta_centre:+.2f} +/- {delta_across:.2f}"
            )

    disagreements = [
        abs(
            raw_total(next(iter(by_reader.values())))
            - raw_total(list(by_reader.values())[1])
        )
        for by_reader in reads.values()
        if len(by_reader) == 2
    ]
    if disagreements:
        print(
            f"  reader disagreement: {fmean(disagreements):.2f} "
            f"mean |A-B| over {len(disagreements)} packets"
        )

    if args.require_map_free:
        print("\n  rule                                      scored   raw mean")
    else:
        print("\n  rule                                      applicable   raw mean")
    for rule in range(1, 16):
        scores = [
            criteria[rule - 1].score
            for by_reader in reads.values()
            for criteria in by_reader.values()
        ]
        applicable = (
            len(scores)
            if args.require_map_free
            else sum(
                criteria[rule - 1].applicable and not criteria[rule - 1].n_a
                for by_reader in reads.values()
                for criteria in by_reader.values()
            )
        )
        name = RULE_NAMES[rule][:38]
        print(
            f"  {rule:2}  {name:<38}  {applicable:3}/{len(scores):3}   {fmean(scores):.2f}"
        )

    print(
        f"\n  For orientation only: the client reports {CLIENT_HUMAN_MEAN} over "
        f"{CLIENT_EVALUATED_DIALOGUES} evaluated human dialogues on this axis."
    )
    print(
        "  Do not subtract these two numbers. A different judge read a different\n"
        "  genre, and this project has already measured a 3.8-point systematic\n"
        "  shift between two judges on identical text. Bridge the judge first."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
