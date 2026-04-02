from __future__ import annotations

import asyncio
import logging
import re
import traceback
from typing import Any

import httpx
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

# WhatsApp Formatting Regexes
WHATSAPP_HEADERS_RE = re.compile(
    r"^#{1,6}\s*\*{0,3}\s*(.+?)\s*\*{0,3}\s*$", flags=re.MULTILINE
)
WHATSAPP_BOLD_RE = re.compile(r"\*{2,3}(.*?)\*{2,3}")
WHATSAPP_INLINE_CODE_RE = re.compile(r"(?<!`)(`)([^`]+)\1(?!`)")
WHATSAPP_IMG_RE = re.compile(r"!\[(.*?)\]\((.*?)\)")
WHATSAPP_LINK_RE = re.compile(r"\[(.*?)\]\((.*?)\)")
# Matches a markdown table separator row: | --- | --- | or |:---:|:---|
WHATSAPP_TABLE_SEP_RE = re.compile(
    r"^\|?[\s:]*-{2,}[\s:]*(\|[\s:]*-{2,}[\s:]*)+\|?\s*$"
)
WHATSAPP_HR_RE = re.compile(r"^\s*-{3,}\s*$", flags=re.MULTILINE)
WHATSAPP_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _convert_markdown_table(text: str) -> str:
    """Detect Markdown tables and convert them into key-value lists.

    A Markdown table is identified by:
    - A header row with pipes: | Col1 | Col2 |
    - A separator row: | --- | --- |
    - One or more data rows: | val1 | val2 |

    Converted into:
    *Col1:* val1
    *Col2:* val2
    (blank line between rows)
    """
    lines = text.split("\n")
    result: list[str] = []
    i = 0

    while i < len(lines):
        # Look for a separator row to identify a table
        if i >= 1 and WHATSAPP_TABLE_SEP_RE.match(lines[i]):
            # Header is the line before the separator
            header_line = lines[i - 1]
            headers = [h.strip() for h in header_line.strip().strip("|").split("|")]
            headers = [h for h in headers if h]

            if not headers:
                result.append(lines[i])
                i += 1
                continue

            # Remove the header line we already added to result
            if result and result[-1] == lines[i - 1]:
                result.pop()

            # Skip the separator row
            i += 1

            # Process data rows
            data_rows: list[str] = []
            while (
                i < len(lines)
                and "|" in lines[i]
                and not lines[i].strip().startswith("#")
            ):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                row_parts: list[str] = []
                for col_idx, cell in enumerate(cells):
                    if col_idx < len(headers) and cell:
                        row_parts.append(f"*{headers[col_idx]}:* {cell}")
                if row_parts:
                    data_rows.append("\n".join(row_parts))
                i += 1

            result.append("\n\n".join(data_rows))
        else:
            result.append(lines[i])
            i += 1

    return "\n".join(result)


def _format_for_whatsapp(text: str) -> str:
    """Convert standard Markdown from LLM into WhatsApp-native formatting.

    WhatsApp supports: *bold*, _italic_, ~strikethrough~, ```monospace```
    """
    if not text:
        return text

    # 0. Markdown tables -> key-value lists (must run first, line-based)
    text = _convert_markdown_table(text)

    # 1. Headers: ### Title or ### **Title** -> *Title*
    text = WHATSAPP_HEADERS_RE.sub(r"*\1*", text)

    # 2. Bold/Italic-Bold: ***text*** or **text** -> *text*
    text = WHATSAPP_BOLD_RE.sub(r"*\1*", text)

    # 3. Inline Code: `text` -> ```text```
    text = WHATSAPP_INLINE_CODE_RE.sub(r"```\2```", text)

    # 4. Image markdown: ![alt](url) -> alt
    text = WHATSAPP_IMG_RE.sub(r"\1", text)

    # 5. Links: [text](url) -> text: url
    text = WHATSAPP_LINK_RE.sub(r"\1: \2", text)

    # 6. B11: Horizontal rules --- -> empty line
    text = WHATSAPP_HR_RE.sub("", text)

    # 7. Collapse 3+ consecutive newlines into 2
    text = WHATSAPP_MULTI_NEWLINE_RE.sub("\n\n", text)

    # 8. Final cleanup: strip any remaining ** or *** (e.g. nested bold from LLM)
    text = text.replace("***", "").replace("**", "")

    return text


