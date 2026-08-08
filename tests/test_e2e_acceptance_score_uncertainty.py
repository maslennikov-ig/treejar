"""The acceptance mean, with the part of it that is the judge separated out.

The numbers that matter here were measured, not invented: one unchanged S03
transcript scored five times returned 15.2, 16.2, 21.5, 21.6 and 23.9, and
those five figures are the only real datum in this file. Everything else is
synthetic -- no captured wording, identifier or customer datum belongs in a
test.

The score-file fixtures come in the two shapes the protected tree actually
holds: before 2026-08-03 the evaluator returned points on the nominal block
weight and the report normalised by hand, and from ``808b07d`` on it normalises
itself. Both have to land on the same /30 axis, and the newer one must not be
normalised twice.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from scripts.e2e_acceptance.score_uncertainty import (
    RunEstimate,
    ScenarioSamples,
    ScoreFileError,
    compare_runs,
    estimate_run,
    format_comparison,
    format_run,
    load_run,
    read_comparable_score,
    t_critical_95,
)

MEASURED_S03_RESCORINGS = (15.2, 16.2, 21.5, 21.6, 23.9)

_BLOCK_WEIGHTS = (("Opening & Trust", 6.0, 4), ("Relationship", 9.0, 5))
_FULL_BLOCKS = (
    ("Opening & Trust", 6.0, 4),
    ("Relationship", 9.0, 5),
    ("Consultative Solution", 9.0, 3),
    ("Conversion & Next Step", 6.0, 3),
)


def _score_file(
    *,
    fraction: float,
    dropped_block: str | None = None,
    normalised: bool,
    blocks: tuple[tuple[str, float, int], ...] = _FULL_BLOCKS,
) -> dict[str, Any]:
    """One score file, at ``fraction`` of the points available to it.

    ``dropped_block`` is a block the evaluator marked wholly non-applicable,
    which is what makes a scenario's comparable score differ from its raw one.
    ``normalised`` chooses between the two shapes: with it, the evaluator has
    already rescaled the remaining blocks to 30 and written the scale it used
    into ``normalized_weight``.
    """

    applicable = [block for block in blocks if block[0] != dropped_block]
    nominal = sum(weight for _name, weight, _rules in applicable)
    scale = 30.0 / nominal if normalised else 1.0

    block_scores: list[dict[str, Any]] = []
    for name, weight, rules in blocks:
        if name == dropped_block:
            block_scores.append(
                {
                    "block_name": name,
                    "weight": weight,
                    "points": 0.0,
                    "applicable_rules": 0,
                }
                | ({"normalized_weight": 0.0} if normalised else {})
            )
            continue
        entry: dict[str, Any] = {
            "block_name": name,
            "weight": weight,
            "points": weight * scale * fraction,
            "applicable_rules": rules,
        }
        if normalised:
            entry["normalized_weight"] = weight * scale
        block_scores.append(entry)
    return {
        "total_score": sum(b["points"] for b in block_scores),
        "block_scores": block_scores,
    }


def test_the_older_shape_is_normalised_the_way_the_reports_did_it_by_hand() -> None:
    """Before 2026-08-03 the points were on the nominal weight of 24."""

    payload = _score_file(
        fraction=0.5, dropped_block="Conversion & Next Step", normalised=False
    )

    assert payload["total_score"] == pytest.approx(12.0)
    assert read_comparable_score(payload) == pytest.approx(15.0)


def test_the_newer_shape_is_not_normalised_a_second_time() -> None:
    """This is the defect the reports carried: 808b07d moved the division
    into the evaluator and the reports kept doing it as well, so every mean
    published on 2026-08-07 was multiplied by 30/24 twice."""

    payload = _score_file(
        fraction=0.5, dropped_block="Conversion & Next Step", normalised=True
    )

    assert payload["total_score"] == pytest.approx(15.0)
    assert read_comparable_score(payload) == pytest.approx(15.0)


def test_both_shapes_agree_when_every_block_applies() -> None:
    older = _score_file(fraction=0.75, normalised=False)
    newer = _score_file(fraction=0.75, normalised=True)

    assert read_comparable_score(older) == pytest.approx(22.5)
    assert read_comparable_score(newer) == pytest.approx(22.5)


def test_a_scenario_too_sparse_to_normalise_is_refused_rather_than_inflated() -> None:
    """The evaluator withholds the /30 scale below eight applicable rules or
    three applicable blocks, because normalising there inflates the score. A
    reader that normalised anyway would undo that guard."""

    payload = _score_file(fraction=1.0, normalised=True, blocks=_BLOCK_WEIGHTS)

    with pytest.raises(ScoreFileError, match="coverage"):
        read_comparable_score(payload)


def test_a_score_file_with_no_blocks_is_refused() -> None:
    with pytest.raises(ScoreFileError):
        read_comparable_score({"total_score": 18.2})


def test_the_multiplier_is_rounded_down_to_a_tabulated_row() -> None:
    """A reader is never handed a narrower interval than the theory allows."""

    assert t_critical_95(1) == 12.706
    assert t_critical_95(4) == 2.776
    assert t_critical_95(30) == 2.042
    assert t_critical_95(35) == 2.042
    assert t_critical_95(40) == 2.021
    assert t_critical_95(10_000) == 1.980

    with pytest.raises(ValueError):
        t_critical_95(0)


def test_the_five_measured_rescorings_carry_the_spread_that_started_this() -> None:
    sample = ScenarioSamples(scenario="S03", scores=MEASURED_S03_RESCORINGS)

    assert sample.repeats == 5
    assert sample.mean == pytest.approx(19.68)
    assert sample.median == pytest.approx(21.5)
    assert sample.sd == pytest.approx(3.8, abs=0.05)
    assert sample.spread == pytest.approx(8.7)


def test_a_single_score_has_a_mean_and_no_deviation() -> None:
    sample = ScenarioSamples(scenario="S06", scores=(12.0,))

    assert sample.mean == 12.0
    assert sample.sd is None
    assert sample.spread == 0.0


def test_a_scenario_with_no_scores_is_rejected() -> None:
    with pytest.raises(ValueError):
        ScenarioSamples(scenario="S01", scores=())


def _two_scenario_run(label: str, offset: float = 0.0) -> RunEstimate:
    """Two scenarios, each scored twice four points apart.

    Each deviation is sqrt(8), so the pooled judge sd is sqrt(8) on two degrees
    of freedom, the standard error of the mean is sqrt(8) * sqrt(1) / 2, and
    the interval is 4.303 times that.
    """

    return estimate_run(
        label,
        [
            ScenarioSamples(scenario="S01", scores=(10.0 + offset, 14.0 + offset)),
            ScenarioSamples(scenario="S02", scores=(20.0 + offset, 24.0 + offset)),
        ],
    )


def test_the_mean_carries_the_interval_its_own_repeats_justify() -> None:
    run = _two_scenario_run("k=2")

    assert run.mean == pytest.approx(17.0)
    assert run.degrees_of_freedom == 2
    assert run.judge_sd == pytest.approx(8**0.5)
    assert run.standard_error == pytest.approx(8**0.5 / 2)
    assert run.half_width == pytest.approx(4.303 * 8**0.5 / 2)


def test_repeating_the_scoring_narrows_the_interval() -> None:
    """Repeats do not make the judge quieter; they make its mean better known,
    which is the whole reason tj-swgu.9 exists."""

    twice = estimate_run("k=2", [ScenarioSamples(scenario="S03", scores=(15.2, 23.9))])
    five_times = estimate_run(
        "k=5", [ScenarioSamples(scenario="S03", scores=MEASURED_S03_RESCORINGS)]
    )

    assert five_times.half_width is not None
    assert twice.half_width is not None
    assert five_times.half_width < twice.half_width


def test_a_run_scored_once_has_no_uncertainty_to_offer() -> None:
    run = estimate_run(
        "single pass",
        [
            ScenarioSamples(scenario="S01", scores=(18.0,)),
            ScenarioSamples(scenario="S02", scores=(12.0,)),
        ],
    )

    assert run.mean == pytest.approx(15.0)
    assert run.degrees_of_freedom == 0
    assert run.judge_sd is None
    assert run.half_width is None
    assert run.scenario_half_width("S01") is None
    assert "cannot carry a conclusion" in format_run(run)


def test_a_run_with_no_scenarios_is_rejected() -> None:
    with pytest.raises(ValueError):
        estimate_run("empty", [])


def test_a_movement_smaller_than_its_own_noise_is_not_a_finding() -> None:
    """18.0, 18.5 and 18.2 were three builds and one number. This is the rule
    that says so before a report does."""

    comparison = compare_runs(
        _two_scenario_run("before"), _two_scenario_run("after", 0.5)
    )

    assert comparison.delta == pytest.approx(0.5)
    assert comparison.half_width is not None
    assert comparison.half_width > 0.5
    assert comparison.conclusive is False
    assert all(item.conclusive is False for item in comparison.scenarios)
    assert "one number, not two" in format_comparison(comparison)


def test_a_movement_larger_than_its_own_noise_is_readable_as_one() -> None:
    comparison = compare_runs(
        _two_scenario_run("before"), _two_scenario_run("after", 12.0)
    )

    assert comparison.delta == pytest.approx(12.0)
    assert comparison.conclusive is True
    assert all(item.conclusive is True for item in comparison.scenarios)
    assert "readable as a difference" in format_comparison(comparison)


def test_comparing_runs_scored_once_each_offers_no_verdict() -> None:
    before = estimate_run("before", [ScenarioSamples(scenario="S01", scores=(18.0,))])
    after = estimate_run("after", [ScenarioSamples(scenario="S01", scores=(24.0,))])

    comparison = compare_runs(before, after)

    assert comparison.delta == pytest.approx(6.0)
    assert comparison.half_width is None
    assert comparison.conclusive is False

    rendered = format_comparison(comparison)
    assert "is not a finding" in rendered
    assert "Neither run repeats" in rendered
    assert "not measurable" in rendered
    assert "inside the noise" not in rendered
    assert comparison.disagreement is None


def test_repeats_on_one_side_only_still_refuse_a_verdict() -> None:
    """A repeated reading and a single one are two different instruments. The
    one that repeats knows its own noise and says so; it cannot lend that
    estimate to the one that does not."""

    once = estimate_run("single pass", [ScenarioSamples("S01", (18.0,))])
    repeated = estimate_run("five readers", [ScenarioSamples("S01", (12.0, 12.4))])

    comparison = compare_runs(once, repeated)

    assert repeated.half_width is not None
    assert comparison.half_width is None
    assert comparison.conclusive is False

    rendered = format_comparison(comparison)
    assert "single pass does not repeat" in rendered
    assert "Neither run repeats" not in rendered


def test_two_readings_of_one_run_report_their_disagreement_without_repeats() -> None:
    """When the judge is a reader rather than a rerun, the uncertainty that
    can still be measured is how far two readers of the same transcripts sit
    apart -- a systematic offset, and a scenario-by-scenario spread on top."""

    before = estimate_run(
        "judge A",
        [
            ScenarioSamples(scenario="S01", scores=(20.0,)),
            ScenarioSamples(scenario="S02", scores=(10.0,)),
            ScenarioSamples(scenario="S03", scores=(15.0,)),
        ],
    )
    after = estimate_run(
        "judge B",
        [
            ScenarioSamples(scenario="S01", scores=(16.0,)),
            ScenarioSamples(scenario="S02", scores=(8.0,)),
            ScenarioSamples(scenario="S03", scores=(9.0,)),
        ],
    )

    comparison = compare_runs(before, after)

    assert comparison.delta == pytest.approx(-4.0)
    assert comparison.disagreement == pytest.approx(2.0)
    assert "2.0 more scenario to scenario" in format_comparison(comparison)


def test_runs_over_different_scenarios_are_refused_rather_than_aligned() -> None:
    before = _two_scenario_run("before")
    after = estimate_run(
        "after", [ScenarioSamples(scenario="S01", scores=(10.0, 14.0))]
    )

    with pytest.raises(ValueError, match="same scenarios"):
        compare_runs(before, after)


def test_repeats_are_read_from_the_files_a_run_directory_holds(
    tmp_path: Path,
) -> None:
    """A rescored scenario writes another file beside the first one."""

    (tmp_path / "S01-score.json").write_text(
        json.dumps(_score_file(fraction=0.5, normalised=True)), encoding="utf-8"
    )
    (tmp_path / "S01-score-r2.json").write_text(
        json.dumps(_score_file(fraction=0.75, normalised=True)), encoding="utf-8"
    )
    (tmp_path / "S02-score.json").write_text(
        json.dumps(_score_file(fraction=1.0, normalised=True)), encoding="utf-8"
    )
    (tmp_path / "S01.json").write_text(
        json.dumps({"scenario": "S01", "turns": []}), encoding="utf-8"
    )

    run = load_run(tmp_path)

    assert [sample.scenario for sample in run.scenarios] == ["S01", "S02"]
    assert run.scenarios[0].repeats == 2
    assert sorted(run.scenarios[0].scores) == pytest.approx([15.0, 22.5])
    assert run.scenarios[1].repeats == 1
    assert run.label == tmp_path.name


def test_a_directory_with_no_score_files_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ScoreFileError):
        load_run(tmp_path)


def test_the_report_line_states_the_rule_it_expects_to_be_followed() -> None:
    rendered = format_run(_two_scenario_run("k=2"))

    assert "+/-" in rendered
    assert "No conclusion is drawn from a movement smaller than" in rendered
    assert "judge sd" in rendered
