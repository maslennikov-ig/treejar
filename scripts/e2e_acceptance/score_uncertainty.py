"""What the acceptance mean is, and how much of it is the instrument.

One unchanged S03 transcript, scored five times against the same stored
conversation with no live traffic and not a byte of difference, came back
``15.2  16.2  21.5  21.6  23.9``. Three acceptance runs on materially different
builds then scored 18.0, 18.5 and 18.2 -- one number wearing three hats. The
reports read per-scenario deltas out of that as evidence about code, and they
are not: S03 moved 25.4 -> 28.9 -> 17.6 across three runs on a path nobody
touched.

This module is the correction. Point it at a run directory of score files, and
it reports the mean with the interval the repeats actually justify, plus the
rule that follows from it: **a delta smaller than its own uncertainty is not a
finding.** Two run directories can be compared, and the comparison says
outright whether the difference survives the noise.

It also fixes the scale. ``comparable`` has always meant "drop the wholly
non-applicable blocks and normalise the rest to 30", and until 2026-08-03 the
evaluator returned points on the nominal block weight, so the reports did that
normalisation by hand. Commit ``808b07d`` moved it into the evaluator --
``normalized_weight`` appears in the score file from then on -- and the reports
kept multiplying anyway. :func:`read_comparable_score` reads the scale off the
file instead of assuming one, so both shapes land on the same /30 axis.

No message text, customer datum or identifier passes through here: it reads
``block_scores`` and ``diagnostics``, and reports numbers.
"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import fmean, median
from typing import Any

COMPARABLE_SCALE = 30.0
"""Every published acceptance score is on a /30 axis."""

CONFIDENCE = 0.95

_SCORE_FILE = re.compile(r"^(?P<scenario>[^-]+)-score(?:[-.].*)?$")

# Two-sided 95% critical values of Student's t. A lookup keeps the arithmetic
# auditable and avoids a numerical dependency for one number; degrees of
# freedom are rounded *down* to a tabulated row, so the interval a reader is
# handed is never narrower than the theory allows.
_T_95: tuple[tuple[int, float], ...] = (
    (1, 12.706),
    (2, 4.303),
    (3, 3.182),
    (4, 2.776),
    (5, 2.571),
    (6, 2.447),
    (7, 2.365),
    (8, 2.306),
    (9, 2.262),
    (10, 2.228),
    (11, 2.201),
    (12, 2.179),
    (13, 2.160),
    (14, 2.145),
    (15, 2.131),
    (16, 2.120),
    (17, 2.110),
    (18, 2.101),
    (19, 2.093),
    (20, 2.086),
    (21, 2.080),
    (22, 2.074),
    (23, 2.069),
    (24, 2.064),
    (25, 2.060),
    (26, 2.056),
    (27, 2.052),
    (28, 2.048),
    (29, 2.045),
    (30, 2.042),
    (40, 2.021),
    (50, 2.009),
    (60, 2.000),
    (80, 1.990),
    (100, 1.984),
    (120, 1.980),
)
_T_95_INFINITY = 1.960


class ScoreFileError(ValueError):
    """A score file is not on a scale this module can put on the /30 axis."""


def t_critical_95(degrees_of_freedom: int) -> float:
    """The two-sided 95% multiplier, rounded down to a tabulated row."""

    if degrees_of_freedom < 1:
        raise ValueError("a confidence interval needs at least one degree of freedom")
    chosen = _T_95_INFINITY
    for tabulated, value in _T_95:
        if tabulated <= degrees_of_freedom:
            chosen = value
        else:
            break
    return chosen


@dataclass(frozen=True, slots=True)
class ScenarioSamples:
    """Every score one scenario received, and what they say between them."""

    scenario: str
    scores: tuple[float, ...]

    def __post_init__(self) -> None:
        if not self.scores:
            raise ValueError(f"{self.scenario} has no scores")

    @property
    def repeats(self) -> int:
        return len(self.scores)

    @property
    def mean(self) -> float:
        return fmean(self.scores)

    @property
    def median(self) -> float:
        return median(self.scores)

    @property
    def spread(self) -> float:
        return max(self.scores) - min(self.scores)

    @property
    def sd(self) -> float | None:
        """The scenario's own sample deviation, or None at a single score."""

        if self.repeats < 2:
            return None
        centre = self.mean
        variance = sum((score - centre) ** 2 for score in self.scores) / (
            self.repeats - 1
        )
        return sqrt(variance)


