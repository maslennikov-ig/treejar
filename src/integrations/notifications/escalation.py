import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient
from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus
from src.services.notifications import _mask_phone

logger = logging.getLogger(__name__)


async def notify_manager_escalation(
    conversation: Conversation,
    reason: str,
    recent_messages: list[str],
    db: AsyncSession,
) -> None:
    """
    Notify the manager about a soft escalation.
    Currently logs the escalation. Can be extended to send a Telegram or Wazzup message.
    """
    logger.warning(
        "ESCALATION TRIGGERED for Conversation %s (%s). Reason: %s. Messages: %d",
        conversation.id,
        _mask_phone(conversation.phone),
        reason,
        len(recent_messages),
    )

    # Set the escalation state in the database
    conversation.escalation_status = EscalationStatus.PENDING.value
    await db.commit()
    await db.refresh(conversation)

    # Send Telegram notification with action buttons (non-blocking)
    try:
        from src.services.notifications import format_escalation_message

        client = TelegramClient(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
        )
        message = format_escalation_message(
            conversation.phone, conversation.id, reason
        )
        # Add inline keyboard for manager to respond
        conv_id_str = str(conversation.id)
        buttons = [
            [
                {
                    "text": "📚 В базу знаний",
                    "callback_data": f"faq_global:{conv_id_str}",
                },
                {
                    "text": "👤 Только клиенту",
                    "callback_data": f"faq_private:{conv_id_str}",
                },
            ]
        ]
        await client.send_message_with_inline_keyboard(message, buttons)
    except Exception:
        logger.exception("Failed to send Telegram escalation notification")
