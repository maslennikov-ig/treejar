import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient
from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus, EscalationType

logger = logging.getLogger(__name__)


async def notify_manager_escalation(
    conversation: Conversation,
    reason: str,
    recent_messages: list[str],
    db: AsyncSession,
    *,
    escalation_type: EscalationType = EscalationType.GENERAL,
) -> None:
    """
    Notify the manager about a soft escalation via logging and Telegram.

    Args:
        conversation: The conversation being escalated.
        reason: The trigger reason from the escalation agent.
        recent_messages: List of recent message strings for context.
        db: Database session.
        escalation_type: Type of escalation (determines button layout).
    """
    phone_display = (
        conversation.phone
        if conversation.phone.startswith("+")
        else f"+{conversation.phone}"
    )
    logger.warning(
        "ESCALATION TRIGGERED for Conversation %s (%s). Reason: %s. Type: %s. Messages: %d",
        conversation.id,
        phone_display,
        reason,
        escalation_type,
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

        # B13: Include conversation context in the alert
        context = "\n".join(recent_messages[-3:]) if recent_messages else None
        message = format_escalation_message(
            conversation.phone, conversation.id, reason, context=context,
        )

        # B12: Choose buttons based on escalation type
        conv_id_str = str(conversation.id)

        if escalation_type == EscalationType.ORDER_CONFIRMATION:
            buttons = [
                [
                    {
                        "text": "✅ Подтвердить заказ",
                        "callback_data": f"order_confirm:{conv_id_str}",
                    },
                    {
                        "text": "❌ Отклонить",
                        "callback_data": f"order_reject:{conv_id_str}",
                    },
                ],
                [
                    {
                        "text": "👤 Ответить клиенту",
                        "callback_data": f"faq_private:{conv_id_str}",
                    },
                ],
            ]
        else:
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
