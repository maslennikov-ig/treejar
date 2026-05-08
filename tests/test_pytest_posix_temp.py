from __future__ import annotations

import tempfile

from tests import pytest_posix_temp


def test_pytest_tempdir_avoids_wsl_windows_mount() -> None:
    assert pytest_posix_temp._looks_like_windows_path(
        "/mnt/c/Users/user/AppData/Local/Temp"
    )
    assert pytest_posix_temp._looks_like_windows_path("C:/Users/user/AppData/Temp")
    assert not pytest_posix_temp._looks_like_windows_path("/tmp")


def test_pytest_tempfile_truncate_works_for_capture_tempdir() -> None:
    assert not pytest_posix_temp._looks_like_windows_path(tempfile.gettempdir())

    with tempfile.TemporaryFile(mode="w+t") as tmp_file:
        tmp_file.write("captured output")
        tmp_file.seek(0)
        assert tmp_file.read() == "captured output"
        tmp_file.seek(0)
        tmp_file.truncate(0)
