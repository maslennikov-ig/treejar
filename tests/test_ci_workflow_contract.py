from __future__ import annotations

import shlex
from pathlib import Path

import pytest
import yaml


def _load_ci_workflow():
    return yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def _assert_test_job_fetches_full_history(workflow) -> None:
    test_job = workflow["jobs"]["test"]
    run_test_steps = [
        step for step in test_job["steps"] if step.get("name") == "Run tests"
    ]
    assert len(run_test_steps) == 1
    assert shlex.split(run_test_steps[0]["run"]) == [
        "uv",
        "run",
        "pytest",
        "tests/",
        "-v",
        "--tb=short",
    ]

    checkout_steps = [
        step
        for step in test_job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 1
    assert checkout_steps[0].get("with", {}).get("fetch-depth") == "0"


def test_ci_workflow_skips_docs_and_orchestration_only_changes() -> None:
    workflow = _load_ci_workflow()

    expected_ignored_paths = {
        ".codex/**",
        ".beads/**",
        "docs/**",
        "**/*.md",
    }

    push_ignored_paths = set(workflow["on"]["push"].get("paths-ignore", []))
    pull_request_ignored_paths = set(
        workflow["on"]["pull_request"].get("paths-ignore", [])
    )

    assert expected_ignored_paths.issubset(push_ignored_paths)
    assert expected_ignored_paths.issubset(pull_request_ignored_paths)

    assert "changes" in workflow["jobs"]
    assert "changes" in workflow["jobs"]["deploy"]["needs"]
    assert "needs.changes.outputs.deploy == 'true'" in workflow["jobs"]["deploy"]["if"]


def test_ci_test_job_fetches_full_history_for_scope_provenance() -> None:
    workflow = _load_ci_workflow()

    _assert_test_job_fetches_full_history(workflow)


def test_ci_full_test_command_contract_rejects_narrowed_command() -> None:
    workflow = _load_ci_workflow()
    run_test_steps = [
        step
        for step in workflow["jobs"]["test"]["steps"]
        if step.get("name") == "Run tests"
    ]

    assert len(run_test_steps) == 1
    run_test_steps[0]["run"] = "uv run pytest tests/test_ci_workflow_contract.py -q"

    with pytest.raises(AssertionError):
        _assert_test_job_fetches_full_history(workflow)
