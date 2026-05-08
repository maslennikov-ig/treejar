"""Keep pytest fd capture away from WSL Windows temp mounts.

Some local Codex/WSL shells inherit ``TMP`` and ``TEMP`` from Windows. Python can
open ``tempfile.TemporaryFile`` on that mount, but ``truncate`` may fail, which
breaks pytest's default fd capture before test collection. Load this plugin via
pytest addopts so the temp directory is normalized before capture starts.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path, PurePosixPath

_TEMP_ENV_VARS = ("TMPDIR", "TMP", "TEMP")
_FALLBACK_TEMP_DIRS = ("/tmp", "/var/tmp")


def _looks_like_windows_path(path: str | None) -> bool:
    if not path:
        return False

    normalized = path.replace("\\", "/")
    if len(normalized) >= 3 and normalized[1] == ":" and normalized[2] == "/":
        return True

    parts = PurePosixPath(normalized).parts
    return (
        len(parts) >= 3
        and parts[0] == "/"
        and parts[1] == "mnt"
        and len(parts[2]) == 1
        and parts[2].isalpha()
    )


def _is_usable_posix_temp_dir(path: str | None) -> bool:
    if not path or _looks_like_windows_path(path):
        return False

    try:
        candidate = Path(path)
        return candidate.is_dir() and os.access(candidate, os.W_OK | os.X_OK)
    except OSError:
        return False


def _select_posix_temp_dir() -> str | None:
    explicit = os.environ.get("PYTEST_POSIX_TMPDIR")
    if explicit and _is_usable_posix_temp_dir(explicit):
        return explicit

    tmpdir = os.environ.get("TMPDIR")
    if _is_usable_posix_temp_dir(tmpdir):
        return tmpdir

    for fallback in _FALLBACK_TEMP_DIRS:
        if _is_usable_posix_temp_dir(fallback):
            return fallback

    return None


def _apply_posix_temp_dir() -> None:
    if not any(
        _looks_like_windows_path(os.environ.get(name)) for name in _TEMP_ENV_VARS
    ):
        return

    temp_dir = _select_posix_temp_dir()
    if temp_dir is None:
        return

    for name in _TEMP_ENV_VARS:
        os.environ[name] = temp_dir
    tempfile.tempdir = temp_dir


def pytest_load_initial_conftests(
    early_config: object,
    parser: object,
    args: list[str],
) -> None:
    _apply_posix_temp_dir()


_apply_posix_temp_dir()
