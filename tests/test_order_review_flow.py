"""Tests for PDF quotation → Telegram escalation → WhatsApp delivery flow (tj-zr2).

TDD RED → GREEN: tests cover the full order review flow.

Covers:
1. Escalation with PDF sends document to Telegram
2. Escalation without PDF sends only text + buttons
3. Order confirm retrieves PDF from Redis, sends via Wazzup
4. Order confirm with expired PDF handles gracefully
5. Order reject deletes PDF, sends rejection text
6. Order reject does NOT send PDF to client
"""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.schemas.common import EscalationType

# =============================================================================
# Redis key constants (must match implementation)
# =============================================================================
PDF_KEY_PREFIX = "quotation_pdf:"
META_KEY_PREFIX = "quotation_meta:"


# =============================================================================
# Helpers
# =============================================================================


def _make_fake_conv(
    conv_id: str = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    phone: str = "+971501234567",
    escalation_status: str = "none",
    language: str = "en",
) -> MagicMock:
    """Create a mock Conversation object."""
    conv = MagicMock()
    conv.id = conv_id
    conv.phone = phone
    conv.escalation_status = escalation_status
    conv.language = language
    conv.customer_name = "Test Customer"
    conv.metadata_ = {}
    return conv


FAKE_PDF_BYTES = b"%PDF-1.4 fake pdf content for testing"
FAKE_CONV_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


# =============================================================================
# 1. Escalation with PDF sends document to Telegram
# =============================================================================


@pytest.mark.asyncio
@patch("src.integrations.notifications.escalation.TelegramClient")
async def test_escalation_with_pdf_sends_document(
    mock_tg_cls: MagicMock,
) -> None:
    """When pdf_bytes is provided, escalation should call send_document."""
    from src.integrations.notifications.escalation import notify_manager_escalation

    mock_tg = AsyncMock()
    mock_tg_cls.return_value = mock_tg
    mock_tg.send_document = AsyncMock(return_value={"ok": True})
    mock_tg.send_message_with_inline_keyboard = AsyncMock(return_value={"ok": True})

    mock_conv = _make_fake_conv(escalation_status="none")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await notify_manager_escalation(
        conversation=mock_conv,
        reason="B2B wholesale order",
        recent_messages=["user: I need 100 chairs"],
        db=mock_db,
        escalation_type=EscalationType.ORDER_CONFIRMATION,
        pdf_bytes=FAKE_PDF_BYTES,
        pdf_filename="quotation_SO-001.pdf",
    )

    # send_document should be called with PDF bytes
    mock_tg.send_document.assert_awaited_once()
    doc_call = mock_tg.send_document.call_args
    assert doc_call.kwargs.get("file_bytes") == FAKE_PDF_BYTES
    assert doc_call.kwargs.get("filename") == "quotation_SO-001.pdf"
    # Inline keyboard should also be sent
    mock_tg.send_message_with_inline_keyboard.assert_awaited_once()


# =============================================================================
# 2. Escalation without PDF sends only text + buttons
# =============================================================================


@pytest.mark.asyncio
@patch("src.integrations.notifications.escalation.TelegramClient")
async def test_escalation_without_pdf_no_document(
    mock_tg_cls: MagicMock,
) -> None:
    """When no pdf_bytes, escalation should NOT call send_document."""
    from src.integrations.notifications.escalation import notify_manager_escalation

    mock_tg = AsyncMock()
    mock_tg_cls.return_value = mock_tg
    mock_tg.send_document = AsyncMock()
    mock_tg.send_message_with_inline_keyboard = AsyncMock(return_value={"ok": True})

    mock_conv = _make_fake_conv(escalation_status="none")
    mock_db = AsyncMock()
    mock_db.add = MagicMock()

    await notify_manager_escalation(
        conversation=mock_conv,
        reason="Customer asked for manager",
        recent_messages=["user: Can I speak to a human?"],
        db=mock_db,
        escalation_type=EscalationType.HUMAN_REQUESTED,
    )

    # send_document should NOT be called
    mock_tg.send_document.assert_not_awaited()
    # But inline keyboard should still be sent
    mock_tg.send_message_with_inline_keyboard.assert_awaited_once()


