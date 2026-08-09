"""The acceptance number is not one number any more, and that is the point."""

from __future__ import annotations

import json
import pathlib

from scripts.e2e_acceptance.score_by_shape import _score_file, _shape_of


def _packet(tmp_path: pathlib.Path, applicability: dict[str, bool]) -> pathlib.Path:
    path = tmp_path / "S01-r1.json"
    path.write_text(json.dumps({"applicability": applicability}), encoding="utf-8")
    return path


def test_the_fork_signature_tells_the_two_shapes_apart(tmp_path: pathlib.Path) -> None:
    """Rules 6, 10 and 13 are charged on a project and not on an order, so the
    applicability map already carries the shape."""

    base = {str(n): True for n in range(1, 16)}
    project = {**base, "6": True, "10": True, "13": True}
    transactional = {**base, "6": False, "10": False, "13": False}

    assert _shape_of(_packet(tmp_path, project)) == "project"
    assert _shape_of(_packet(tmp_path, transactional)) == "transactional"


def test_a_shape_is_reported_with_the_rules_it_was_scored_over(
    tmp_path: pathlib.Path,
) -> None:
    """The denominator travels with the number. Two conversations scored a
    perfect 30 on 2026-08-09 over the eight easy rules alone, and the score
    alone could not say so."""

    path = tmp_path / "R05-r1.json"
    path.write_text(
        json.dumps(
            {
                "criteria": [
                    {
                        "rule_number": n,
                        "score": 2 if n in (1, 2, 3, 4, 5, 7, 8, 9) else 0,
                        "applicable": n in (1, 2, 3, 4, 5, 7, 8, 9),
                        "n_a": n not in (1, 2, 3, 4, 5, 7, 8, 9),
                    }
                    for n in range(1, 16)
                ]
            }
        ),
        encoding="utf-8",
    )

    total, applicable = _score_file(path)

    assert applicable == 8
    # A perfect score over eight rules, which is exactly why it is reported
    # next to the eight rather than on its own.
    assert total == 30.0
