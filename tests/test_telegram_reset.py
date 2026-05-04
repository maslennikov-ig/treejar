from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import settings
from src.models.conversation import Conversation


class _DbContext:
    def __init__(self, db: AsyncMock) -> None:
        self.db = db

    async def __aenter__(self) -> AsyncMock:
        return self.db

    async def __aexit__(self, *_args: object) -> bool:
        return False


@pytest.fixture
def telegram_chat_settings() -> object:
    original_chat_id = settings.telegram_chat_id
    settings.telegram_chat_id = "-100123456789"
    yield
    settings.telegram_chat_id = original_chat_id


@pytest.mark.asyncio
async def test_reset_command_sends_preview_and_does_not_mutate_db(
    telegram_chat_settings: object,
) -> None:
    from src.api.telegram_webhook import _handle_reset_command_if_present
    from src.services.conversation_reset import ResetPreview

    db = AsyncMock()
    redis = AsyncMock()
    telegram = AsyncMock()
    preview = ResetPreview(
        phone="+79262810921",
        phone_variants=("+79262810921", "79262810921"),
        conversation_count=2,
        latest_conversation_id=uuid.uuid4(),
        message_count=5,
        pending_escalation_count=1,
    )

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook.async_session_factory",
            MagicMock(return_value=_DbContext(db)),
        ),
        patch(
            "src.api.telegram_webhook.build_reset_preview",
            new=AsyncMock(return_value=preview),
        ) as build_preview,
        patch(
            "src.api.telegram_webhook.execute_conversation_reset",
            new=AsyncMock(side_effect=AssertionError("preview must not reset")),
        ),
    ):
        handled = await _handle_reset_command_if_present(
            {
                "chat": {"id": -100123456789},
                "from": {"id": 777},
                "text": "/reset +7 926 281-09-21",
            }
        )

    assert handled is True
    build_preview.assert_awaited_once()
    redis.setex.assert_awaited_once()
    assert redis.setex.await_args.args[0].startswith("tg_reset_pending:")
    assert redis.setex.await_args.args[1] == 300
    pending_payload = json.loads(redis.setex.await_args.args[2])
    assert pending_payload["phone"] == "+79262810921"
    assert pending_payload["requested_by_telegram_user_id"] == 777
    telegram.send_message_with_inline_keyboard.assert_awaited_once()
    text = telegram.send_message_with_inline_keyboard.await_args.args[0]
    buttons = telegram.send_message_with_inline_keyboard.await_args.args[1]
    assert "Клиенту ничего не отправится" in text
    assert "2" in text
    assert buttons[0][0]["callback_data"].startswith("reset_confirm:")
    assert buttons[0][1]["callback_data"].startswith("reset_cancel:")
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_command_from_non_admin_chat_is_ignored(
    telegram_chat_settings: object,
) -> None:
    from src.api.telegram_webhook import _handle_reset_command_if_present

    telegram = AsyncMock()

    with patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram):
        handled = await _handle_reset_command_if_present(
            {
                "chat": {"id": -100999999999},
                "from": {"id": 777},
                "text": "/reset +79262810921",
            }
        )

    assert handled is True
    telegram.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_command_invalid_phone_returns_usage(
    telegram_chat_settings: object,
) -> None:
    from src.api.telegram_webhook import _handle_reset_command_if_present

    telegram = AsyncMock()

    with patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram):
        handled = await _handle_reset_command_if_present(
            {
                "chat": {"id": -100123456789},
                "from": {"id": 777},
                "text": "/reset not-a-phone",
            }
        )

    assert handled is True
    telegram.send_message.assert_awaited_once()
    assert "Использование" in telegram.send_message.await_args.args[0]


