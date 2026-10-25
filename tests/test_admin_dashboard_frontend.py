from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def _resolve_node_binary() -> str:
    candidate = shutil.which("node")
    if candidate and os.access(candidate, os.X_OK):
        return candidate
    nvm_bins = sorted((Path.home() / ".nvm" / "versions" / "node").glob("*/bin/node"))
    for node_bin in reversed(nvm_bins):
        if node_bin.is_file() and os.access(node_bin, os.X_OK):
            return str(node_bin)
    return "node"


def _ensure_worktree_node_modules(repo_root: Path) -> None:
    local_node_modules = repo_root / "frontend" / "admin" / "node_modules"
    if local_node_modules.exists():
        return
    common = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not common:
        return
    common_dir = Path(common)
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    shared_node_modules = common_dir.parent / "frontend" / "admin" / "node_modules"
    if shared_node_modules.is_dir():
        local_node_modules.symlink_to(shared_node_modules)


def _run_frontend_regression(script_name: str) -> subprocess.CompletedProcess[str]:
    repo_root = Path(__file__).resolve().parents[1]
    _ensure_worktree_node_modules(repo_root)
    script_path = repo_root / "frontend" / "admin" / "tests" / script_name

    return subprocess.run(
        [_resolve_node_binary(), str(script_path)],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def test_operator_center_renders_when_metrics_fail() -> None:
    result = _run_frontend_regression("app_operator_center_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_crm_admin_static_contract() -> None:
    result = _run_frontend_regression("crm_admin_static_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_dashboard_uses_no_external_font_hosts() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    index_html = repo_root / "frontend" / "admin" / "index.html"
    source = index_html.read_text(encoding="utf-8")

    assert "fonts.googleapis.com" not in source
    assert "fonts.gstatic.com" not in source


def test_admin_light_theme_charts_use_readable_tokens() -> None:
    result = _run_frontend_regression("light_theme_chart_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_operator_center_review_message_handles_refresh_failure_after_success() -> None:
    result = _run_frontend_regression("operator_center_review_message_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_ai_quality_controls_dashboard_renders_controls_and_warnings() -> None:
    result = _run_frontend_regression("ai_quality_controls_dashboard_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_ai_quality_controls_api_uses_admin_patch_payload() -> None:
    result = _run_frontend_regression("ai_quality_controls_api_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_client_self_test_api_submits_finish_payload() -> None:
    result = _run_frontend_regression("client_self_test_api_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_client_self_test_state_helpers_cover_acceptance_scenarios() -> None:
    result = _run_frontend_regression("client_self_test_state_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_client_self_test_public_route_mode() -> None:
    result = _run_frontend_regression("client_self_test_public_route_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_help_tooltip_is_instant_and_accessible() -> None:
    result = _run_frontend_regression("help_tooltip_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_i18n_dictionaries_match_and_cover_ui() -> None:
    result = _run_frontend_regression("i18n_dictionary_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_dashboard_charts_render_without_clipping() -> None:
    result = _run_frontend_regression("dashboard_charts_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_dashboard_polish_search_banners_and_quick_actions() -> None:
    result = _run_frontend_regression("dashboard_polish_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_onboarding_tour_and_guide_view() -> None:
    result = _run_frontend_regression("onboarding_guide_regression.mjs")

    assert result.returncode == 0, result.stderr or result.stdout


def test_admin_session_guard_redirects_expired_sessions() -> None:
    result = _run_frontend_regression("session_guard_regression.mjs")

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
