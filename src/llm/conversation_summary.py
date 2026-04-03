from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import async_session_factory
from src.llm.pii import mask_pii, unmask_pii
from src.models.conversation_summary import ConversationSummary
from src.models.message import Message

logger = logging.getLogger(__name__)

SUMMARY_VERSION = 1
SUMMARY_TAIL_MESSAGES = 4
SUMMARY_SOFT_LIMIT_CHARS = 1200

SUMMARY_SYSTEM_PROMPT = f"""\
You compress older sales-conversation history into a compact fact summary.

Return ONLY plain text using this exact section order:
Customer / company:
Products and needs:
Commercial facts:
Logistics / constraints:
Decisions and current stage:
Open questions / next step:
Escalation-sensitive signals:

Rules:
- Facts only. No narrative paragraphs.
- Keep each section short. Use '- none' if there is nothing useful.
- Prefer concrete facts, products, quantities, prices, delivery details, and next-step state.
- Merge the current summary with the new messages and deduplicate repeated facts.
- Keep the whole summary around {SUMMARY_SOFT_LIMIT_CHARS} characters when possible.
"""

summary_model = OpenAIChatModel(
    settings.openrouter_model_fast,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

summary_agent: Agent[None, str] = Agent(
    model=summary_model,
    system_prompt=SUMMARY_SYSTEM_PROMPT,
)


def should_enqueue_conversation_summary_refresh(
    total_messages: int,
    has_summary: bool,
) -> bool:
    """Decide whether to queue a background summary refresh."""
    return total_messages > 8 or has_summary


async def _load_conversation_summary(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> ConversationSummary | None:
    result = await db.execute(
        select(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id
        )
    )
    return result.scalar_one_or_none()


async def _load_conversation_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> list[Message]:
    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
    )
    return list(result.scalars().all())


def _messages_to_summarize(
    messages: list[Message],
    summary: ConversationSummary | None,
) -> list[Message]:
    if len(messages) <= SUMMARY_TAIL_MESSAGES:
        return []

    eligible_messages = messages[:-SUMMARY_TAIL_MESSAGES]
    if not summary or not summary.covered_through_message_id:
        return eligible_messages

    covered_index = next(
        (
            index
            for index, message in enumerate(eligible_messages)
            if message.id == summary.covered_through_message_id
        ),
        None,
    )
    if covered_index is None:
        return eligible_messages

    return eligible_messages[covered_index + 1 :]


def needs_conversation_summary_refresh(
    messages: list[Message],
    summary: ConversationSummary | None,
) -> bool:
    """Return True when there are older messages not yet covered."""
    return bool(_messages_to_summarize(messages, summary))


def _build_summary_prompt(
    current_summary: str | None,
    messages: list[Message],
) -> tuple[str, dict[str, str]]:
    pii_map: dict[str, str] = {}

    if current_summary:
        masked_summary, summary_pii = mask_pii(current_summary)
        pii_map.update(summary_pii)
        summary_block = masked_summary
    else:
        summary_block = "- none"

    message_lines: list[str] = []
    for message in messages:
        content = message.content.strip()
        if not content:
            continue

        masked_content, content_pii = mask_pii(content)
        pii_map.update(content_pii)

        role = "Customer" if message.role == "user" else "Assistant"
        message_lines.append(f"{role}: {masked_content}")

    if not message_lines:
        message_lines.append("- none")

    prompt = (
        "[CURRENT SUMMARY]\n"
        f"{summary_block}\n\n"
        "[NEWLY ELIGIBLE MESSAGES TO MERGE]\n"
        f"{chr(10).join(message_lines)}"
    )
    return prompt, pii_map


async def refresh_conversation_summary_record(
    db: AsyncSession,
    conversation_id: uuid.UUID | str,
) -> ConversationSummary | None:
    """Refresh the persistent conversation summary incrementally."""
    if isinstance(conversation_id, str):
        conversation_id = uuid.UUID(conversation_id)

    summary = await _load_conversation_summary(db, conversation_id)
    messages = await _load_conversation_messages(db, conversation_id)
    messages_to_merge = _messages_to_summarize(messages, summary)

    if not messages_to_merge:
        return None

    prompt, pii_map = _build_summary_prompt(
        summary.summary_text if summary else None,
        messages_to_merge,
    )
    result = await asyncio.wait_for(summary_agent.run(prompt), timeout=45.0)
    refreshed_summary = unmask_pii(result.output.strip(), pii_map)

    if summary is None:
        summary = ConversationSummary(
            conversation_id=conversation_id,
            summary_text=refreshed_summary,
            covered_through_message_id=messages_to_merge[-1].id,
            model=settings.openrouter_model_fast,
            version=SUMMARY_VERSION,
        )
        db.add(summary)
    else:
        summary.summary_text = refreshed_summary
        summary.covered_through_message_id = messages_to_merge[-1].id
        summary.model = settings.openrouter_model_fast
        summary.version = SUMMARY_VERSION

    await db.commit()
    return summary


async def refresh_conversation_summary(
    ctx: dict[str, Any],
    conversation_id: str,
) -> None:
    """ARQ job wrapper for conversation summary refresh."""
    del ctx

    try:
        async with async_session_factory() as db:
            await refresh_conversation_summary_record(db, conversation_id)
    except Exception:
        logger.exception(
            "Conversation summary refresh failed for conversation_id=%s",
            conversation_id,
        )
