from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_API_MODULE_PATH = REPO_ROOT / "scripts" / "verify_api.py"


def _load_verify_api_module():
    spec = importlib.util.spec_from_file_location(
        "scripts.verify_api",
        VERIFY_API_MODULE_PATH,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_build_api_headers_uses_x_api_key() -> None:
    verify_api = _load_verify_api_module()

    assert verify_api.build_api_headers("") == {}
    assert verify_api.build_api_headers("secret-key") == {"X-API-Key": "secret-key"}


@pytest.mark.asyncio
async def test_check_conversations_expects_anonymous_denial_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_api = _load_verify_api_module()
    calls: list[dict[str, Any]] = []

    async def fake_check_endpoint(
        client: object,
        method: str,
        path: str,
        name: str,
        *,
        expect_status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        del client
        calls.append(
            {
                "method": method,
                "path": path,
                "name": name,
                "expect_status": expect_status,
                "headers": headers,
            }
        )

    monkeypatch.setattr(verify_api, "check_endpoint", fake_check_endpoint)

    await verify_api.check_conversations(client=object(), api_key="")

    assert calls == [
        {
            "method": "GET",
            "path": "/api/v1/conversations/",
            "name": "Conversation list auth guard",
            "expect_status": 403,
            "headers": {},
        }
    ]


@pytest.mark.asyncio
async def test_check_conversations_uses_api_key_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify_api = _load_verify_api_module()
    calls: list[dict[str, Any]] = []

    async def fake_check_endpoint(
        client: object,
        method: str,
        path: str,
        name: str,
        *,
        expect_status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        del client
        calls.append(
            {
                "method": method,
                "path": path,
                "name": name,
                "expect_status": expect_status,
                "headers": headers,
            }
        )

    monkeypatch.setattr(verify_api, "check_endpoint", fake_check_endpoint)

    await verify_api.check_conversations(client=object(), api_key="secret-key")

    assert calls == [
        {
            "method": "GET",
            "path": "/api/v1/conversations/",
            "name": "Conversation list",
            "expect_status": 200,
            "headers": {"X-API-Key": "secret-key"},
        }
    ]
