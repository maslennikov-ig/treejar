from __future__ import annotations

import asyncio
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

# Maximum time to wait for LLM response (seconds)
LLM_TIMEOUT = 120


def _determine_role(msg: WazzupIncomingMessage) -> str:
    """Determine message role based on Wazzup authorType field.

    Returns:
        'manager' if authorType is 'manager', otherwise 'user'.
    """
    if msg.authorType == "manager":
        return "manager"
    return "user"


async def process_incoming_batch(
    ctx: dict[str, Any],
    chat_id: str,
) -> None:
    """Process a batch of incoming messages from a single chat.

    Messages are read from a Redis list (``wazzup_msgs:{chat_id}``) where
    the webhook handler pushes them via ``rpush``.

    1. Pop all queued messages from Redis.
    2. Get or create conversation based on chat_id (phone number).
    3. Save incoming messages (with correct role: user/manager).
    4. If escalation is active or message is from manager → skip LLM.
    5. Otherwise generate LLM response, save, and send via Wazzup.
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

    # Determine roles for each message
    has_manager_message = any(m.authorType == "manager" for m in messages)
    manager_name = next(
        (m.authorName for m in messages if m.authorType == "manager" and m.authorName),
        None,
    )
    combined_text = "\n".join(m.text for m in messages if m.text)

    # Check for audio/voice messages and transcribe them
    audio_url: str | None = None
    transcription: str | None = None
    audio_messages = [m for m in messages if m.type in ("audio", "voice") and m.media and m.media.url]
    if audio_messages:
        from src.integrations.voice.voxtral import MAX_AUDIO_SIZE, transcribe_audio

        transcriptions: list[str] = []
        try:
            async with WazzupProvider(channel_id=settings.wazzup_channel_id) as wazzup_dl:
                for audio_msg in audio_messages:
                    if audio_msg.media is None:
                        continue  # CR-V-01: safe guard instead of assert
                    audio_url = audio_msg.media.url
                    logger.info(
                        "Audio message detected for %s, downloading from %s",
                        chat_id,
                        audio_url,
                    )
                    audio_bytes = await wazzup_dl.download_media(audio_url)

                    # CR-V-02: size limit check
                    if len(audio_bytes) > MAX_AUDIO_SIZE:
                        logger.warning(
                            "Audio too large for %s: %d bytes (max %d)",
                            chat_id,
                            len(audio_bytes),
                            MAX_AUDIO_SIZE,
                        )
                        await wazzup_dl.send_text(
                            chat_id=chat_id,
                            text=(
                                "The voice message is too large to process. "
                                "Please send a shorter message.\n"
                                "الرسالة الصوتية كبيرة جداً. يرجى إرسال رسالة أقصر."
                            ),
                        )
                        return

                    # CR-V-11: robust MIME → format mapping
                    mime = (audio_msg.media.mimeType or "").split(";")[0].strip()
                    format_map = {
                        "audio/ogg": "ogg",
                        "audio/mpeg": "mp3",
                        "audio/mp3": "mp3",
                        "audio/wav": "wav",
                        "audio/x-wav": "wav",
                        "audio/webm": "webm",
                    }
                    audio_format = format_map.get(mime, "mp3")

                    t = await transcribe_audio(audio_bytes, audio_format=audio_format)
                    if t:
                        transcriptions.append(t)
                        logger.info("Transcription for %s: %s", chat_id, t[:200])

            # CR-V-06: combine all transcriptions
            if transcriptions:
                transcription = "\n".join(transcriptions)
                combined_text = (
                    transcription
                    if not combined_text.strip()
                    else f"{combined_text}\n{transcription}"
                )

        except Exception:
            logger.exception("Failed to transcribe audio for %s", chat_id)
            # CR-V-07: bilingual fallback message
            async with WazzupProvider(channel_id=settings.wazzup_channel_id) as wazzup_fallback:
                await wazzup_fallback.send_text(
                    chat_id=chat_id,
                    text=(
                        "Sorry, I couldn't process your voice message. "
                        "Could you please type your message instead?\n"
                        "عذراً، لم أتمكن من معالجة الرسالة الصوتية. "
                        "هل يمكنك كتابة رسالتك بدلاً من ذلك؟"
                    ),
                )
            return

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

        # 2. Manual takeover: manager writes when no escalation is active
        if has_manager_message and conv.escalation_status in ("none", None):
            conv.escalation_status = "manual_takeover"
            logger.info(
                "Manual takeover for %s by manager %s",
                chat_id,
                manager_name or "unknown",
            )

        # 3. Save incoming messages (deduplicate by wazzup_message_id)
        message_ids = [m.messageId for m in messages if m.messageId]
        existing_msgs_stmt = select(Message.wazzup_message_id).where(
            Message.wazzup_message_id.in_(message_ids)
        )
        existing_result = await db.execute(existing_msgs_stmt)
        existing_ids = set(existing_result.scalars().all())

        for m in messages:
            if m.messageId and m.messageId not in existing_ids:
                role = _determine_role(m)
                is_audio = m.type in ("audio", "voice")
                new_msg = Message(
                    conversation_id=conv.id,
                    role=role,
                    content=transcription if is_audio and transcription else (m.text or ""),
                    message_type=m.type,
                    wazzup_message_id=m.messageId,
                    audio_url=audio_url if is_audio else None,
                    transcription=transcription if is_audio else None,
                )
                db.add(new_msg)
                existing_ids.add(m.messageId)

        await db.commit()

        # 4. Bot silencing: if escalation is active, don't call LLM
        if conv.escalation_status not in ("none", None):
            logger.info(
                "Escalation active (%s) for %s. Saving messages but NOT calling LLM.",
                conv.escalation_status,
                chat_id,
            )
            return

        # 5. Generate LLM response
        embedding_engine = EmbeddingEngine()

        # CR-WA-01 fix: pass channel_id from settings to WazzupProvider
        async with (
            ZohoInventoryClient(redis_client=redis) as zoho_client,
            ZohoCRMClient(redis_client=redis) as crm_client,
            WazzupProvider(
                channel_id=settings.wazzup_channel_id,
            ) as wazzup_provider,
        ):
            logger.info("Calling LLM for %s (timeout=%ds)", chat_id, LLM_TIMEOUT)
            try:
                llm_response = await asyncio.wait_for(
                    process_message(
                        conversation_id=conv.id,
                        combined_text=combined_text,
                        db=db,
                        redis=redis,
                        embedding_engine=embedding_engine,
                        zoho_client=zoho_client,
                        crm_client=crm_client,
                        messaging_client=wazzup_provider,
                    ),
                    timeout=LLM_TIMEOUT,
                )
            except TimeoutError:
                logger.error(
                    "LLM timeout after %ds for chat_id=%s", LLM_TIMEOUT, chat_id
                )
                # Send a fallback message so the user isn't left hanging
                await wazzup_provider.send_text(
                    chat_id=chat_id,
                    text="Извините, я сейчас перегружен. Пожалуйста, попробуйте написать ещё раз через минуту.",
                )
                return

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