# =============================================================================
# Shared helpers for _handle_order_decision tests
# =============================================================================


def _setup_mocks_for_order_decision(
    mock_redis: AsyncMock,
    mock_session_factory: MagicMock,
    pdf_b64_raw: bytes | None = None,
    meta_raw: bytes | None = None,
    escalation_status: str = "pending",
) -> tuple[AsyncMock, AsyncMock]:
    """Set up common mocks for _handle_order_decision tests.

    Returns (mock_tg_client, mock_wazzup).
    """

    # Redis mock
    async def mock_get(key: str) -> bytes | None:
        if "quotation_pdf:" in key and pdf_b64_raw is not None:
            return pdf_b64_raw
        if "quotation_meta:" in key and meta_raw is not None:
            return meta_raw
        return None

    mock_redis.get = AsyncMock(side_effect=mock_get)
    mock_redis.delete = AsyncMock()

    # DB session mock (for CR-1 idempotency)
    mock_db = AsyncMock()
    mock_conv = _make_fake_conv(escalation_status=escalation_status)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_conv
    mock_db.execute = AsyncMock(return_value=mock_result)
    mock_db.commit = AsyncMock()
    mock_db.add = MagicMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    # Telegram client mock
    mock_tg_client = AsyncMock()
    mock_tg_client.answer_callback_query = AsyncMock()
    mock_tg_client.send_message = AsyncMock()
    mock_tg_client.edit_message_reply_markup = AsyncMock()

    # Wazzup mock
    mock_wazzup = AsyncMock()
    mock_wazzup.send_media = AsyncMock(return_value="msg-id-123")
    mock_wazzup.send_text = AsyncMock(return_value="msg-id-456")
    mock_wazzup.close = AsyncMock()

    return mock_tg_client, mock_wazzup


# =============================================================================
# 3. Order confirm retrieves PDF from Redis, sends to client via Wazzup
# =============================================================================


@pytest.mark.asyncio
@patch("src.api.telegram_webhook._get_conversation_phone_and_lang")
@patch("src.api.telegram_webhook.async_session_factory")
@patch("src.api.telegram_webhook.redis_client")
async def test_order_confirm_sends_pdf_to_client(
    mock_redis: AsyncMock,
    mock_session_factory: MagicMock,
    mock_phone_fn: AsyncMock,
) -> None:
    """Confirm button should retrieve PDF from Redis and send via Wazzup."""
    from src.api.telegram_webhook import _handle_order_decision

    pdf_b64 = base64.b64encode(FAKE_PDF_BYTES).decode()
    meta_json = json.dumps(
        {"quote_number": "SO-001", "filename": "quotation_SO-001.pdf"}
    )

    mock_phone_fn.return_value = ("+971501234567", "en")
    mock_tg_client, mock_wazzup = _setup_mocks_for_order_decision(
        mock_redis,
        mock_session_factory,
        pdf_b64_raw=pdf_b64.encode(),
        meta_raw=meta_json.encode(),
    )

    with patch(
        "src.integrations.messaging.wazzup.WazzupProvider",
        return_value=mock_wazzup,
    ):
        await _handle_order_decision(
            client=mock_tg_client,
            callback_id="cb-123",
            chat_id=12345,
            message_id=999,
            mode="order_confirm",
            conv_id_str=FAKE_CONV_ID,
        )

    # PDF should be sent via Wazzup
    mock_wazzup.send_media.assert_awaited_once()
    media_call = mock_wazzup.send_media.call_args
    assert media_call.kwargs.get("content") == FAKE_PDF_BYTES
    assert media_call.kwargs.get("content_type") == "application/pdf"

    # Redis keys should be cleaned up
    mock_redis.delete.assert_awaited()


# =============================================================================
# 4. Order confirm with expired PDF gracefully handles missing data
# =============================================================================


