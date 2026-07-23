from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESS_VERIFICATION = (
    REPO_ROOT / "scripts" / "orchestration" / "run_process_verification.sh"
)
RUNTIME_SUPPORT = REPO_ROOT / "scripts" / "orchestration" / "runtime_support.py"
STAGE_CLOSEOUT = REPO_ROOT / "scripts" / "orchestration" / "run_stage_closeout.py"
STAGE_CLEANUP = REPO_ROOT / "scripts" / "orchestration" / "cleanup_stage_workspace.py"
CHECK_STAGE_READY = REPO_ROOT / "scripts" / "orchestration" / "check_stage_ready.py"
REVIEW_COMPLETION_INBOX = (
    REPO_ROOT / "scripts" / "orchestration" / "review_completion_inbox.py"
)


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def _load_runtime_support():
    spec = importlib.util.spec_from_file_location("runtime_support", RUNTIME_SUPPORT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_stage_closeout():
    spec = importlib.util.spec_from_file_location("stage_closeout", STAGE_CLOSEOUT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ProcessVerificationTests(unittest.TestCase):
    def test_verification_policy_references_defined_command_groups(self) -> None:
        contract = tomllib.loads(
            (REPO_ROOT / ".codex" / "orchestrator.toml").read_text()
        )
        verification = contract["verification"]
        policy = contract["verification_policy"]

        referenced_groups = {
            group
            for mapping_name in (
                "level_groups",
                "tier_groups",
                "risk_tag_groups",
                "surface_groups",
            )
            for groups in policy[mapping_name].values()
            for group in groups
        }

        missing = sorted(
            group
            for group in referenced_groups
            if not isinstance(verification.get(group), list) or not verification[group]
        )
        self.assertEqual(missing, [])

    def test_contract_points_to_current_stage_summary(self) -> None:
        contract = tomllib.loads(
            (REPO_ROOT / ".codex" / "orchestrator.toml").read_text()
        )
        stage_id = contract["workspace"]["current_stage_id"]
        expected = f".codex/stages/{stage_id}/summary.md"

        self.assertEqual(
            contract["artifacts"].get("current_stage_summary"),
            expected,
        )
        self.assertTrue((REPO_ROOT / expected).is_file())

    def test_completion_inbox_accepts_git_common_dir_transport(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subprocess.run(
                ["git", "init", "-q"],
                cwd=tmp_path,
                check=True,
            )
            (tmp_path / ".codex").mkdir()
            (tmp_path / ".codex" / "orchestrator.toml").write_text(
                "\n".join(
                    [
                        "[baseline]",
                        'profile = "balanced-v2.19"',
                        "",
                        "[workspace]",
                        'current_stage_id = "tj-shared-inbox"',
                        "",
                        "[completion_inbox]",
                        'scope = "git_common_dir"',
                        'events_file = "codex-orchestration/completions.ndjson"',
                        'review_state_file = "codex-orchestration/review-state.json"',
                    ]
                )
            )

            result = subprocess.run(
                [sys.executable, str(REVIEW_COMPLETION_INBOX)],
                cwd=tmp_path,
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("total_events: 0", result.stdout)
            self.assertIn("pending_events: 0", result.stdout)

    def test_stage_ready_requires_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stage_dir = tmp_path / ".codex" / "stages" / "tj-no-artifacts"
            stage_dir.mkdir(parents=True)
            (stage_dir / "summary.md").write_text(
                "# Stage tj-no-artifacts\n\nproject-index: reviewed-no-change\n"
            )
            (tmp_path / ".codex" / "handoff.md").write_text(
                "# Handoff\n\n"
                "Stage tj-no-artifacts is under review.\n\n"
                "## Explicit defers\n\n"
                "- tracked bead covers the blocker.\n"
            )

            result = subprocess.run(
                [sys.executable, str(CHECK_STAGE_READY), "tj-no-artifacts"],
                cwd=tmp_path,
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing stage artifacts", result.stderr)

    def test_stage_closeout_requires_artifacts_when_contract_requires_them(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            stage_dir = tmp_path / ".codex" / "stages" / "tj-no-artifacts"
            stage_dir.mkdir(parents=True)
            (stage_dir / "summary.md").write_text(
                "# Stage tj-no-artifacts\n\nproject-index: reviewed-no-change\n"
            )
            (tmp_path / ".codex" / "handoff.md").write_text(
                "# Handoff\n\n"
                "Stage tj-no-artifacts is under review.\n\n"
                "## Explicit defers\n\n"
                "- tracked bead covers the blocker.\n"
            )
            (tmp_path / ".codex" / "orchestrator.toml").write_text(
                "\n".join(
                    [
                        'handoff_file = ".codex/handoff.md"',
                        "",
                        "[enforcement]",
                        'process_verification_entrypoint = "scripts/orchestration/run_process_verification.sh"',
                        "artifact_required_for_stage_close = true",
                        "",
                        "[verification]",
                        "",
                    ]
                )
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(STAGE_CLOSEOUT),
                    "--stage",
                    "tj-no-artifacts",
                    "--dry-run",
                    "--skip-process-check",
                ],
                cwd=tmp_path,
                capture_output=True,
                check=False,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("missing stage artifacts", result.stderr)

    def test_stage_scripts_bootstrap_tomllib_runtime_before_import(self) -> None:
        for path in (STAGE_CLOSEOUT, STAGE_CLEANUP):
            text = path.read_text()
            self.assertIn("ensure_tomllib_runtime", text)
            self.assertLess(
                text.index("ensure_tomllib_runtime"),
                text.index("import tomllib"),
                f"{path.name} must re-exec Python 3.10 before importing tomllib",
            )

    def test_debt_scan_ignores_untracked_binary_files(self) -> None:
        stage_closeout = _load_stage_closeout()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
            binary_marker = "".join(("HA", "CK"))
            text_marker = "".join(("TO", "DO"))
            (tmp_path / "binary.pdf").write_bytes(
                b"%PDF-1.7\n\x00\x01compressed "
                + binary_marker.encode()
                + b" payload\xff"
            )
            (tmp_path / "notes.txt").write_text(f"{text_marker}: tracked follow-up\n")

            hits = stage_closeout.changed_line_debt_hits(tmp_path)

            self.assertEqual(
                hits,
                [f"notes.txt:1: {text_marker}: tracked follow-up"],
            )

    def test_runtime_support_reexecs_with_uv_for_python_without_tomllib(self) -> None:
        runtime_support = _load_runtime_support()
        exec_calls: list[tuple[str, list[str]]] = []
        runtime_support.ensure_tomllib_runtime(
            ["scripts/orchestration/run_stage_closeout.py", "--dry-run"],
            version_info=(3, 10, 14),
            which=lambda name: "/fake/bin/uv" if name == "uv" else None,
            execvp=lambda executable, argv: exec_calls.append((executable, argv)),
        )

        self.assertEqual(
            exec_calls,
            [
                (
                    "/fake/bin/uv",
                    [
                        "/fake/bin/uv",
                        "run",
                        "--python",
                        runtime_support.UV_PYTHON_VERSION,
                        "python",
                        "scripts/orchestration/run_stage_closeout.py",
                        "--dry-run",
                    ],
                )
            ],
        )

    def test_process_verification_uses_uv_when_python3_lacks_tomllib(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            bin_dir = tmp_path / "bin"
            bin_dir.mkdir()
            uv_log = tmp_path / "uv.log"

            _write_executable(
                bin_dir / "python3",
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        'if [[ "${1:-}" == "--version" ]]; then',
                        "  echo 'Python 3.10.14'",
                        "  exit 0",
                        "fi",
                        'if [[ "${1:-}" == "-" ]]; then',
                        "  cat >/dev/null",
                        "  exit 1",
                        "fi",
                        'echo "unexpected python3 invocation: $*" >&2',
                        "exit 99",
                    ]
                )
                + "\n",
            )
            _write_executable(
                bin_dir / "uv",
                "\n".join(
                    [
                        "#!/usr/bin/env bash",
                        "set -euo pipefail",
                        f"printf '%s\\n' \"$*\" >> '{uv_log}'",
                        'if [[ "${1:-}" == "run" ]]; then',
                        "  shift",
                        "fi",
                        'if [[ "${1:-}" == "--python" ]]; then',
                        "  shift 2",
                        "fi",
                        'if [[ "${1:-}" == "python" ]]; then',
                        "  shift",
                        "fi",
                        f'exec "{sys.executable}" "$@"',
                    ]
                )
                + "\n",
            )

            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(PROCESS_VERIFICATION)],
                cwd=REPO_ROOT,
                capture_output=True,
                check=False,
                env=env,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertIn("process verification OK", result.stdout)
            self.assertIn("run --python 3.12 python -", uv_log.read_text())


if __name__ == "__main__":
    unittest.main()