# Cooldown for re-notifying the manager (seconds)
_ESCALATION_RENOTIFY_COOLDOWN = 300  # 5 minutes


async def _handle_escalation_fallback(
    conv: Any,
    combined_text: str,
    wazzup: WazzupProvider,
    redis: Any,
    db: Any,
) -> None:
    """Send a contextual fallback to client + re-notify manager with cooldown.

    Called when a client message arrives while escalation is active.
    Instead of silently saving the message, we:
      1. Send a brief acknowledgement to the client (in their language).
      2. Save the fallback as an assistant message in DB.
      3. Re-notify the manager in Telegram (with 5-min cooldown to prevent spam).
    """
    lang = conv.language or "en"

    # 1. Client fallback — contextual ack
    if lang == "ar":
        fallback = (
            "شكراً لتواصلك! 🙏\n"
            "تم إبلاغ المدير بطلبك وسيتواصل معك قريباً.\n"
            "يرجى الانتظار قليلاً."
        )
    else:
        fallback = (
            "Thank you for your message! 🙏\n"
            "A manager has been notified and will get back to you shortly.\n"
            "Please bear with us."
        )

    await wazzup.send_text(chat_id=conv.phone, text=fallback)

    # Save fallback as assistant message
    fb_msg = Message(
        conversation_id=conv.id,
        role="assistant",
        content=fallback,
        model="fallback",
    )
    db.add(fb_msg)
    await db.commit()

    # 2. Re-notify manager (with cooldown)
    cooldown_key = f"escalation_renotify:{conv.id}"
    already_notified = await redis.get(cooldown_key)
    if not already_notified:
        await redis.setex(cooldown_key, _ESCALATION_RENOTIFY_COOLDOWN, "1")
        try:
            from src.integrations.notifications.telegram import TelegramClient

            client = TelegramClient(
                bot_token=settings.telegram_bot_token,
                chat_id=settings.telegram_chat_id,
            )
            phone_display = (
                conv.phone if conv.phone.startswith("+") else f"+{conv.phone}"
            )
            # R3-1: HTML-escape client text to prevent Telegram API 400 errors
            safe_text = (
                combined_text[:200]
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )
            await client.send_message(
                f"⚠️ <b>Клиент снова пишет</b> (эскалация активна)\n\n"
                f'📞 <a href="tel:{phone_display}">{phone_display}</a>\n'
                f"💬 <i>{safe_text}</i>"
            )
        except Exception:
            logger.exception("Failed to re-notify manager for %s", conv.phone)


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

    expected_channel = settings.wazzup_channel_id
    if not expected_channel:
        logger.error(
            "Skipping batch for %s because WAZZUP_CHANNEL_ID is not configured.",
            chat_id,
        )
        return

    filtered_messages = [m for m in messages if m.channelId == expected_channel]
    skipped_count = len(messages) - len(filtered_messages)
    if skipped_count:
        logger.warning(
            "Skipping %d message(s) for %s from unexpected or missing Wazzup channel IDs.",
            skipped_count,
            chat_id,
        )

    messages = filtered_messages
    if not messages:
        logger.warning(
            "No messages left for %s after Wazzup channel filtering, skipping batch.",
            chat_id,
        )
        return

    channel_id = expected_channel

    # Determine roles for each message
    has_manager_message = any(m.authorType == "manager" for m in messages)
    manager_name = next(
        (m.authorName for m in messages if m.authorType == "manager" and m.authorName),
        None,
    )
    combined_text = "\n".join(m.text for m in messages if m.text)

    # Check for audio/voice messages and transcribe them
    audio_results: dict[str, dict[str, str]] = {}
    audio_messages = [
        m
        for m in messages
        if m.type in ("audio", "voice") and (m.contentUri or (m.media and m.media.url))
    ]

    if audio_messages:
        from src.integrations.voice.voxtral import MAX_AUDIO_SIZE, transcribe_audio

        async def _process_single_audio(
            audio_msg: Any,
            wazzup_dl: WazzupProvider,
            shared_client: httpx.AsyncClient,
        ) -> tuple[str, str | None, str | None]:
            msg_id = audio_msg.messageId or ""
            audio_url = audio_msg.contentUri or (
                audio_msg.media.url if audio_msg.media else None
            )

            if not audio_url:
                return msg_id, None, None

            try:
                logger.info(
                    "Audio message detected for %s, downloading from %s",
                    chat_id,
                    audio_url,
                )

                audio_bytes = await wazzup_dl.download_media(
                    audio_url, max_retries=2, client=shared_client
                )

                if len(audio_bytes) > MAX_AUDIO_SIZE:
                    logger.warning(
                        "Audio too large for %s: %d bytes (max %d)",
                        chat_id,
                        len(audio_bytes),
                        MAX_AUDIO_SIZE,
                    )
                    return (
                        msg_id,
                        audio_url,
                        "[System: Unreadable voice message (file too large)]",
                    )

                mime = (
                    (audio_msg.media.mimeType if audio_msg.media else "")
                    .split(";")[0]
                    .strip()
                )
                format_map = {
                    "audio/ogg": "ogg",
                    "audio/mpeg": "mp3",
                    "audio/mp3": "mp3",
                    "audio/wav": "wav",
                    "audio/x-wav": "wav",
                    "audio/webm": "webm",
                }
                audio_format = format_map.get(mime, "mp3")

                t = await transcribe_audio(
                    audio_bytes, audio_format=audio_format, client=shared_client
                )
                if t:
                    logger.info("Transcription for %s: %s", chat_id, t[:200])
                    return msg_id, audio_url, t

                return msg_id, audio_url, None

            except Exception:
                logger.exception("Failed to process audio message for %s", chat_id)
                url = audio_msg.contentUri or (
                    audio_msg.media.url if audio_msg.media else None
                )
                return (
                    msg_id,
                    url,
                    "[System: Unreadable voice message (error during processing)]",
                )

        try:
            async with (
                WazzupProvider(channel_id=channel_id) as wazzup_dl,
                httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as shared_client,
            ):
                tasks = [
                    _process_single_audio(msg, wazzup_dl, shared_client)
                    for msg in audio_messages
                ]
                results = await asyncio.gather(*tasks)

            transcriptions: list[str] = []
            for msg_id, url, t in results:
                if msg_id:
                    audio_results[msg_id] = {"url": url or "", "transcription": t or ""}
                if t:
                    transcriptions.append(t)

            if transcriptions:
                transcription_text = "\n".join(transcriptions)
                combined_text = (
                    transcription_text
                    if not combined_text.strip()
                    else f"{combined_text}\n{transcription_text}"
                )

        except Exception:
            logger.exception(
                "Unexpected error in audio batch processing for %s", chat_id
            )

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

                audio_url = None
                transcription = None
                if is_audio and m.messageId in audio_results:
                    audio_url = audio_results[m.messageId].get("url")
                    transcription = audio_results[m.messageId].get("transcription")

                new_msg = Message(
                    conversation_id=conv.id,
                    role=role,
                    content=transcription
                    if is_audio and transcription
                    else (m.text or ""),
                    message_type=m.type,
                    wazzup_message_id=m.messageId,
                    audio_url=audio_url,
                    transcription=transcription,
                )
                db.add(new_msg)
                existing_ids.add(m.messageId)

        await db.commit()

        # 4. Escalation active: send fallback to client + re-notify manager
        # CR-3: Skip fallback during manual_takeover — manager is handling it
        if conv.escalation_status not in ("none", None, "manual_takeover"):
            logger.info(
                "Escalation active (%s) for %s. Sending fallback response.",
                conv.escalation_status,
                chat_id,
            )
            async with WazzupProvider(
                channel_id=channel_id,
            ) as wazzup_fallback:
                await _handle_escalation_fallback(
                    conv=conv,
                    combined_text=combined_text,
                    wazzup=wazzup_fallback,
                    redis=redis,
                    db=db,
                )
            return
        if conv.escalation_status == "manual_takeover":
            logger.info(
                "Manual takeover active for %s. Skipping LLM + fallback.",
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
                channel_id=channel_id,
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
                # R3-11: Send timeout fallback in client's language
                lang = conv.language or "en"
                timeout_msg = (
                    "عذراً، أنا مشغول حالياً. يرجى إعادة المحاولة بعد دقيقة."
                    if lang == "ar"
                    else "Sorry, I'm currently overloaded. Please try again in a minute."
                )
                await wazzup_provider.send_text(
                    chat_id=chat_id,
                    text=timeout_msg,
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
            whatsapp_text = _format_for_whatsapp(llm_response.text)
            await wazzup_provider.send_text(
                chat_id=chat_id,
                text=whatsapp_text,
            )
            logger.info("Reply sent to %s successfully", chat_id)
