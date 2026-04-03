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
    SystemPromptPart,
    TextPart,
    UserPromptPart,
)
from sqlalchemy import select

from src.llm.pii import mask_pii
from src.models.conversation_summary import ConversationSummary
from src.models.message import Message

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Constants for context window sizing
RECENT_MESSAGE_CANDIDATE_WINDOW = 24
VERBATIM_TAIL_MESSAGES = 4
MAX_RAW_MESSAGES = 8
MAX_RAW_CHARS = 3000
SUMMARY_PREFIX = "[EARLIER CONVERSATION SUMMARY - FACTS ONLY]"


def _select_raw_tail(messages_desc: list[Message]) -> list[Message]:
    if not messages_desc:
        return []

    recent_messages = list(reversed(messages_desc))
    if len(recent_messages) <= VERBATIM_TAIL_MESSAGES:
        return recent_messages

    selected = recent_messages[-VERBATIM_TAIL_MESSAGES:]
    raw_chars = sum(len(message.content) for message in selected)

    for message in reversed(recent_messages[:-VERBATIM_TAIL_MESSAGES]):
        next_char_total = raw_chars + len(message.content)
        if len(selected) >= MAX_RAW_MESSAGES or next_char_total > MAX_RAW_CHARS:
            break
        selected.insert(0, message)
        raw_chars = next_char_total

    return selected


def _messages_newer_than_summary_boundary(
    messages_desc: list[Message],
    summary: ConversationSummary | None,
) -> list[Message]:
    if not summary or not summary.covered_through_message_id:
        return messages_desc

    recent_messages = list(reversed(messages_desc))
    boundary_index = next(
        (
            index
            for index, message in enumerate(recent_messages)
            if message.id == summary.covered_through_message_id
        ),
        None,
    )
    if boundary_index is None:
        return messages_desc

    return list(reversed(recent_messages[boundary_index + 1 :]))


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

    summary_result = await db.execute(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
    )
    summary = summary_result.scalar_one_or_none()
    if not isinstance(summary, ConversationSummary):
        summary = None

    # 1. Query a recent candidate window from DB
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(RECENT_MESSAGE_CANDIDATE_WINDOW)
    )
    result = await db.execute(stmt)
    db_messages = list(result.scalars().all())

    if not db_messages and not (summary and summary.summary_text):
        return []

    selected_messages = _select_raw_tail(
        _messages_newer_than_summary_boundary(db_messages, summary)
    )

    # 4. Convert and mask
    history: list[ModelMessage] = []

    if summary and summary.summary_text:
        masked_summary, summary_pii = mask_pii(summary.summary_text)
        pii_map.update(summary_pii)
        history.append(
            ModelRequest(
                parts=[
                    SystemPromptPart(
                        content=f"{SUMMARY_PREFIX}\n{masked_summary}",
                    )
                ]
            )
        )

    for msg in selected_messages:
        if msg.role == "user":
            # Mask PII in incoming texts before AI sees it
            masked_text, new_pii_map = mask_pii(msg.content)
            # Update the global map passed in from the current turn
            pii_map.update(new_pii_map)

            history.append(ModelRequest(parts=[UserPromptPart(content=masked_text)]))
        elif msg.role == "assistant":
            # Assistant replies from the DB are safe as they were generated.
            history.append(ModelResponse(parts=[TextPart(content=msg.content)]))
        else:
            logger.warning(f"Unknown message role: {msg.role}")

    return history
