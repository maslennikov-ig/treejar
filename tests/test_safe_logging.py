from __future__ import annotations

import io
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _capture_root_logging(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))
    root = logging.getLogger()
    monkeypatch.setattr(root, "handlers", [handler])
    root.setLevel(logging.INFO)
    return stream


def _emit_sensitive_http_records() -> None:
    httpx_logger = logging.getLogger("httpx")
    wazzup_logger = logging.getLogger("src.integrations.messaging.wazzup")
    httpx_logger.info(
        "HTTP Request: POST %s %s",
        "https://api.telegram.org/bot123456:unit-test-token/sendMessage",
        '"HTTP/1.1 200 OK"',
    )
    wazzup_logger.info(
        "Uploaded 128 bytes to %s",
        "https://tmpfiles.org/download/unit-test-access/report.pdf"
        "?signature=unit-test-signature&expires=123",
    )
    try:
        raise RuntimeError(
            "GET https://media.example.test/private/unit-test-path"
            "?token=unit-test-query-token failed"
        )
    except RuntimeError:
        httpx_logger.exception("HTTP client failed")


@pytest.mark.asyncio
async def test_worker_redacts_credential_bearing_urls_from_every_http_logger(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.worker import startup

    with patch("src.worker.EmbeddingEngine") as mock_engine:
        mock_engine.return_value.warmup_async = AsyncMock()
        await startup({"redis": None})

    stream = io.StringIO()
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler):
            handler.setStream(stream)

    _emit_sensitive_http_records()

    output = stream.getvalue()
    assert "unit-test-token" not in output
    assert "unit-test-access" not in output
    assert "unit-test-signature" not in output
    assert "unit-test-path" not in output
    assert "unit-test-query-token" not in output
    assert "https://api.telegram.org/[redacted-url]" in output
    assert "https://tmpfiles.org/[redacted-url]" in output
    assert "https://media.example.test/[redacted-url]" in output
    assert "HTTP client failed" in output


@pytest.mark.asyncio
async def test_api_lifespan_installs_the_same_record_filter_before_http_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src import main

    stream = _capture_root_logging(monkeypatch)
    pool = AsyncMock()
    app = SimpleNamespace(state=SimpleNamespace())

    with (
        patch("src.main.create_pool", new=AsyncMock(return_value=pool)),
        patch("src.main.sync_telegram_webhook", new=AsyncMock(return_value=True)),
        patch("src.main.redis_client", new=AsyncMock()),
        patch("src.main.engine", new=AsyncMock()),
    ):
        async with main.lifespan(app):
            _emit_sensitive_http_records()

    output = stream.getvalue()
    assert "unit-test-token" not in output
    assert "unit-test-signature" not in output
    assert "unit-test-query-token" not in output
    assert "https://api.telegram.org/[redacted-url]" in output
