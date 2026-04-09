"""Tests for Telegram notifications module (TDD: tests written first).

Covers:
- TelegramClient send_message / send_document
- No-op when token is empty
- NotificationService formatting and dispatching
- API endpoints: POST /notifications/test, GET /notifications/config
"""

from __future__ import annotations

from datetime import UTC, datetime
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
    assert "Эскалация" in msg
    assert "Телефон клиента" in msg
    assert "запрошен менеджер" in msg
    assert "Менеджер уведомлён" in msg


@pytest.mark.asyncio
async def test_notify_escalation_unknown_reason_uses_russian_fallback() -> None:
    """Unknown English reasons should not leak into owner-facing escalation alerts."""
    from src.services.notifications import format_escalation_message

    conv_id = uuid4()
    with patch("src.services.report_localization.logfire.info") as mock_logfire:
        msg = format_escalation_message(
            "+971501234567", conv_id, "Mystery escalation cause"
        )

    assert "Mystery escalation cause" not in msg
    assert "иная причина" in msg
    mock_logfire.assert_called_once()


@pytest.mark.asyncio
async def test_notify_quality_alert_formats_html() -> None:
    """notify_quality_alert should render the detailed quality review in Russian."""
    from src.quality.schemas import CriterionScore
    from src.services.notifications import format_quality_alert_message

    conv_id = uuid4()
    msg = format_quality_alert_message(
        conv_id,
        score=8.0,
        rating="poor",
        summary="Bad dialogue",
        criteria=[
            CriterionScore(rule_number=1, rule_name="Greeting", score=2, comment="ok"),
            CriterionScore(
                rule_number=8,
                rule_name="Clarifying questions",
                score=0,
                comment="missed",
            ),
            CriterionScore(
                rule_number=14, rule_name="Closing", score=0, comment="missed"
            ),
        ],
        current_stage="qualifying",
        trigger="low_score",
    )
    assert "<b>" in msg
    assert "8.0" in msg
    assert "Оценка качества" in msg
    assert "Взвешенная разбивка" in msg
    assert "Что сделано хорошо" in msg
    assert "Что ухудшило диалог" in msg
    assert "Рекомендации" in msg
    assert "Следующее действие" in msg
    assert "плохо" in msg
    assert "Текущий этап" in msg
    assert "квалификация" in msg
    assert "Основание" in msg
    assert "оценка ниже порога" in msg


@pytest.mark.asyncio
async def test_red_flag_warning_formatting() -> None:
    """Realtime red-flag warning should be compact, owner-facing, and localized."""
    from src.quality.schemas import RedFlagItem
    from src.services.notifications import format_red_flag_warning_message

    conv_id = uuid4()
    msg = format_red_flag_warning_message(
        conversation_id=conv_id,
        phone="+971501234567",
        sales_stage="greeting",
        flags=[
            RedFlagItem(
                code="missing_identity",
                title="Missing identity",
                explanation="The first reply omitted Siyyad and Treejar.",
                evidence=["Hello, how can I help?", "Tell me what you need."],
            )
        ],
        recommended_action="Отправить корректирующий follow-up и представиться заново.",
    )
    assert "🚨 <b>Критический сигнал</b>" in msg
    assert "UUID диалога" in msg
    assert "+971501234567" in msg
    assert "приветствие" in msg
    assert "Нет идентификации" in msg
    assert "Ассистент не представился как Siyyad из Treejar" in msg
    assert "Hello, how can I help?" in msg
    assert "Рекомендуемое действие" in msg


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
async def test_catalog_mismatch_formatting() -> None:
    from src.services.notifications import format_catalog_mismatch_message

    msg = format_catalog_mismatch_message(
        sku="CH 970 grey",
        treejar_slug="skyland-executive-chair-ch-970-grey",
        product_name="Skyland Executive Chair CH 970 Grey",
        detail="Zoho item lookup returned no exact SKU match.",
    )

    assert "Catalog mismatch" in msg
    assert "CH 970 grey" in msg
    assert "skyland-executive-chair-ch-970-grey" in msg
    assert "missing in Zoho" in msg
    assert "site/customer team" in msg


@pytest.mark.asyncio
async def test_notify_catalog_mismatch_calls_telegram() -> None:
    from src.services.notifications import notify_catalog_mismatch

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_catalog_mismatch(
            sku="CH 970 grey",
            treejar_slug="skyland-executive-chair-ch-970-grey",
            product_name="Skyland Executive Chair CH 970 Grey",
        )

        mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_final_quality_review_formatting() -> None:
    """Final review should render weighted breakdown and owner-facing sections."""
    from src.quality.schemas import BlockScore, CriterionScore, EvaluationResult
    from src.services.notifications import format_final_quality_review_message

    conv_id = uuid4()
    result = EvaluationResult(
        criteria=[
            CriterionScore(
                rule_number=i,
                rule_name=f"Rule {i}",
                score=2,
                comment="ok",
                applicable=True,
                evidence=[f"Evidence {i}"],
            )
            for i in range(1, 16)
        ],
        summary="Structured narrative",
        total_score=24.5,
        rating="good",
        strengths=["Strong opening and clear tone"],
        weaknesses=["Discovery could go deeper"],
        recommendations=["Ask for team size before quoting"],
        next_best_action="Send a concise quote follow-up after confirming quantities.",
        block_scores=[
            BlockScore(
                block_name="Opening & Trust", weight=6.0, points=5.0, applicable_rules=4
            ),
            BlockScore(
                block_name="Relationship & Discovery",
                weight=9.0,
                points=7.0,
                applicable_rules=5,
            ),
            BlockScore(
                block_name="Consultative Solution",
                weight=9.0,
                points=7.5,
                applicable_rules=3,
            ),
            BlockScore(
                block_name="Conversion & Next Step",
                weight=6.0,
                points=5.0,
                applicable_rules=3,
            ),
        ],
    )
    msg = format_final_quality_review_message(
        conversation_id=conv_id,
        phone="+971501234567",
        customer_name="Acme",
        sales_stage="quoting",
        trigger="idle 3h",
        result=result,
    )
    assert "🟢 <b>Оценка качества</b>" in msg
    assert "Оценка:</b> 24.5/30 (хорошо)" in msg
    assert "Основание:</b> нет ответа 3 часа" in msg
    assert "Открытие и доверие: 5.0/6" in msg
    assert "Контакт и выявление потребностей: 7.0/9" in msg
    assert "Что сделано хорошо" in msg
    assert "Что ухудшило диалог" in msg
    assert "Рекомендации" in msg
    assert "Следующее действие" in msg


