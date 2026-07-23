from __future__ import annotations

from importlib.metadata import PackageNotFoundError

import pytest

from src.api.v1 import health


def test_resolve_app_version_from_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health, "package_version", lambda package: "9.8.7")

    assert health.resolve_app_version() == "9.8.7"


def test_resolve_app_version_has_deterministic_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def package_not_installed(package: str) -> str:
        raise PackageNotFoundError(package)

    monkeypatch.setattr(health, "package_version", package_not_installed)

    assert health.resolve_app_version() == "0.0.0+unknown"
