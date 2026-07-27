"""Public runner/CLI boundary regressions for policy v2."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.e2e_acceptance import runner

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI = PROJECT_ROOT / "scripts/run_noor_e2e_acceptance.py"


def test_public_runner_facade_has_no_scenario_specific_implementation() -> None:
    source = inspect.getsource(runner)

    assert "SC-OPEN" not in source
    assert "scenario_id ==" not in source
    assert "scenario_id !=" not in source
    assert not hasattr(runner, "AcceptanceRunner")
    assert runner.FakeLocalAdapter.__doc__


def test_cli_validates_exact_contracts_without_network_path() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(CLI),
            "validate-contracts",
            "--repo-root",
            str(PROJECT_ROOT),
        ],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert '"scenario_count": 20' in completed.stdout
    assert '"evidence_block_count": 9' in completed.stdout
    assert '"criterion_count": 30' in completed.stdout
    assert "fake-local-adapter" in completed.stdout


def test_cli_has_no_live_or_provider_switch() -> None:
    help_result = subprocess.run(
        [sys.executable, str(CLI), "--help"],
        cwd=PROJECT_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    source = CLI.read_text(encoding="utf-8")

    assert help_result.returncode == 0
    assert "--live" not in help_result.stdout
    assert "--provider" not in help_result.stdout
    for forbidden in ("requests", "httpx", "Wazzup", "Zoho", "CRM"):
        assert forbidden not in source


def test_fake_adapter_constructor_rejects_live_identity() -> None:
    with pytest.raises(Exception, match="fake local"):
        runner.FakeLocalAdapter(adapter_id="live-adapter", journal=None)
