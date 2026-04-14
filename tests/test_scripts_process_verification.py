from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESS_VERIFICATION = (
    REPO_ROOT / "scripts" / "orchestration" / "run_process_verification.sh"
)
RUNTIME_SUPPORT = REPO_ROOT / "scripts" / "orchestration" / "runtime_support.py"


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


class ProcessVerificationTests(unittest.TestCase):
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
