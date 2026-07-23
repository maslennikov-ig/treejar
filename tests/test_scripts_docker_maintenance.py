from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MAINTENANCE_SCRIPT = REPO_ROOT / "scripts" / "docker-maintenance.sh"
CRON_INSTALL_SCRIPT = REPO_ROOT / "scripts" / "install-docker-maintenance-cron.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def test_docker_maintenance_dry_run_only_prints_planned_commands(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"

    _write_executable(
        bin_dir / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"printf '%s\\n' \"$*\" >> '{docker_log}'",
                'if [ "$1 $2" = "system df" ]; then',
                "  printf 'TYPE SIZE\\n'",
                "fi",
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(MAINTENANCE_SCRIPT)],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert docker_log.read_text().splitlines() == ["system df"]
    assert "Dry-run only" in result.stdout
    assert (
        "docker builder prune --force --all --max-used-space 20gb --reserved-space 5gb"
        in result.stdout
    )
    assert "docker image prune --force --all --filter until=168h" in result.stdout


def test_docker_maintenance_apply_runs_conservative_cleanup_and_health_check(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"
    target_dir = tmp_path / "noor"
    target_dir.mkdir()

    _write_executable(
        bin_dir / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"printf '%s\\n' \"$*\" >> '{docker_log}'",
                'if [ "$1 $2" = "system df" ]; then',
                "  printf 'TYPE SIZE\\n'",
                "fi",
            ]
        )
        + "\n",
    )
    _write_executable(
        bin_dir / "curl",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"printf '%s\\n' \"$*\" >> '{curl_log}'",
                'printf \'{"status":"ok"}\\n\'',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        [
            "bash",
            str(MAINTENANCE_SCRIPT),
            "--apply",
            "--target-dir",
            str(target_dir),
            "--health-url",
            "http://127.0.0.1:8002/api/v1/health",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert docker_log.read_text().splitlines() == [
        "system df",
        "builder prune --force --all --max-used-space 20gb --reserved-space 5gb",
        "image prune --force --all --filter until=168h",
        "system df",
    ]
    assert curl_log.read_text().splitlines() == [
        "--fail --silent --show-error http://127.0.0.1:8002/api/v1/health"
    ]


def test_docker_maintenance_failed_health_check_is_a_failure(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"

    _write_executable(
        bin_dir / "docker",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"printf '%s\\n' \"$*\" >> '{docker_log}'",
            ]
        )
        + "\n",
    )
    _write_executable(
        bin_dir / "curl",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 22\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(MAINTENANCE_SCRIPT), "--apply"],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "Docker maintenance complete" not in result.stdout


def test_cron_installer_rewrites_managed_block_idempotently(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    crontab_file = tmp_path / "crontab.txt"
    target_dir = tmp_path / "noor"
    script_dir = target_dir / "scripts"
    script_dir.mkdir(parents=True)
    maintenance_script = script_dir / "docker-maintenance.sh"
    _write_executable(maintenance_script, "#!/usr/bin/env bash\n")

    _write_executable(
        bin_dir / "crontab",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"CRON_FILE='{crontab_file}'",
                'if [ "${1:-}" = "-l" ]; then',
                '  [ -f "$CRON_FILE" ] && cat "$CRON_FILE"',
                "  exit 0",
                "fi",
                'cat > "$CRON_FILE"',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    first = subprocess.run(
        [
            "bash",
            str(CRON_INSTALL_SCRIPT),
            "--target-dir",
            str(target_dir),
            "--schedule",
            "17 3 * * *",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )
    second = subprocess.run(
        [
            "bash",
            str(CRON_INSTALL_SCRIPT),
            "--target-dir",
            str(target_dir),
            "--schedule",
            "17 3 * * *",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert first.returncode == 0, first.stderr or first.stdout
    assert second.returncode == 0, second.stderr or second.stdout

    crontab_contents = crontab_file.read_text()
    assert crontab_contents.count("# BEGIN treejar-docker-maintenance") == 1
    assert crontab_contents.count("# END treejar-docker-maintenance") == 1
    assert "17 3 * * *" in crontab_contents
    assert (
        str(target_dir / "logs" / "maintenance" / "docker-maintenance.log")
        in crontab_contents
    )
    assert "--aggressive" not in crontab_contents
    assert "Verified Docker maintenance cron readback" in second.stdout


def test_cron_installer_handles_spaces_and_quotes_in_paths(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    crontab_file = tmp_path / "crontab.txt"
    target_dir = tmp_path / "noor ops' safe"
    script_dir = target_dir / "scripts"
    script_dir.mkdir(parents=True)
    _write_executable(
        script_dir / "docker-maintenance.sh",
        "#!/usr/bin/env bash\n",
    )
    _write_executable(
        bin_dir / "crontab",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"CRON_FILE='{crontab_file}'",
                'if [ "${1:-}" = "-l" ]; then',
                '  [ -f "$CRON_FILE" ] && cat "$CRON_FILE"',
                "  exit 0",
                "fi",
                'cat > "$CRON_FILE"',
            ]
        )
        + "\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        [
            "bash",
            str(CRON_INSTALL_SCRIPT),
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    entry = crontab_file.read_text().splitlines()[1]
    syntax = subprocess.run(
        ["sh", "-n"],
        input=entry.split(maxsplit=5)[5],
        capture_output=True,
        check=False,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr


def test_cron_installer_restores_previous_crontab_when_readback_fails(
    tmp_path: Path,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    crontab_file = tmp_path / "crontab.txt"
    calls_file = tmp_path / "calls.txt"
    target_dir = tmp_path / "noor"
    script_dir = target_dir / "scripts"
    script_dir.mkdir(parents=True)
    _write_executable(
        script_dir / "docker-maintenance.sh",
        "#!/usr/bin/env bash\n",
    )
    crontab_file.write_text("5 4 * * * /usr/local/bin/existing-job\n")
    _write_executable(
        bin_dir / "crontab",
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"CRON_FILE='{crontab_file}'",
                f"CALLS_FILE='{calls_file}'",
                'if [ "${1:-}" = "-l" ]; then',
                '  calls="$(cat "$CALLS_FILE" 2>/dev/null || printf 0)"',
                '  if [ "$calls" = "1" ]; then',
                "    printf '# corrupted readback\\n'",
                "  else",
                '    cat "$CRON_FILE"',
                "  fi",
                "  exit 0",
                "fi",
                'calls="$(cat "$CALLS_FILE" 2>/dev/null || printf 0)"',
                'printf "%s" "$((calls + 1))" > "$CALLS_FILE"',
                'cat > "$CRON_FILE"',
            ]
        )
        + "\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(CRON_INSTALL_SCRIPT), "--target-dir", str(target_dir)],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert crontab_file.read_text() == "5 4 * * * /usr/local/bin/existing-job\n"


def test_cron_installer_rejects_schedule_command_injection(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    target_dir = tmp_path / "noor"
    script_dir = target_dir / "scripts"
    script_dir.mkdir(parents=True)
    _write_executable(
        script_dir / "docker-maintenance.sh",
        "#!/usr/bin/env bash\n",
    )
    _write_executable(
        bin_dir / "crontab",
        "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        [
            "bash",
            str(CRON_INSTALL_SCRIPT),
            "--target-dir",
            str(target_dir),
            "--schedule",
            "17 3 * * *; touch /tmp/unsafe",
        ],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert not Path("/tmp/unsafe").exists()