@dataclass(frozen=True, slots=True)
class RunEstimate:
    """A run's mean, and the interval its own repeats justify.

    The scenario set is fixed rather than sampled, so the only uncertainty on
    this mean is the judge re-reading the same transcripts. Judge noise is
    pooled across scenarios: it is a property of the instrument, and pooling
    buys the degrees of freedom that ten scenarios at three repeats each cannot
    reach one scenario at a time. Each scenario's own deviation is reported
    beside it, so a scenario the judge finds harder than the rest is visible
    rather than averaged away.
    """

    label: str
    scenarios: tuple[ScenarioSamples, ...]

    def __post_init__(self) -> None:
        if not self.scenarios:
            raise ValueError(f"{self.label} has no scenarios")

    @property
    def mean(self) -> float:
        return fmean(sample.mean for sample in self.scenarios)

    @property
    def degrees_of_freedom(self) -> int:
        return sum(sample.repeats - 1 for sample in self.scenarios)

    @property
    def judge_sd(self) -> float | None:
        """One pooled within-scenario deviation, or None with no repeats."""

        df = self.degrees_of_freedom
        if df < 1:
            return None
        pooled = (
            sum(
                (sample.repeats - 1) * (sd**2)
                for sample in self.scenarios
                if (sd := sample.sd) is not None
            )
            / df
        )
        return sqrt(pooled)

    @property
    def standard_error(self) -> float | None:
        """The standard error of the run mean under the pooled judge noise."""

        judge_sd = self.judge_sd
        if judge_sd is None:
            return None
        return (
            judge_sd
            * sqrt(sum(1.0 / sample.repeats for sample in self.scenarios))
            / len(self.scenarios)
        )

    @property
    def half_width(self) -> float | None:
        """Half the 95% interval on the mean, or None when nothing repeats."""

        standard_error = self.standard_error
        if standard_error is None:
            return None
        return t_critical_95(self.degrees_of_freedom) * standard_error

    def scenario_half_width(self, scenario: str) -> float | None:
        """Half the 95% interval on one scenario, on the same pooled noise."""

        judge_sd = self.judge_sd
        if judge_sd is None:
            return None
        sample = self._sample(scenario)
        return t_critical_95(self.degrees_of_freedom) * judge_sd / sqrt(sample.repeats)

    def _sample(self, scenario: str) -> ScenarioSamples:
        for sample in self.scenarios:
            if sample.scenario == scenario:
                return sample
        raise KeyError(scenario)


@dataclass(frozen=True, slots=True)
class ScenarioDelta:
    """One scenario's movement between two runs, against its own noise."""

    scenario: str
    baseline: float
    candidate: float
    half_width: float | None

    @property
    def delta(self) -> float:
        return self.candidate - self.baseline

    @property
    def conclusive(self) -> bool:
        """False whenever the movement is inside what the judge invents."""

        return self.half_width is not None and abs(self.delta) > self.half_width


@dataclass(frozen=True, slots=True)
class RunComparison:
    """Two runs on the same scenarios, and whether they actually differ."""

    baseline: RunEstimate
    candidate: RunEstimate
    delta: float
    half_width: float | None
    scenarios: tuple[ScenarioDelta, ...]

    @property
    def conclusive(self) -> bool:
        return self.half_width is not None and abs(self.delta) > self.half_width

    @property
    def disagreement(self) -> float | None:
        """How much the per-scenario deltas vary around their own mean.

        Two readings of the same ten transcripts differ in two ways, and they
        are worth separating: :attr:`delta` is the systematic part, one reader
        being harsher than the other across the board, and this is the part
        that moves scenario by scenario. Neither needs repeats to be measured,
        which is why this is reported even when no interval can be.
        """

        if len(self.scenarios) < 2:
            return None
        deltas = [item.delta for item in self.scenarios]
        centre = fmean(deltas)
        return sqrt(sum((delta - centre) ** 2 for delta in deltas) / (len(deltas) - 1))


