from __future__ import annotations

import logging
import traceback
from typing import Any

from sqlalchemy import select

from src.core.config import settings
from src.core.database import async_session_factory
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.wazzup import WazzupProvider
from src.llm.engine import process_message
from src.models.conversation import Conversation
from src.models.message import Message
from src.models.system_config import SystemConfig
from src.rag.embeddings import EmbeddingEngine
from src.schemas.webhook import WazzupIncomingMessage

logger = logging.getLogger(__name__)


async def process_incoming_batch(
    ctx: dict[str, Any],
    chat_id: str,
) -> None:
    """Process a batch of incoming messages from a single chat.

    Messages are read from a Redis list (``wazzup_msgs:{chat_id}``) where
    the webhook handler pushes them via ``rpush``.

    1. Pop all queued messages from Redis.
    2. Get or create conversation based on chat_id (phone number).
    3. Save incoming messages.
    4. Generate LLM response from the combined text.
    5. Save LLM response.
    6. Send reply via Wazzup.
    """
    # ARQ automatically injects its Redis pool as ctx["redis"]
    redis = ctx["redis"]

    try:
        await _process_batch_inner(redis, chat_id)
    except Exception:
        logger.exception("Failed to process batch for chat_id=%s", chat_id)
        traceback.print_exc()
        raise  # Let ARQ mark the job as failed


async def _process_batch_inner(redis: Any, chat_id: str) -> None:
    """Inner implementation — separated for clean error handling."""
    # 1. Pop all messages from Redis list
    raw_messages: list[str] = []
    while True:
        raw = await redis.lpop(f"wazzup_msgs:{chat_id}")
        if raw is None:
            break
        raw_messages.append(raw if isinstance(raw, str) else raw.decode())

    if not raw_messages:
        logger.warning("No messages in Redis for %s, skipping.", chat_id)
        return

    messages = [WazzupIncomingMessage.model_validate_json(raw) for raw in raw_messages]
    logger.info("Processing batch for %s with %d messages.", chat_id, len(messages))

    # Sort messages by dateTime (Wazzup v3 format) or timestamp (legacy)
    messages.sort(key=lambda m: m.dateTime or str(m.timestamp or 0))
    combined_text = "\n".join(m.text for m in messages if m.text)

    if not combined_text.strip():
        logger.warning("No text content in batch for %s, skipping.", chat_id)
        return

    async with async_session_factory() as db:
        # 0. Check if bot is enabled
        cfg_stmt = select(SystemConfig).where(SystemConfig.key == "bot_enabled")
        cfg_result = await db.execute(cfg_stmt)
        bot_enabled_cfg = cfg_result.scalars().first()
        if bot_enabled_cfg and (
            bot_enabled_cfg.value is False
            or str(bot_enabled_cfg.value).lower() == "false"
        ):
            logger.info("Bot is globally disabled. Skipping batch for %s", chat_id)
            return

        # 1. Get or create conversation
        stmt = select(Conversation).where(Conversation.phone == chat_id)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            logger.info("Creating new conversation for %s", chat_id)
            conv = Conversation(phone=chat_id)
            db.add(conv)
            await db.flush()

        # 2. Save incoming messages (deduplicate by wazzup_message_id)
        message_ids = [m.messageId for m in messages if m.messageId]
        existing_msgs_stmt = select(Message.wazzup_message_id).where(
            Message.wazzup_message_id.in_(message_ids)
        )
        existing_result = await db.execute(existing_msgs_stmt)
        existing_ids = set(existing_result.scalars().all())

        for m in messages:
            if m.messageId and m.messageId not in existing_ids:
                new_msg = Message(
                    conversation_id=conv.id,
                    role="user",
                    content=m.text or "",
                    wazzup_message_id=m.messageId,
                )
                db.add(new_msg)
                existing_ids.add(m.messageId)

        await db.commit()

        # 3. Generate LLM response
        embedding_engine = EmbeddingEngine()

        # CR-WA-01 fix: pass channel_id from settings to WazzupProvider
        async with (
            ZohoInventoryClient(redis_client=redis) as zoho_client,
            ZohoCRMClient(redis_client=redis) as crm_client,
            WazzupProvider(
                channel_id=settings.wazzup_channel_id,
            ) as wazzup_provider,
        ):
            logger.info("Calling LLM for %s", chat_id)
            llm_response = await process_message(
                conversation_id=conv.id,
                combined_text=combined_text,
                db=db,
                redis=redis,
                embedding_engine=embedding_engine,
                zoho_client=zoho_client,
                crm_client=crm_client,
                messaging_client=wazzup_provider,
            )

            # 4. Save response to DB
            assistant_msg = Message(
                conversation_id=conv.id,
                role="assistant",
                content=llm_response.text,
                tokens_in=llm_response.tokens_in,
                tokens_out=llm_response.tokens_out,
                cost=llm_response.cost,
                model=llm_response.model,
            )
            db.add(assistant_msg)
            await db.commit()

            # 5. Send via Wazzup
            logger.info("Sending reply to %s via Wazzup", chat_id)
            await wazzup_provider.send_text(
                chat_id=chat_id,
                text=llm_response.text,
            )
            logger.info("Reply sent to %s successfully", chat_id)