@pytest.mark.asyncio
async def test_notify_red_flag_warning_calls_telegram() -> None:
    """notify_red_flag_warning should send a message via TelegramClient."""
    from src.quality.schemas import RedFlagItem
    from src.services.notifications import notify_red_flag_warning

    conv_id = uuid4()

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_red_flag_warning(
            conversation_id=conv_id,
            phone="+971501234567",
            sales_stage="greeting",
            flags=[
                RedFlagItem(
                    code="missing_identity",
                    title="Missing identity",
                    explanation="The first reply omitted Siyyad and Treejar.",
                    evidence=["Hello, how can I help?"],
                )
            ],
            recommended_action="Reply with a corrective follow-up and restate identity.",
        )

        mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_notify_final_quality_review_calls_telegram() -> None:
    """notify_final_quality_review should send a rich owner-facing report."""
    from src.quality.schemas import BlockScore, CriterionScore, EvaluationResult
    from src.services.notifications import notify_final_quality_review

    conv_id = uuid4()
    result = EvaluationResult(
        criteria=[
            CriterionScore(
                rule_number=i,
                rule_name=f"Rule {i}",
                score=2,
                comment="ok",
                applicable=True,
            )
            for i in range(1, 16)
        ],
        summary="Structured narrative",
        total_score=12.0,
        rating="poor",
        strengths=["Polite opening"],
        weaknesses=["Missed the direct question"],
        recommendations=["Answer the customer question before redirecting"],
        next_best_action="Send an apology and concrete answer now.",
        block_scores=[
            BlockScore(
                block_name="Opening & Trust", weight=6.0, points=4.0, applicable_rules=4
            ),
            BlockScore(
                block_name="Relationship & Discovery",
                weight=9.0,
                points=3.0,
                applicable_rules=5,
            ),
            BlockScore(
                block_name="Consultative Solution",
                weight=9.0,
                points=3.0,
                applicable_rules=3,
            ),
            BlockScore(
                block_name="Conversion & Next Step",
                weight=6.0,
                points=2.0,
                applicable_rules=3,
            ),
        ],
    )

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_final_quality_review(
            conversation_id=conv_id,
            phone="+971501234567",
            customer_name="Acme",
            sales_stage="closing",
            trigger="closed",
            result=result,
        )

        mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_notify_quality_alert_calls_telegram() -> None:
    """Legacy notify_quality_alert should remain callable for compatibility."""
    from src.services.notifications import notify_quality_alert

    conv_id = uuid4()

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_quality_alert(conv_id, score=8.0, rating="poor", summary="Bad")

        mock_instance.send_message.assert_called_once()

    with patch("src.services.notifications.TelegramClient") as MockTg:
        mock_instance = AsyncMock()
        MockTg.return_value = mock_instance
        mock_instance.send_message = AsyncMock()

        await notify_quality_alert(conv_id, score=8.0, rating="poor", summary="Bad")

        mock_instance.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_notify_daily_summary_formats_metrics() -> None:
    """notify_daily_summary should format dashboard metrics as HTML."""
    from src.services.daily_summary import DailySummaryData
    from src.services.notifications import format_daily_summary

    metrics = DailySummaryData(
        period_start=datetime.now(tz=UTC),
        period_end=datetime.now(tz=UTC),
        total_conversations=42,
        unique_customers=30,
        escalation_count=5,
        avg_quality_score=22.5,
        conversion_rate_7d=11.0,
    )

    msg = format_daily_summary(metrics)
    assert "42" in msg
    assert "22.5" in msg
    assert "11.0%" in msg
    assert "Ежедневная сводка" in msg
    assert "Диалоги" in msg
    assert "Средняя оценка качества" in msg
    assert "LLM Cost" not in msg


@pytest.mark.asyncio
async def test_notify_daily_summary_formats_na_values() -> None:
    """format_daily_summary should render missing metrics as N/A."""
    from src.services.daily_summary import DailySummaryData
    from src.services.notifications import format_daily_summary

    metrics = DailySummaryData(
        period_start=datetime.now(tz=UTC),
        period_end=datetime.now(tz=UTC),
    )

    msg = format_daily_summary(metrics)
    assert "<b>Средняя оценка качества:</b> н/д" in msg
    assert "<b>Конверсия (7д):</b> н/д" in msg
    assert "LLM Cost" not in msg


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
