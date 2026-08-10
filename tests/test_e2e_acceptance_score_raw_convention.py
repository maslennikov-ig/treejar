"""The bridge to the client's ruler, and the two ways it can lie.

The client scores all fifteen criteria on every dialogue and lets an unearned
one stand at zero; we drop what did not apply and stretch the rest back to /30.
Our 20.02 and their 6.05 were never the same measurement. These tests hold the
bridge to the client's convention exactly, because the moment it drifts the
comparison stops meaning anything and nothing visibly breaks.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from scripts.e2e_acceptance.score_raw_convention import _read, _scenario_of, main

from src.quality.schemas import RULE_NAMES, CriterionScore, raw_total


def _criterion(rule: int, score: int, *, applicable: bool = True) -> CriterionScore:
    return CriterionScore(
        rule_number=rule,
        rule_name=RULE_NAMES[rule],
        score=score,
        comment="",
        applicable=applicable,
    )


def test_a_rule_that_did_not_apply_still_counts_as_zero() -> None:
    """This is the whole difference between the two rulers.

    `calculate_weighted_score` would drop the twelve and renormalise the rest
    upward. The client lets it stand at zero, and so does this.
    """

    criteria = [_criterion(rule, 2) for rule in range(1, 4)]
    criteria += [_criterion(rule, 0, applicable=False) for rule in range(4, 16)]

    assert raw_total(criteria) == 6


def test_a_perfect_conversation_is_thirty() -> None:
    assert raw_total([_criterion(rule, 2) for rule in range(1, 16)]) == 30


def test_nothing_earned_is_zero() -> None:
    assert raw_total([_criterion(rule, 0) for rule in range(1, 16)]) == 0
    assert raw_total([]) == 0


def test_an_applicable_rule_scored_zero_and_an_inapplicable_one_agree() -> None:
    """Deliberate, and the reason the gap is a claim about openings.

    On the stored 8b75888 run rules 12, 14 and 15 were applicable in 2 reads of
    106. A reader handed a frozen map saying "not applicable" never went looking,
    so on this axis those zeros are unexamined rather than earned. The arithmetic
    cannot tell the two apart -- only the applicability count printed beside it
    can, which is why the report prints it.
    """

    earned = [_criterion(12, 0)] + [_criterion(r, 2) for r in range(1, 12)]
    unexamined = [_criterion(12, 0, applicable=False)] + [
        _criterion(r, 2) for r in range(1, 12)
    ]

    assert raw_total(earned) == raw_total(unexamined)


@pytest.mark.parametrize(
    ("packet", "scenario"),
    [
        ("S01-r1", "S01"),
        ("R07-r3", "R07"),
        ("S09-r1", "S09"),
        # A packet that carries no repeat suffix is its own scenario rather than
        # silently joining another one.
        ("S01", "S01"),
    ],
)
def test_repeats_collapse_onto_their_scenario(packet: str, scenario: str) -> None:
    assert _scenario_of(packet) == scenario


def _write_reader_file(
    directory: pathlib.Path, packet: str, scores: dict[int, int]
) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{packet}.json").write_text(
        json.dumps(
            {
                "scenario": packet,
                "criteria": [
                    {
                        "rule_number": rule,
                        "score": scores.get(rule, 0),
                        "applicable": rule in scores,
                        "n_a": rule not in scores,
                        "comment": "",
                        "evidence": [],
                    }
                    for rule in range(1, 16)
                ],
            }
        ),
        encoding="utf-8",
    )


def test_a_reader_file_round_trips_into_the_client_total(
    tmp_path: pathlib.Path,
) -> None:
    _write_reader_file(tmp_path / "readerA", "S01-r1", {1: 2, 2: 2, 7: 1})

    criteria = _read(tmp_path / "readerA" / "S01-r1.json")

    assert len(criteria) == 15
    assert raw_total(criteria) == 5


def test_the_report_clusters_by_scenario_not_by_packet(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Three repeats of one scenario are one observation, not three.

    Counting them as three would shrink the interval by sqrt(3) it has not
    earned. The stored run is 53 packets and 19 scenarios; if this ever prints
    53 the interval on every client-facing number is wrong.
    """

    scores = tmp_path / "scores"
    for repeat in (1, 2, 3):
        _write_reader_file(scores / "readerA", f"S01-r{repeat}", {1: 2, 2: 2})
        _write_reader_file(scores / "readerB", f"S01-r{repeat}", {1: 2, 2: 2})
    _write_reader_file(scores / "readerA", "R01-r1", {1: 2})
    _write_reader_file(scores / "readerB", "R01-r1", {1: 2})

    import sys

    argv = sys.argv
    sys.argv = ["score_raw_convention", "--scores", str(scores)]
    try:
        assert main() == 0
    finally:
        sys.argv = argv

    out = capsys.readouterr().out
    assert "4 packets over 2 scenarios" in out
    assert "8 blind reads" in out


def test_the_report_refuses_to_subtract_the_client_figure(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The client's 6.05 came from a different judge on a different genre, and
    this project has already measured a 3.8-point shift between two judges on
    identical text. The tool prints their number for orientation and refuses the
    subtraction in as many words."""

    scores = tmp_path / "scores"
    _write_reader_file(scores / "readerA", "S01-r1", {1: 2})
    _write_reader_file(scores / "readerB", "S01-r1", {1: 2})

    import sys

    argv = sys.argv
    sys.argv = ["score_raw_convention", "--scores", str(scores)]
    try:
        assert main() == 0
    finally:
        sys.argv = argv

    out = capsys.readouterr().out
    assert "Do not subtract these two numbers" in out
    assert "6.05" in out


def test_a_missing_scores_directory_fails_loudly(tmp_path: pathlib.Path) -> None:
    import sys

    argv = sys.argv
    sys.argv = ["score_raw_convention", "--scores", str(tmp_path / "nope")]
    try:
        assert main() == 2
    finally:
        sys.argv = argv
