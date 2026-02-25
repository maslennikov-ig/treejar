"""Context window manager.

Responsible for building the message history passed to the LLM agent,
including PII masking and context truncation.
"""
from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    UserPromptPart,
)
from sqlalchemy import select

from src.llm.pii import mask_pii
from src.models.message import Message

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Constants for context window sizing
# We keep the last N User/Assistant message pairs (so N * 2 individual messages)
MAX_RAW_MESSAGES = 10


async def build_message_history(
    db: AsyncSession,
    conversation_id: uuid.UUID | str,
    pii_map: dict[str, str],
) -> list[ModelMessage]:
    """Retrieve history from DB and format it for pydantic-ai, masking PII.

    This function:
    1. Fetches previous messages for the conversation, ordered by creation time.
    2. Converts them into pydantic-ai ModelMessage objects.
    3. Truncates older history to prevent blowing the context window.
    4. Masks any PII in user messages.

    Args:
        db: Active database session.
        conversation_id: The UUID of the conversation to load.
        pii_map: The mapping dictionary to store PII placeholders.

    Returns:
        List of formatted ModelMessage objects ready for agent.run().
    """
    if isinstance(conversation_id, str):
        conversation_id = uuid.UUID(conversation_id)

    # 1. Query past messages
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(stmt)
    db_messages = result.scalars().all()

    if not db_messages:
        return []

    # 2 & 3. Truncate
    # We only want the last MAX_RAW_MESSAGES
    # If there are more, we drop them. (For MVP, no summarization)
    if len(db_messages) > MAX_RAW_MESSAGES:
        logger.debug(
            f"Truncating history for conv {conversation_id} from "
            f"{len(db_messages)} to {MAX_RAW_MESSAGES}"
        )
        db_messages = db_messages[-MAX_RAW_MESSAGES:]

    # 4. Convert and mask
    history: list[ModelMessage] = []

    for msg in db_messages:
        if msg.role == "user":
            # Mask PII in incoming texts before AI sees it
            masked_text, new_pii_map = mask_pii(msg.content)
            # Update the global map passed in from the current turn
            pii_map.update(new_pii_map)

            history.append(
                ModelRequest(parts=[UserPromptPart(content=masked_text)])
            )
        elif msg.role == "assistant":
            # Assistant replies from the DB are safe as they were generated.
            history.append(
                ModelResponse(parts=[TextPart(content=msg.content)])
            )
        else:
            logger.warning(f"Unknown message role: {msg.role}")

    return history
