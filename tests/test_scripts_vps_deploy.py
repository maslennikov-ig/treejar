from __future__ import annotations

import os
import subprocess
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "vps-deploy.sh"


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def _build_release_archive(release_root: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        for file_path in sorted(release_root.rglob("*")):
            archive.add(file_path, arcname=file_path.relative_to(release_root))


def test_vps_deploy_syncs_release_and_preserves_runtime_state(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "docker-compose.yml").write_text("services: {}\n")
    (release_root / "Dockerfile").write_text("FROM scratch\n")
    (release_root / ".release-sha").write_text("278c46c8\n")
    (release_root / "app.txt").write_text("new release payload\n")

    archive_path = tmp_path / "release.tar.gz"
    _build_release_archive(release_root, archive_path)

    target_dir = tmp_path / "noor"
    target_dir.mkdir()
    (target_dir / ".env").write_text("SECRET=1\n")
    (target_dir / ".release-sha").write_text("oldsha\n")
    (target_dir / "docker-compose.yml").write_text("services: {old: {}}\n")
    (target_dir / "stale.txt").write_text("remove me\n")
    (target_dir / "app.txt").write_text("old payload\n")
    (target_dir / ".codex").mkdir()
    (target_dir / ".codex" / "keep.txt").write_text("preserve me\n")

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    docker_log = tmp_path / "docker.log"
    curl_log = tmp_path / "curl.log"

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
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f"printf '%s\\n' \"$*\" >> '{curl_log}'",
                'printf \'{"status": "ok"}\\n\'',
            ]
        )
        + "\n",
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--archive",
            str(archive_path),
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
    assert (target_dir / "app.txt").read_text() == "new release payload\n"
    assert (target_dir / ".env").read_text() == "SECRET=1\n"
    assert not (target_dir / "stale.txt").exists()
    assert (target_dir / ".codex" / "keep.txt").read_text() == "preserve me\n"
    assert (target_dir / ".release-sha").read_text() == "278c46c8\n"

    backup_files = sorted((target_dir / ".hotfix-backups").glob("deploy-*.tar.gz"))
    assert backup_files, "expected at least one rollback backup"

    docker_calls = docker_log.read_text().splitlines()
    assert docker_calls == [
        "compose --project-name noor -f docker-compose.yml up -d --build"
    ]
    assert (
        curl_log.read_text().strip()
        == "--fail --silent --show-error http://127.0.0.1:8002/api/v1/health"
    )


def test_vps_deploy_requires_existing_env_file(tmp_path: Path) -> None:
    release_root = tmp_path / "release"
    release_root.mkdir()
    (release_root / "docker-compose.yml").write_text("services: {}\n")
    archive_path = tmp_path / "release.tar.gz"
    _build_release_archive(release_root, archive_path)

    target_dir = tmp_path / "noor"

    result = subprocess.run(
        [
            "bash",
            str(SCRIPT_PATH),
            "--archive",
            str(archive_path),
            "--target-dir",
            str(target_dir),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert "Missing" in result.stderr
