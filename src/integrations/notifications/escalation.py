import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import Conversation
from src.schemas.common import EscalationStatus

logger = logging.getLogger(__name__)

async def notify_manager_escalation(
    conversation: Conversation,
    reason: str,
    recent_messages: list[str],
    db: AsyncSession
) -> None:
    """
    Notify the manager about a soft escalation.
    Currently logs the escalation. Can be extended to send a Telegram or Wazzup message.
    """
    logger.warning(
        f"ESCALATION TRIGGERED for Conversation {conversation.id} ({conversation.phone}).\n"
        f"Reason: {reason}\n"
        f"Recent History: {recent_messages}"
    )

    # Set the escalation state in the database
    conversation.escalation_status = EscalationStatus.PENDING.value
    await db.commit()
    await db.refresh(conversation)

    # Future: send message to manager via Wazzup or Telegram using settings.manager_phone