def _applicable_blocks(
    block_scores: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    return [
        block
        for block in block_scores
        if isinstance(block.get("applicable_rules"), int)
        and block["applicable_rules"] > 0
    ]


def _is_low_coverage(applicable: Sequence[Mapping[str, Any]]) -> bool:
    """The evaluator's own rule, recomputed so both file shapes answer it.

    ``diagnostics`` only exists from 2026-08-03 on, and the guard it encodes --
    a scenario too sparsely applicable to be normalised without inflating it --
    has to hold for the older files too.
    """

    applicable_rules = sum(int(block["applicable_rules"]) for block in applicable)
    return applicable_rules < 8 or len(applicable) < 3


def read_comparable_score(payload: Mapping[str, Any]) -> float:
    """One score file's number on the /30 comparable axis.

    The scale is read off the file rather than assumed. ``normalized_weight``
    means the evaluator already normalised and the points are on /30;
    its absence means they are on the nominal block weight and the report used
    to do the division by hand. Dividing by whichever weight the points were
    actually earned against gets both onto one axis, and stops the newer files
    being normalised a second time.
    """

    block_scores = payload.get("block_scores")
    if not isinstance(block_scores, list) or not block_scores:
        raise ScoreFileError("score file carries no block_scores")
    blocks = [block for block in block_scores if isinstance(block, Mapping)]
    applicable = _applicable_blocks(blocks)
    if not applicable:
        raise ScoreFileError("no block in the score file is applicable")
    if _is_low_coverage(applicable):
        raise ScoreFileError(
            "coverage is too low to normalise: the evaluator withholds the /30 "
            "scale for this scenario and so does this reader"
        )

    scale = sum(
        float(
            block["normalized_weight"]
            if isinstance(block.get("normalized_weight"), int | float)
            and block["normalized_weight"]
            else block["weight"]
        )
        for block in applicable
    )
    if scale <= 0:
        raise ScoreFileError("applicable blocks carry no weight")
    points = sum(float(block.get("points", 0.0)) for block in blocks)
    return points / scale * COMPARABLE_SCALE


def estimate_run(label: str, samples: Iterable[ScenarioSamples]) -> RunEstimate:
    return RunEstimate(
        label=label,
        scenarios=tuple(sorted(samples, key=lambda sample: sample.scenario)),
    )


def compare_runs(baseline: RunEstimate, candidate: RunEstimate) -> RunComparison:
    """Compare two runs scenario by scenario, paired on the scenario set.

    The scenarios are the same ten transcripts both times, so the comparison is
    paired and the between-scenario spread -- much the larger number, and the
    same in both runs -- cancels instead of drowning the difference.
    """

    baseline_ids = tuple(sample.scenario for sample in baseline.scenarios)
    candidate_ids = tuple(sample.scenario for sample in candidate.scenarios)
    if baseline_ids != candidate_ids:
        raise ValueError(
            "runs must cover the same scenarios to be compared: "
            f"{baseline.label} has {baseline_ids}, {candidate.label} has "
            f"{candidate_ids}"
        )

    baseline_sd = baseline.judge_sd
    candidate_sd = candidate.judge_sd
    degrees_of_freedom = baseline.degrees_of_freedom + candidate.degrees_of_freedom
    paired: list[ScenarioDelta] = []
    variance = 0.0
    measurable = baseline_sd is not None and candidate_sd is not None
    multiplier = t_critical_95(degrees_of_freedom) if measurable else None

    for before, after in zip(baseline.scenarios, candidate.scenarios, strict=True):
        half_width: float | None = None
        if baseline_sd is not None and candidate_sd is not None:
            scenario_variance = (
                baseline_sd**2 / before.repeats + candidate_sd**2 / after.repeats
            )
            variance += scenario_variance
            assert multiplier is not None
            half_width = multiplier * sqrt(scenario_variance)
        paired.append(
            ScenarioDelta(
                scenario=before.scenario,
                baseline=before.mean,
                candidate=after.mean,
                half_width=half_width,
            )
        )

    count = len(paired)
    mean_half_width = (
        multiplier * sqrt(variance) / count if multiplier is not None else None
    )
    return RunComparison(
        baseline=baseline,
        candidate=candidate,
        delta=candidate.mean - baseline.mean,
        half_width=mean_half_width,
        scenarios=tuple(paired),
    )


def load_run(directory: Path, label: str | None = None) -> RunEstimate:
    """Read every score file in a run directory, grouped by scenario.

    A scenario scored more than once writes more than one file --
    ``S03-score.json`` beside ``S03-score-r2.json`` -- and every one of them
    counts as a repeat of that scenario.
    """

    samples: dict[str, list[float]] = {}
    for path in sorted(directory.glob("*-score*.json")):
        match = _SCORE_FILE.match(path.stem)
        if not match:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            continue
        samples.setdefault(match.group("scenario"), []).append(
            read_comparable_score(payload)
        )
    if not samples:
        raise ScoreFileError(f"no score files under {directory}")
    return estimate_run(
        label or directory.name,
        (
            ScenarioSamples(scenario=scenario, scores=tuple(scores))
            for scenario, scores in samples.items()
        ),
    )


def _number(value: float | None, width: int = 6) -> str:
    return f"{value:>{width}.1f}" if value is not None else " " * (width - 1) + "-"


def format_run(run: RunEstimate) -> str:
    lines = [
        run.label,
        f"{'scenario':<10}{'k':>3}{'mean':>7}{'median':>8}{'sd':>7}"
        f"{'range':>7}{'95% CI':>16}",
    ]
    for sample in run.scenarios:
        half_width = run.scenario_half_width(sample.scenario)
        interval = (
            f"{sample.mean - half_width:.1f} .. {sample.mean + half_width:.1f}"
            if half_width is not None
            else "-"
        )
        lines.append(
            f"{sample.scenario:<10}{sample.repeats:>3}{_number(sample.mean, 7)}"
            f"{_number(sample.median, 8)}{_number(sample.sd, 7)}"
            f"{_number(sample.spread, 7)}{interval:>16}"
        )

    half_width = run.half_width
    lines.append("")
    if half_width is None:
        lines.append(
            f"mean {run.mean:.1f}/30 over {len(run.scenarios)} scenarios, scored "
            "once each. No repeats, so no uncertainty: this number cannot carry "
            "a conclusion."
        )
        return "\n".join(lines)

    judge_sd = run.judge_sd
    assert judge_sd is not None
    lines.append(
        f"mean {run.mean:.1f}/30 +/- {half_width:.1f} "
        f"(95%, {len(run.scenarios)} scenarios, "
        f"{sum(s.repeats for s in run.scenarios)} scorings, df "
        f"{run.degrees_of_freedom})"
    )
    lines.append(
        f"judge sd {judge_sd:.1f} per scenario per scoring, pooled across scenarios."
    )
    lines.append(
        f"No conclusion is drawn from a movement smaller than "
        f"{half_width:.1f} on the mean, or than its own interval on a scenario."
    )
    return "\n".join(lines)


def format_comparison(comparison: RunComparison) -> str:
    lines = [
        f"{comparison.baseline.label} -> {comparison.candidate.label}",
        f"{'scenario':<10}{'before':>8}{'after':>8}{'delta':>8}{'+/-':>8}  verdict",
    ]
    for item in comparison.scenarios:
        if item.half_width is None:
            verdict = "not measurable"
        elif item.conclusive:
            verdict = "moved"
        else:
            verdict = "inside the noise"
        lines.append(
            f"{item.scenario:<10}{_number(item.baseline, 8)}"
            f"{_number(item.candidate, 8)}{item.delta:>+8.1f}"
            f"{_number(item.half_width, 8)}  {verdict}"
        )

    lines.append("")
    if comparison.half_width is None:
        without = [
            run.label
            for run in (comparison.baseline, comparison.candidate)
            if run.judge_sd is None
        ]
        which = (
            "Neither run repeats"
            if len(without) == 2
            else f"{without[0]} does not repeat"
        )
        lines.append(
            f"mean {comparison.baseline.mean:.1f} -> {comparison.candidate.mean:.1f} "
            f"({comparison.delta:+.1f}). {which}, so this difference has no "
            "uncertainty to be measured against and is not a finding. Two "
            "different judges do not share a noise estimate, so the repeats of "
            "one cannot stand in for the other."
        )
        disagreement = comparison.disagreement
        if disagreement is not None:
            lines.append(
                f"The two readings differ by {comparison.delta:+.1f} on average "
                f"and by {disagreement:.1f} more scenario to scenario. Both are "
                "measured; neither is a repeat."
            )
        return "\n".join(lines)

    verdict = (
        "larger than the noise, and readable as a difference between the builds"
        if comparison.conclusive
        else "smaller than the noise: these are one number, not two"
    )
    lines.append(
        f"mean {comparison.baseline.mean:.1f} -> {comparison.candidate.mean:.1f}, "
        f"delta {comparison.delta:+.1f} +/- {comparison.half_width:.1f} (95%) -- "
        f"{verdict}."
    )
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "run",
        type=Path,
        help="run directory holding the per-scenario score files",
    )
    parser.add_argument(
        "--against",
        type=Path,
        default=None,
        help="an earlier run directory to compare this one against",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="name for the run in the output; defaults to the directory name",
    )
    parser.add_argument(
        "--against-label",
        default=None,
        help="name for the earlier run in the output",
    )
    args = parser.parse_args(argv)

    run = load_run(args.run, args.label)
    print(format_run(run))
    if args.against is not None:
        baseline = load_run(args.against, args.against_label)
        print()
        print(format_run(baseline))
        print()
        print(format_comparison(compare_runs(baseline, run)))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
