"""Freeze real openings without placing their text in tracked artefacts."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path("scripts/corpus_bridge/freeze_opening_scenarios.py")


def _dialog(
    dialog_id: int, opening: str, *, manager: str, score: int, msg_type: str = "text"
) -> dict[str, object]:
    return {
        "dialog_id": dialog_id,
        "manager": manager,
        "messages": [
            {
                "role": "client",
                "type": msg_type,
                "text": opening,
                "sent_at": "2026-01-01T00:00:00+00:00",
            }
        ],
        "evaluation": {"total_score": score},
    }


def test_freeze_selects_length_strata_and_keeps_text_only_under_protected_root(
    tmp_path: pathlib.Path,
) -> None:
    corpus = tmp_path / "dialogs.jsonl"
    protected = tmp_path / "protected"
    template = "template-prefix-that-is-longer-than-forty-eight-characters:"
    dialogs = [
        _dialog(1, template + "a", manager="A", score=1),
        _dialog(2, template + "b", manager="A", score=2),
        _dialog(3, "photo.jpeg", manager="A", score=3),
        _dialog(4, "", manager="B", score=4, msg_type="image"),
    ]
    for index, length in enumerate((2, 5, 8, 13, 21, 34, 55, 89), start=5):
        dialogs.append(
            _dialog(index, "z" * length, manager="A" if index % 2 else "B", score=5)
        )
    corpus.write_text(
        "".join(json.dumps(dialog) + "\n" for dialog in dialogs), encoding="utf-8"
    )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--corpus",
            str(corpus),
            "--protected-root",
            str(protected),
            "--run-id",
            "test-openings",
            "--seed",
            "17",
            "--count",
            "4",
            "--strata",
            "4",
            "--bootstrap-samples",
            "200",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    public = json.loads(completed.stdout)
    assert public["population"] == {
        "with_customer_opening": 12,
        "template": 2,
        "attachment_only": 2,
        "natural_text": 8,
        "evaluated_natural_text": 8,
        "natural_text_median_chars": 17,
    }
    assert len(public["selection"]) == 4
    assert {item["length_stratum"] for item in public["selection"]} == {1, 2, 3, 4}
    assert all(
        set(item)
        == {
            "dialog_id",
            "opener_chars",
            "length_stratum",
            "stored_human_raw_total",
        }
        for item in public["selection"]
    )
    assert "template-prefix" not in completed.stdout
    protected_file = protected / "test-openings" / "scenarios.json"
    full = json.loads(protected_file.read_text())
    assert all("opening" in item for item in full["scenarios"])
    assert protected_file.stat().st_mode & 0o777 == 0o600
