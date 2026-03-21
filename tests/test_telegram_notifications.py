"""Tests for Telegram notifications module (TDD: tests written first).

Covers:
- TelegramClient send_message / send_document
- No-op when token is empty
- NotificationService formatting and dispatching
- API endpoints: POST /notifications/test, GET /notifications/config
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

# =============================================================================
# TelegramClient tests
# =============================================================================


@pytest.mark.asyncio
async def test_telegram_send_message_calls_api() -> None:
    """send_message should POST to Telegram sendMessage API."""
    from src.integrations.notifications.telegram import TelegramClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {}}
    mock_response.raise_for_status = MagicMock()

    with patch(
        "src.integrations.notifications.telegram.httpx.AsyncClient"
    ) as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TelegramClient(bot_token="test-token", chat_id="123")
        await client.send_message("Hello <b>world</b>")

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert "sendMessage" in call_args[0][0]
        payload = call_args[1].get("json") or call_args[1].get("data")
        assert payload["chat_id"] == "123"
        assert payload["text"] == "Hello <b>world</b>"
        assert payload["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_telegram_noop_when_token_empty() -> None:
    """All methods should silently return when bot_token is empty."""
    from src.integrations.notifications.telegram import TelegramClient

    client = TelegramClient(bot_token="", chat_id="123")
    # Should not raise
    await client.send_message("test")
    await client.send_document(b"pdf-bytes", "report.pdf")


@pytest.mark.asyncio
async def test_telegram_send_document_calls_api() -> None:
    """send_document should POST multipart to Telegram sendDocument API."""
    from src.integrations.notifications.telegram import TelegramClient

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True, "result": {}}
    mock_response.raise_for_status = MagicMock()

    with patch(
        "src.integrations.notifications.telegram.httpx.AsyncClient"
    ) as MockClient:
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock(return_value=False)
        MockClient.return_value = mock_client_instance

        client = TelegramClient(bot_token="test-token", chat_id="456")
        await client.send_document(b"fake-pdf", "report.pdf", caption="Weekly report")

        mock_client_instance.post.assert_called_once()
        call_args = mock_client_instance.post.call_args
        assert "sendDocument" in call_args[0][0]


# =============================================================================
# NotificationService tests
# =============================================================================


@pytest.mark.asyncio
async def test_notify_escalation_formats_html() -> None:
    """notify_escalation should format HTML with masked phone, reason, and link."""
    from src.services.notifications import format_escalation_message

    conv_id = uuid4()
    phone = "+971501234567"

    msg = format_escalation_message(phone, conv_id, "Customer asked for a manager")
    assert "<b>" in msg
    # Phone should be shown in full (I3 fix: managers need to contact clients)
    assert "+971501234567" in msg
    assert "Customer asked for a manager" in msg


@pytest.mark.asyncio
async def test_notify_quality_alert_formats_html() -> None:
    """notify_quality_alert should format HTML with score and rating."""
    from src.services.notifications import format_quality_alert_message

    conv_id = uuid4()
    msg = format_quality_alert_message(
        conv_id, score=8.0, rating="poor", summary="Bad dialogue"
    )
    assert "<b>" in msg
    assert "8.0" in msg
    assert "poor" in msg


@pytest.mark.asyncio
async def test_notify_escalation_calls_telegram() -> None:
    """notify_escalation should send message via TelegramClient."""
    from src.services.notifications import notify_escalation

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_escalation("+971501234567", uuid4(), "Customer wants human")

        mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_notify_quality_alert_calls_telegram() -> None:
    """notify_quality_alert should send message via TelegramClient when score < 14."""
    from src.services.notifications import notify_quality_alert

    conv_id = uuid4()

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_quality_alert(conv_id, score=8.0, rating="poor", summary="Bad")

        mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_notify_daily_summary_formats_metrics() -> None:
    """notify_daily_summary should format dashboard metrics as HTML."""
    from src.services.notifications import format_daily_summary

    metrics = MagicMock()
    metrics.total_conversations = 42
    metrics.unique_customers = 30
    metrics.escalation_count = 5
    metrics.avg_quality_score = 22.5
    metrics.conversion_rate = 11.0
    metrics.llm_cost_usd = 1.23

    msg = format_daily_summary(metrics)
    assert "42" in msg
    assert "22.5" in msg
    assert "1.23" in msg


# =============================================================================
# API tests
# =============================================================================


@pytest.mark.asyncio
async def test_api_notifications_test(client: AsyncMock) -> None:
    """POST /api/v1/notifications/test should return 200."""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    with patch("src.api.v1.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/api/v1/notifications/test")
        assert resp.status_code == 200
        assert resp.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_api_notifications_config() -> None:
    """GET /api/v1/notifications/config should return masked config."""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        resp = await ac.get("/api/v1/notifications/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "telegram_configured" in data
