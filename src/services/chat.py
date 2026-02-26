from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select

from src.core.database import async_session_factory
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.wazzup import WazzupProvider
from src.llm.engine import process_message
from src.models.conversation import Conversation
from src.models.message import Message
from src.rag.embeddings import EmbeddingEngine
from src.schemas.webhook import WazzupIncomingMessage

logger = logging.getLogger(__name__)


async def process_incoming_batch(
    ctx: dict[str, Any],
    chat_id: str,
    messages: list[WazzupIncomingMessage],
) -> None:
    """Process a batch of incoming messages from a single chat.

    1. Get or create conversation based on chat_id (phone number).
    2. Save incoming messages.
    3. Generate LLM response from the combined text.
    4. Save LLM response.
    5. Send reply via Wazzup.
    """
    logger.info(f"Processing batch for {chat_id} with {len(messages)} messages.")

    # Sort messages by timestamp asc
    messages.sort(key=lambda m: m.timestamp)
    combined_text = "\n".join(m.text for m in messages if m.text)

    if not combined_text.strip():
        logger.warning(f"No text content in batch for {chat_id}, skipping.")
        return

    async with async_session_factory() as db:
        # 1. Get or create conversation
        stmt = select(Conversation).where(Conversation.phone == chat_id)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            logger.info(f"Creating new conversation for {chat_id}")
            conv = Conversation(phone=chat_id)
            db.add(conv)
            await db.flush()

        # 2. Save incoming messages
        for m in messages:
            # We skip duplicates based on wazzup_message_id unique index constraint
            # Check if exists first to avoid exception in flush
            msg_stmt = select(Message).where(Message.wazzup_message_id == m.messageId)
            msg_result = await db.execute(msg_stmt)
            if not msg_result.scalar_one_or_none():
                new_msg = Message(
                    conversation_id=conv.id,
                    role="user",
                    content=m.text or "",
                    wazzup_message_id=m.messageId,
                )
                db.add(new_msg)

        await db.commit()

        # 3. Process LLM
        # We need Redis, EmbeddingEngine, ZohoClient
        # In a real app these typically come from the ARQ context or are instantiated here
        embedding_engine = EmbeddingEngine()
        redis = ctx.get("redis")
        zoho_client = ZohoInventoryClient(redis_client=redis)
        crm_client = ZohoCRMClient(redis_client=redis)

        logger.info(f"Calling LLM for {chat_id}")
        llm_response = await process_message(
            conversation_id=conv.id,
            combined_text=combined_text,
            db=db,
            redis=redis,
            embedding_engine=embedding_engine,
            zoho_client=zoho_client,
            crm_client=crm_client,
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
        logger.info(f"Sending reply to {chat_id} via Wazzup")
        wazzup_provider = WazzupProvider()
        await wazzup_provider.send_text(
            chat_id=chat_id,
            text=llm_response.text,
        )
