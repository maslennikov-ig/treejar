"""Pairing two rounds refuses the comparisons that would not mean anything."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "scripts" / "corpus_bridge" / "pair_rounds.py"
)
_spec = importlib.util.spec_from_file_location("pair_rounds", MODULE_PATH)
assert _spec is not None and _spec.loader is not None
pair_rounds = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pair_rounds)


def _run(root: Path, name: str, *, judge: str, digest: str, scores: dict[int, int]):
    run_dir = root / name
    run_dir.mkdir()
    (run_dir / "preflight.json").write_text(
        json.dumps({"judge_model": judge, "scenario_digest": digest})
    )
    (run_dir / "analysis.json").write_text(
        json.dumps(
            {
                "scenarios": [
                    {
                        "dialog_id": dialog_id,
                        "length_stratum": 1,
                        "weighted_score_tenths": score,
                        "raw_total": score // 10,
                        "critical_failure_count": 0,
                    }
                    for dialog_id, score in scores.items()
                ]
            }
        )
    )
    return run_dir


def test_pairing_across_judges_is_refused(tmp_path: Path) -> None:
    """Two judges have been measured 3.8 points apart on identical text.

    A delta taken across them is a judge difference wearing a build's name, so
    the tool refuses rather than reports it with a caveat nobody reads.
    """

    before = _run(tmp_path, "a", judge="root-orchestrator", digest="d", scores={1: 10})
    after = _run(tmp_path, "b", judge="z-ai/glm-5.2", digest="d", scores={1: 20})

    with pytest.raises(SystemExit, match="across judges"):
        pair_rounds.pair(before, after)


def test_pairing_across_frozen_sets_is_refused(tmp_path: Path) -> None:
    before = _run(tmp_path, "a", judge="root", digest="one", scores={1: 10})
    after = _run(tmp_path, "b", judge="root", digest="two", scores={1: 20})

    with pytest.raises(SystemExit, match="different frozen sets"):
        pair_rounds.pair(before, after)


def test_a_partial_overlap_is_refused_rather_than_silently_shrunk(
    tmp_path: Path,
) -> None:
    """Dropping the openings one round is missing would flatter whichever
    round lost them, and the count in the report would still read twenty."""

    before = _run(tmp_path, "a", judge="root", digest="d", scores={1: 10, 2: 10})
    after = _run(tmp_path, "b", judge="root", digest="d", scores={1: 20, 3: 20})

    with pytest.raises(SystemExit, match="same openings"):
        pair_rounds.pair(before, after)


def test_the_paired_delta_is_the_mean_of_the_per_opening_differences(
    tmp_path: Path,
) -> None:
    before = _run(tmp_path, "a", judge="root", digest="d", scores={1: 100, 2: 200})
    after = _run(tmp_path, "b", judge="root", digest="d", scores={1: 120, 2: 180})

    result = pair_rounds.pair(before, after)

    assert result["scenario_count"] == 2
    assert result["weighted_delta_on_30_scale"]["mean"] == pytest.approx(0.0)
    assert {
        item["dialog_id"]: item["weighted_delta_tenths"] for item in result["pairs"]
    } == {
        1: 20,
        2: -20,
    }


def test_a_bootstrap_of_identical_rounds_has_no_spread(tmp_path: Path) -> None:
    before = _run(tmp_path, "a", judge="root", digest="d", scores={1: 100, 2: 200})
    after = _run(tmp_path, "b", judge="root", digest="d", scores={1: 100, 2: 200})

    weighted = pair_rounds.pair(before, after)["weighted_delta_on_30_scale"]

    assert weighted == {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0}
