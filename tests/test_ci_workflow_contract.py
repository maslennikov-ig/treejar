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
