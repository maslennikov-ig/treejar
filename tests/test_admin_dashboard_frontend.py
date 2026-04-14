from __future__ import annotations

import subprocess
from pathlib import Path


def test_operator_center_renders_when_metrics_fail() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = (
        repo_root
        / "frontend"
        / "admin"
        / "tests"
        / "app_operator_center_regression.mjs"
    )

    result = subprocess.run(
        ["node", str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_operator_center_regression_script_uses_portable_frontend_root() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script_path = (
        repo_root
        / "frontend"
        / "admin"
        / "tests"
        / "app_operator_center_regression.mjs"
    )
    script = script_path.read_text(encoding="utf-8")

    assert (
        "/Users/igor/code/treejar-tj-9a4m/.worktrees/tj-9a4m-auth-align/frontend/admin"
        not in script
    )
    assert "import.meta.url" in script
