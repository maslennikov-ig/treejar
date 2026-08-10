"""The blind raw panel must never receive the frozen applicability map."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

SCRIPT = pathlib.Path("scripts/e2e_acceptance/prepare_map_free_panel.py")


def test_prepared_inputs_keep_only_transcripts(tmp_path: pathlib.Path) -> None:
    """Catch leaking rule_applicability into a supposedly map-free read."""
    source = tmp_path / "source"
    split = tmp_path / "split.json"
    output = tmp_path / "output"
    assignments = {"readerA": ["P01"], "readerB": ["P01"]}
    split.write_text(json.dumps(assignments), encoding="utf-8")
    for reader in assignments:
        reader_dir = source / reader
        reader_dir.mkdir(parents=True)
        (reader_dir / "_input.json").write_text(
            json.dumps(
                {
                    "P01": {
                        "transcript": ["Customer: hello", "Noor: hello"],
                        "rule_applicability": {"1": True, "15": False},
                    }
                }
            ),
            encoding="utf-8",
        )

    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--source",
            str(source),
            "--split",
            str(split),
            "--output",
            str(output),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    for reader in assignments:
        payload = json.loads((output / reader / "_input.json").read_text())
        assert payload == {"P01": {"transcript": ["Customer: hello", "Noor: hello"]}}
    manifest = json.loads((output / "assignment-manifest.json").read_text())
    assert manifest["packets"] == 1
    assert manifest["reads"] == 2
    assert manifest["max_packets_per_reader"] == 1