@pytest.mark.asyncio
@patch("src.api.telegram_webhook._get_conversation_phone_and_lang")
@patch("src.api.telegram_webhook.async_session_factory")
@patch("src.api.telegram_webhook.redis_client")
async def test_order_confirm_no_pdf_graceful(
    mock_redis: AsyncMock,
    mock_session_factory: MagicMock,
    mock_phone_fn: AsyncMock,
) -> None:
    """Confirm with expired/missing PDF should still send text confirmation."""
    from src.api.telegram_webhook import _handle_order_decision

    mock_phone_fn.return_value = ("+971501234567", "en")
    mock_tg_client, mock_wazzup = _setup_mocks_for_order_decision(
        mock_redis,
        mock_session_factory,
        pdf_b64_raw=None,
        meta_raw=None,
    )

    with patch(
        "src.integrations.messaging.wazzup.WazzupProvider",
        return_value=mock_wazzup,
    ):
        await _handle_order_decision(
            client=mock_tg_client,
            callback_id="cb-456",
            chat_id=12345,
            message_id=999,
            mode="order_confirm",
            conv_id_str=FAKE_CONV_ID,
        )

    # Text confirmation still sent
    mock_wazzup.send_text.assert_awaited_once()
    # PDF NOT sent (since it expired)
    mock_wazzup.send_media.assert_not_awaited()

    # Manager should be notified about missing PDF
    msg_calls = [str(c) for c in mock_tg_client.send_message.call_args_list]
    assert any("PDF" in c for c in msg_calls)


# =============================================================================
# 5. Order reject deletes PDF and sends rejection text
# =============================================================================


@pytest.mark.asyncio
@patch("src.api.telegram_webhook._get_conversation_phone_and_lang")
@patch("src.api.telegram_webhook.async_session_factory")
@patch("src.api.telegram_webhook.redis_client")
async def test_order_reject_deletes_pdf(
    mock_redis: AsyncMock,
    mock_session_factory: MagicMock,
    mock_phone_fn: AsyncMock,
) -> None:
    """Reject should delete PDF from Redis and send rejection text."""
    from src.api.telegram_webhook import _handle_order_decision

    pdf_b64 = base64.b64encode(FAKE_PDF_BYTES).decode()
    mock_phone_fn.return_value = ("+971501234567", "en")
    mock_tg_client, mock_wazzup = _setup_mocks_for_order_decision(
        mock_redis,
        mock_session_factory,
        pdf_b64_raw=pdf_b64.encode(),
    )

    with patch(
        "src.integrations.messaging.wazzup.WazzupProvider",
        return_value=mock_wazzup,
    ):
        await _handle_order_decision(
            client=mock_tg_client,
            callback_id="cb-789",
            chat_id=12345,
            message_id=999,
            mode="order_reject",
            conv_id_str=FAKE_CONV_ID,
        )

    # Rejection text sent to client
    mock_wazzup.send_text.assert_awaited_once()

    # Redis cleanup should happen
    mock_redis.delete.assert_awaited()


# =============================================================================
# 6. Order reject does NOT send PDF to client
# =============================================================================


@pytest.mark.asyncio
@patch("src.api.telegram_webhook._get_conversation_phone_and_lang")
@patch("src.api.telegram_webhook.async_session_factory")
@patch("src.api.telegram_webhook.redis_client")
async def test_order_reject_no_pdf_to_client(
    mock_redis: AsyncMock,
    mock_session_factory: MagicMock,
    mock_phone_fn: AsyncMock,
) -> None:
    """Reject should NOT send PDF to client via Wazzup."""
    from src.api.telegram_webhook import _handle_order_decision

    mock_phone_fn.return_value = ("+971501234567", "en")
    mock_tg_client, mock_wazzup = _setup_mocks_for_order_decision(
        mock_redis,
        mock_session_factory,
    )

    with patch(
        "src.integrations.messaging.wazzup.WazzupProvider",
        return_value=mock_wazzup,
    ):
        await _handle_order_decision(
            client=mock_tg_client,
            callback_id="cb-000",
            chat_id=12345,
            message_id=999,
            mode="order_reject",
            conv_id_str=FAKE_CONV_ID,
        )

    # send_media should NOT be called for reject
    mock_wazzup.send_media.assert_not_awaited()
