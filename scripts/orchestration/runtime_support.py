from __future__ import annotations

import os
import shutil
import sys
from collections.abc import Callable, Sequence

MIN_TOMLLIB_VERSION = (3, 11)
UV_PYTHON_VERSION = "3.12"


def ensure_tomllib_runtime(
    script_argv: Sequence[str],
    *,
    version_info: Sequence[int] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    execvp: Callable[[str, Sequence[str]], object] = os.execvp,
) -> None:
    current_version = tuple((version_info or sys.version_info)[:2])
    if current_version >= MIN_TOMLLIB_VERSION:
        return

    uv = which("uv")
    if not uv:
        raise SystemExit(
            "Python 3.11+ is required for orchestration TOML parsing; install uv or use a newer python3."
        )

    execvp(uv, [uv, "run", "--python", UV_PYTHON_VERSION, "python", *script_argv])
