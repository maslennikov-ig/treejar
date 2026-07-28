from __future__ import annotations

from pathlib import Path

import yaml


def test_ci_workflow_skips_docs_and_orchestration_only_changes() -> None:
    workflow = yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

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
    workflow = yaml.load(
        Path(".github/workflows/ci.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )

    test_job = workflow["jobs"]["test"]
    assert any(
        "uv run pytest tests/" in step.get("run", "") for step in test_job["steps"]
    )

    checkout_steps = [
        step
        for step in test_job["steps"]
        if step.get("uses", "").startswith("actions/checkout@")
    ]

    assert len(checkout_steps) == 1
    assert checkout_steps[0].get("with", {}).get("fetch-depth") == "0"