@pytest.mark.asyncio
async def test_reset_confirm_by_same_user_executes_reset(
    telegram_chat_settings: object,
) -> None:
    from src.api.telegram_webhook import _handle_callback_query
    from src.services.conversation_reset import ResetResult

    token = "abc123"
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "phone": "+79262810921",
            "requested_by_telegram_user_id": 777,
            "chat_id": -100123456789,
        }
    )
    telegram = AsyncMock()
    db = AsyncMock()
    new_conv = Conversation(
        id=uuid.uuid4(),
        phone="+79262810921",
        sales_stage="greeting",
        language="en",
        status="active",
        escalation_status="none",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        metadata_={},
    )

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook.async_session_factory",
            MagicMock(return_value=_DbContext(db)),
        ),
        patch(
            "src.api.telegram_webhook.execute_conversation_reset",
            new=AsyncMock(
                return_value=ResetResult(
                    phone="+79262810921",
                    archived_count=2,
                    new_conversation=new_conv,
                )
            ),
        ) as execute_reset,
    ):
        await _handle_callback_query(
            {
                "id": "callback-1",
                "from": {"id": 777},
                "data": f"reset_confirm:{token}",
                "message": {"chat": {"id": -100123456789}, "message_id": 55},
            }
        )

    redis.get.assert_awaited_once_with(f"tg_reset_pending:{token}")
    execute_reset.assert_awaited_once_with(
        db,
        "+79262810921",
        requested_by_telegram_user_id=777,
    )
    db.commit.assert_awaited_once()
    redis.delete.assert_awaited_once_with(f"tg_reset_pending:{token}")
    telegram.answer_callback_query.assert_awaited_once_with(
        "callback-1", "✅ Reset done"
    )
    telegram.edit_message_reply_markup.assert_awaited_once_with(-100123456789, 55)
    sent_text = telegram.send_message.await_args.args[0]
    assert "Готово" in sent_text
    assert str(new_conv.id) in sent_text


@pytest.mark.asyncio
async def test_reset_confirm_by_different_user_is_rejected(
    telegram_chat_settings: object,
) -> None:
    from src.api.telegram_webhook import _handle_callback_query

    token = "abc123"
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "phone": "+79262810921",
            "requested_by_telegram_user_id": 777,
            "chat_id": -100123456789,
        }
    )
    telegram = AsyncMock()

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook.execute_conversation_reset",
            new=AsyncMock(side_effect=AssertionError("must not reset")),
        ),
    ):
        await _handle_callback_query(
            {
                "id": "callback-1",
                "from": {"id": 888},
                "data": f"reset_confirm:{token}",
                "message": {"chat": {"id": -100123456789}, "message_id": 55},
            }
        )

    telegram.answer_callback_query.assert_awaited_once_with(
        "callback-1",
        "❌ Only the admin who requested reset can confirm it",
    )
    redis.delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_reset_cancel_deletes_pending_token_without_mutation(
    telegram_chat_settings: object,
) -> None:
    from src.api.telegram_webhook import _handle_callback_query

    token = "abc123"
    redis = AsyncMock()
    redis.get.return_value = json.dumps(
        {
            "phone": "+79262810921",
            "requested_by_telegram_user_id": 777,
            "chat_id": -100123456789,
        }
    )
    telegram = AsyncMock()

    with (
        patch("src.api.telegram_webhook.redis_client", redis),
        patch("src.api.telegram_webhook._get_telegram_client", return_value=telegram),
        patch(
            "src.api.telegram_webhook.execute_conversation_reset",
            new=AsyncMock(side_effect=AssertionError("must not reset")),
        ),
    ):
        await _handle_callback_query(
            {
                "id": "callback-1",
                "from": {"id": 777},
                "data": f"reset_cancel:{token}",
                "message": {"chat": {"id": -100123456789}, "message_id": 55},
            }
        )

    redis.delete.assert_awaited_once_with(f"tg_reset_pending:{token}")
    telegram.answer_callback_query.assert_awaited_once_with(
        "callback-1",
        "✅ Reset cancelled",
    )
    telegram.edit_message_reply_markup.assert_awaited_once_with(-100123456789, 55)
    assert "отменён" in telegram.send_message.await_args.args[0]
