import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.notifications.telegram import TelegramClient
from src.models.conversation import Conversation
from src.models.escalation import Escalation
from src.schemas.common import EscalationStatus, EscalationType
from src.services.inbound_channels import (
    should_send_manager_alert_for_conversation_with_db,
)

logger = logging.getLogger(__name__)


class _AlertNotDelivered(Exception):
    """Internal signal: the manager alert stopped short of being sent.

    Not an error. It carries the three quiet exits — gating, an unconfigured
    client, a failed call — to the one place that reports them.
    """


async def notify_manager_escalation(
    conversation: Conversation,
    reason: str,
    recent_messages: list[str],
    db: AsyncSession,
    *,
    escalation_type: EscalationType = EscalationType.GENERAL,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "quotation.pdf",
) -> None:
    """
    Notify the manager about a soft escalation via logging and Telegram.

    Args:
        conversation: The conversation being escalated.
        reason: The trigger reason from the escalation agent.
        recent_messages: List of recent message strings for context.
        db: Database session.
        escalation_type: Type of escalation (determines button layout).
        pdf_bytes: Optional PDF file bytes to attach as Telegram document.
        pdf_filename: Filename for the PDF attachment.
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

    # Persist the escalation row so manager-review jobs and audit paths can track it.
    conversation.escalation_status = EscalationStatus.PENDING.value
    db.add(
        Escalation(
            conversation_id=conversation.id,
            reason=reason,
            status=EscalationStatus.PENDING.value,
        )
    )
    await db.commit()

    # Send Telegram notification with action buttons (non-blocking).
    #
    # The escalation row above is already committed, so an escalation is never
    # lost. What can be lost is the manager finding out about it in time, and
    # until 2026-08-06 all three ways of losing it were quiet: channel gating
    # returned early at info level, an unconfigured client returned None, and
    # any failure was swallowed by the except below. A suppressed alert looked
    # exactly like a delivered one. Every path now ends at one warning that
    # says the manager was not notified and why.
    delivered = False
    undelivered_reason = ""
    try:
        if not await should_send_manager_alert_for_conversation_with_db(
            conversation, db
        ):
            undelivered_reason = (
                "inbound channel gating: telegram_test_mode_enabled is on and "
                "this conversation is not on the allowed inbound channel"
            )
            raise _AlertNotDelivered

        from src.services.notifications import format_escalation_message

        client = TelegramClient(
            bot_token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
        )

        # B13: Include conversation context in the alert
        context = "\n".join(recent_messages[-3:]) if recent_messages else None
        message = format_escalation_message(
            conversation.phone,
            conversation.id,
            reason,
            context=context,
        )

        # B12: Choose buttons based on escalation type
        conv_id_str = str(conversation.id)

        if escalation_type == EscalationType.ORDER_CONFIRMATION:
            buttons = [
                [
                    {
                        "text": "✅ Confirm order",
                        "callback_data": f"order_confirm:{conv_id_str}",
                    },
                    {
                        "text": "❌ Reject",
                        "callback_data": f"order_reject:{conv_id_str}",
                    },
                ],
                [
                    {
                        "text": "👤 Reply to customer",
                        "callback_data": f"faq_private:{conv_id_str}",
                    },
                ],
            ]
        else:
            buttons = [
                [
                    {
                        "text": "📚 To knowledge base",
                        "callback_data": f"faq_global:{conv_id_str}",
                    },
                    {
                        "text": "👤 Customer only",
                        "callback_data": f"faq_private:{conv_id_str}",
                    },
                ]
            ]

        sent = await client.send_message_with_inline_keyboard(message, buttons)
        if sent is None:
            undelivered_reason = "Telegram is not configured on this runtime"
            raise _AlertNotDelivered
        delivered = True

        # Send PDF document if provided (ORDER_CONFIRMATION with quotation)
        if pdf_bytes:
            try:
                await client.send_document(
                    file_bytes=pdf_bytes,
                    filename=pdf_filename,
                    caption="📄 Quotation for review",
                )
            except Exception:
                logger.exception("Failed to send PDF document to Telegram")

    except _AlertNotDelivered:
        pass
    except Exception:
        undelivered_reason = "the Telegram call raised"
        logger.exception("Failed to send Telegram escalation notification")

    if not delivered:
        logger.warning(
            "MANAGER NOT NOTIFIED of escalation for conversation %s (%s): %s. "
            "The escalation row is recorded and visible in the admin panel.",
            conversation.id,
            escalation_type,
            undelivered_reason or "unknown reason",
        )
