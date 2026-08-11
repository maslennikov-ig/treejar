"""Pair two measured rounds on the frozen set and bootstrap the difference.

Both rounds must be the same twenty openings read by the same judge. Comparing
across judges is refused here for the reason `score_uncertainty.py` already
refuses it: two judges have been measured 3.8 points apart on identical text,
which is half of any gap worth claiming.

The pairing is by `dialog_id`, so the between-opening spread -- much the larger
number -- cancels. The bootstrap resamples openings within their length
stratum, because the frozen set was stratified and the strata have very
different attainable ceilings.

Digests and integers only. No opening, no reply and no amount is written.

    uv run python scripts/corpus_bridge/pair_rounds.py \
        --baseline <protected>/<run> --candidate <protected>/<run> \
        --output <protected>/<run>/paired-comparison.json
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "treejar-real-opening-paired/v1"
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20260810


def _scenarios(run_dir: Path) -> dict[int, dict[str, Any]]:
    analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    return {int(item["dialog_id"]): item for item in analysis["scenarios"]}


def _judge(run_dir: Path) -> str:
    preflight = json.loads((run_dir / "preflight.json").read_text(encoding="utf-8"))
    return str(preflight["judge_model"])


def _scenario_digest(run_dir: Path) -> str:
    preflight = json.loads((run_dir / "preflight.json").read_text(encoding="utf-8"))
    return str(preflight["scenario_digest"])


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def bootstrap_mean(
    deltas: list[tuple[int, float]], *, seed: int, samples: int
) -> dict[str, float]:
    """Mean paired delta and its interval, resampling within length strata."""

    strata: dict[int, list[float]] = {}
    for stratum, delta in deltas:
        strata.setdefault(stratum, []).append(delta)
    total = sum(len(values) for values in strata.values())
    observed = sum(sum(values) for values in strata.values()) / total

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(samples):
        drawn = 0.0
        for values in strata.values():
            drawn += sum(values[rng.randrange(len(values))] for _ in values)
        means.append(drawn / total)
    return {
        "mean": observed,
        "ci95_low": _percentile(means, 0.025),
        "ci95_high": _percentile(means, 0.975),
    }


def pair(baseline_dir: Path, candidate_dir: Path) -> dict[str, Any]:
    baseline_judge, candidate_judge = _judge(baseline_dir), _judge(candidate_dir)
    if baseline_judge != candidate_judge:
        raise SystemExit(
            f"refusing to pair across judges: {baseline_judge} vs {candidate_judge}"
        )
    if _scenario_digest(baseline_dir) != _scenario_digest(candidate_dir):
        raise SystemExit("refusing to pair across different frozen sets")

    before, after = _scenarios(baseline_dir), _scenarios(candidate_dir)
    shared = sorted(set(before) & set(after))
    if len(shared) != len(before) or len(shared) != len(after):
        raise SystemExit("the two rounds do not cover the same openings")

    pairs: list[dict[str, Any]] = []
    weighted: list[tuple[int, float]] = []
    raw: list[tuple[int, float]] = []
    for dialog_id in shared:
        first, second = before[dialog_id], after[dialog_id]
        stratum = int(first["length_stratum"])
        weighted_delta = int(second["weighted_score_tenths"]) - int(
            first["weighted_score_tenths"]
        )
        raw_delta = int(second["raw_total"]) - int(first["raw_total"])
        weighted.append((stratum, weighted_delta / 10))
        raw.append((stratum, float(raw_delta)))
        pairs.append(
            {
                "dialog_id": dialog_id,
                "length_stratum": stratum,
                "weighted_delta_tenths": weighted_delta,
                "raw_delta": raw_delta,
                "baseline_critical_count": int(first["critical_failure_count"]),
                "candidate_critical_count": int(second["critical_failure_count"]),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "judge_model": candidate_judge,
        "baseline_run": baseline_dir.name,
        "candidate_run": candidate_dir.name,
        "scenario_count": len(shared),
        "samples": BOOTSTRAP_SAMPLES,
        "seed": BOOTSTRAP_SEED,
        "weighted_delta_on_30_scale": bootstrap_mean(
            weighted, seed=BOOTSTRAP_SEED, samples=BOOTSTRAP_SAMPLES
        ),
        "raw_total_delta": bootstrap_mean(
            raw, seed=BOOTSTRAP_SEED, samples=BOOTSTRAP_SAMPLES
        ),
        "baseline_critical_count": sum(
            item["baseline_critical_count"] for item in pairs
        ),
        "candidate_critical_count": sum(
            item["candidate_critical_count"] for item in pairs
        ),
        "pairs": pairs,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    result = pair(args.baseline, args.candidate)
    weighted = result["weighted_delta_on_30_scale"]
    raw = result["raw_total_delta"]
    print(f"{result['baseline_run']} -> {result['candidate_run']}")
    print(f"judge {result['judge_model']}, {result['scenario_count']} paired openings")
    print(
        f"weighted delta {weighted['mean']:+.2f} "
        f"(95% {weighted['ci95_low']:+.2f} to {weighted['ci95_high']:+.2f})"
    )
    print(
        f"raw delta      {raw['mean']:+.2f} "
        f"(95% {raw['ci95_low']:+.2f} to {raw['ci95_high']:+.2f})"
    )
    print(
        f"criticals      {result['baseline_critical_count']} -> "
        f"{result['candidate_critical_count']}"
    )
    if args.output is not None:
        args.output.write_text(json.dumps(result, indent=1), encoding="utf-8")
        print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
