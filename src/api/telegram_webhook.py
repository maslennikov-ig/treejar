"""Telegram webhook handler for manager FAQ responses.

Processes callback_query events from Telegram inline keyboards
(triggered by escalation alerts). Handles two flows:
- faq_global: Adapt response + send to client + save to FAQ
- faq_private: Adapt response + send to client only

The full flow uses a two-step interaction:
1. Manager clicks a button → bot asks for the answer text.
2. Manager types the answer → bot adapts it, sends it, and optionally saves to FAQ.

NOTE: This requires setting up the Telegram webhook externally
(the runtime now syncs `setWebhook(secret_token=...)` on startup).
"""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import UTC, datetime
from html import escape
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from src.core.config import settings
from src.core.database import async_session_factory
from src.core.redis import redis_client
from src.integrations.notifications.telegram import TelegramClient
from src.integrations.notifications.telegram_webhook import (
    expected_telegram_webhook_secret,
)
from src.models.conversation import Conversation
from src.models.message import Message, message_created_at_now
from src.services.escalation_state import resolve_conversation_pending_escalations
from src.services.outbound_audit import (
    deterministic_crm_message_id,
    send_wazzup_media_with_audit,
    send_wazzup_text_with_audit,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["telegram"])

# Redis key prefix for pending manager responses; TTL = 5 minutes.
_PENDING_KEY_PREFIX = "tg_pending:"
_PENDING_TTL_SECONDS = 600
_ORDER_DECISION_SOURCE = "telegram_order_decision"


def _get_telegram_client() -> TelegramClient:
    return TelegramClient(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
    )


def _metadata_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _parse_quotation_meta(raw: bytes | str | None) -> dict[str, Any]:
    if raw is None:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _apply_order_decision_metadata(
    conversation: Conversation,
    *,
    is_confirm: bool,
    quote_number: str,
    sale_order_id: str,
    sale_order_number: str,
    decided_at: str,
) -> None:
    metadata = dict(conversation.metadata_ or {})
    status = "approved" if is_confirm else "rejected"
    is_active = is_confirm

    sale_order_id = sale_order_id or _metadata_text(metadata.get("zoho_sale_order_id"))
    sale_order_number = sale_order_number or _metadata_text(
        metadata.get("zoho_sale_order_number")
    )

    decision: dict[str, Any] = {
        "status": status,
        "active": is_active,
        "quote_number": quote_number,
        "decided_at": decided_at,
        "source": _ORDER_DECISION_SOURCE,
    }
    if sale_order_id:
        decision["zoho_sale_order_id"] = sale_order_id
        metadata["zoho_sale_order_id"] = sale_order_id
    if sale_order_number:
        decision["zoho_sale_order_number"] = sale_order_number
        metadata["zoho_sale_order_number"] = sale_order_number

    metadata["quotation_decision"] = decision
    metadata["quotation_decision_status"] = status
    metadata["quotation_decided_at"] = decided_at
    metadata["quotation_decision_source"] = _ORDER_DECISION_SOURCE
    metadata["quotation_quote_number"] = quote_number
    metadata["zoho_sale_order_active"] = is_active
    metadata["order_active"] = is_active
    conversation.metadata_ = metadata


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(None),
) -> dict[str, str]:
    """Handle incoming Telegram updates (callback queries and messages)."""
    # Validate webhook secret (prevents forged requests)
    expected = expected_telegram_webhook_secret()
    if x_telegram_bot_api_secret_token != expected:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    data: dict[str, Any] = await request.json()

    # Handle callback_query (button press from escalation alert)
    callback_query = data.get("callback_query")
    if callback_query:
        await _handle_callback_query(callback_query)
        return {"status": "ok"}

    # Handle text message (manager's reply after clicking a button)
    message = data.get("message")
    if message and message.get("text"):
        await _handle_manager_reply(message)
        return {"status": "ok"}

    return {"status": "ignored"}


async def _handle_callback_query(callback_query: dict[str, Any]) -> None:
    """Process inline keyboard button press."""
    client = _get_telegram_client()
    callback_id = callback_query["id"]
    callback_data = callback_query.get("data", "")
    chat_id = callback_query["message"]["chat"]["id"]
    message_id = callback_query["message"].get("message_id")

    # Parse callback_data: "faq_global:<conv_id>" or "faq_private:<conv_id>"
    if ":" not in callback_data:
        await client.answer_callback_query(callback_id, "❌ Invalid callback data")
        return

    mode, conv_id_str = callback_data.split(":", 1)

    if mode not in ("faq_global", "faq_private", "order_confirm", "order_reject"):
        await client.answer_callback_query(callback_id, "❌ Unknown action")
        return

    # Handle order confirmation/rejection immediately (no text input needed)
    if mode in ("order_confirm", "order_reject"):
        await _handle_order_decision(
            client,
            callback_id,
            chat_id,
            message_id,
            mode,
            conv_id_str,
        )
        return

    # Validate conversation UUID
    try:
        conv_uuid = uuid.UUID(conv_id_str)
    except ValueError:
        await client.answer_callback_query(callback_id, "❌ Invalid conversation ID")
        return

    # Find the last user question from the conversation
    question = await _get_last_user_question(conv_uuid)

    # Store the pending response context in Redis (survives restarts)
    pending_data = json.dumps(
        {
            "conversation_id": str(conv_uuid),
            "mode": mode,
            "question": question or "Question not found",
        }
    )
    await redis_client.setex(
        f"{_PENDING_KEY_PREFIX}{chat_id}", _PENDING_TTL_SECONDS, pending_data
    )

    mode_label = "📚 FAQ + клиент" if mode == "faq_global" else "👤 Только клиенту"
    await client.answer_callback_query(callback_id, f"✅ Режим: {mode_label}")
    await client.send_message(
        f"📝 <b>Введите ваш ответ</b> ({mode_label}):\n\n"
        f"<i>Вопрос клиента:</i> {question or 'не найден'}\n\n"
        "Напишите ваш ответ, и я отправлю его клиенту.",
        chat_id=str(chat_id),
    )


async def _handle_manager_reply(message: dict[str, Any]) -> None:
    """Process the manager's text reply after they clicked a button."""
    chat_id = message["chat"]["id"]
    draft = message["text"]

    # Retrieve and delete pending context from Redis
    redis_key = f"{_PENDING_KEY_PREFIX}{chat_id}"
    pending_raw = await redis_client.get(redis_key)
    if not pending_raw:
        # No pending context — this is not a reply to an escalation
        return
    await redis_client.delete(redis_key)

    pending = json.loads(pending_raw)
    question = pending["question"]
    mode = pending["mode"]
    conv_id = pending["conversation_id"]

    client = _get_telegram_client()

    try:
        phone, language = await _get_conversation_phone_and_lang(uuid.UUID(conv_id))

        faq_candidate = None
        if mode == "faq_global":
            from src.llm.response_adapter import (
                adapt_manager_response_with_faq_candidate,
            )

            combined = await adapt_manager_response_with_faq_candidate(
                question, draft, language
            )
            adapted = combined.customer_message
            faq_candidate = combined.kb_candidate
        else:
            from src.llm.response_adapter import adapt_manager_response

            adapted = await adapt_manager_response(question, draft, language)

        # 2. Send adapted response to the client via Wazzup
        if phone:
            from src.integrations.messaging.wazzup import WazzupProvider

            wazzup = WazzupProvider(channel_id=settings.wazzup_channel_id)
            try:
                async with async_session_factory() as resolve_db:
                    send_result = await send_wazzup_text_with_audit(
                        resolve_db,
                        provider=wazzup,
                        conversation_id=uuid.UUID(conv_id),
                        chat_id=phone,
                        text=adapted,
                        source="manager_reply",
                        crm_message_id=deterministic_crm_message_id(
                            "manager",
                            conv_id,
                            message.get("message_id") or chat_id,
                            "private",
                        ),
                    )
                    msg = Message(
                        conversation_id=uuid.UUID(conv_id),
                        role="assistant",
                        content=adapted,
                        model="manager_reply",
                        wazzup_message_id=send_result.provider_message_id,
                        created_at=message_created_at_now(),
                    )
                    resolve_db.add(msg)

                    try:
                        resolved_rows = await resolve_conversation_pending_escalations(
                            resolve_db, uuid.UUID(conv_id)
                        )
                    except Exception:
                        resolved_rows = 0
                        logger.exception(
                            "Failed to resolve escalation for %s",
                            conv_id,
                        )

                    await resolve_db.commit()
                    logger.info(
                        "Manager reply persisted for %s; pending_rows=%d",
                        conv_id,
                        resolved_rows,
                    )
            finally:
                await wazzup.close()

            # R3-2: HTML-escape adapted text before Telegram notification
            safe_adapted = escape(adapted)
            await client.send_message(
                f"✅ Ответ отправлен клиенту:\n\n{safe_adapted}",
                chat_id=str(chat_id),
            )
        else:
            await client.send_message(
                "⚠️ Не удалось найти номер телефона клиента. "
                f"Адаптированный ответ:\n\n{adapted}",
                chat_id=str(chat_id),
            )

        # 3. Prepare FAQ candidate if global mode. Saving requires admin confirmation.
        if mode == "faq_global":
            from src.rag.embeddings import EmbeddingEngine
            from src.services.auto_faq import review_auto_faq_candidate

            async with async_session_factory() as db:
                save_result = await review_auto_faq_candidate(
                    db=db,
                    candidate=faq_candidate,
                    embedding_engine=EmbeddingEngine(),
                    customer_message=adapted,
                    manager_draft=draft,
                )
            if save_result.status == "needs_confirmation" and save_result.candidate:
                candidate = save_result.candidate
                await client.send_message(
                    "📚 Кандидат для Базы Знаний подготовлен, но не сохранён. "
                    "Требуется подтверждение админа.\n\n"
                    f"<b>Q:</b> {escape(candidate.question)}\n"
                    f"<b>A:</b> {escape(candidate.answer)}",
                    chat_id=str(chat_id),
                )
            elif save_result.status == "duplicate":
                await client.send_message(
                    "ℹ️ Похожий ответ уже есть в Базе Знаний (дубликат).",
                    chat_id=str(chat_id),
                )
            elif save_result.status == "low_confidence":
                await client.send_message(
                    "⚠️ Ответ отправлен клиенту, но кандидат для Базы Знаний "
                    "отклонён: низкая уверенность.",
                    chat_id=str(chat_id),
                )
            elif save_result.status == "blocked_unsafe":
                await client.send_message(
                    "⚠️ Ответ отправлен клиенту, но кандидат для Базы Знаний "
                    "отклонён safety-проверкой.",
                    chat_id=str(chat_id),
                )
            elif save_result.status == "missing_candidate":
                await client.send_message(
                    "ℹ️ Ответ отправлен клиенту. Кандидат для Базы Знаний не создан.",
                    chat_id=str(chat_id),
                )
            else:
                logger.info(
                    "Downgrading faq_global save to private-only for %s: reasons=%s",
                    conv_id,
                    ",".join(save_result.guard_reasons),
                )
                await client.send_message(
                    "⚠️ Ответ отправлен клиенту, но не добавлен в Базу Знаний: "
                    "он выглядит как контекстный/private-only.",
                    chat_id=str(chat_id),
                )

    except Exception:
        logger.exception("Failed to process manager reply")
        await client.send_message(
            "❌ Ошибка при обработке ответа. Попробуйте ещё раз.",
            chat_id=str(chat_id),
        )


async def _get_last_user_question(conv_id: uuid.UUID) -> str | None:
    """Fetch the last user message from a conversation by UUID."""
    async with async_session_factory() as db:
        stmt = (
            select(Message.content)
            .where(
                Message.conversation_id == conv_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()


async def _get_conversation_phone_and_lang(
    conv_id: uuid.UUID,
) -> tuple[str | None, str]:
    """Fetch the phone number and detect current language for a conversation.

    B6 fix: Instead of relying solely on conversation.language (which may be stale
    if the client switched languages), we check the last 3 user messages to detect
    the actual language being used.
    """
    async with async_session_factory() as db:
        # Get conversation phone and stored language
        stmt = (
            select(Conversation.phone, Conversation.language)
            .where(Conversation.id == conv_id)
            .limit(1)
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            return None, "en"

        phone = row.phone
        stored_lang = row.language or "en"

        # B6: Check last 3 user messages for actual language
        msg_stmt = (
            select(Message.content)
            .where(Message.conversation_id == conv_id, Message.role == "user")
            .order_by(Message.created_at.desc())
            .limit(3)
        )
        msg_result = await db.execute(msg_stmt)
        user_messages = [r[0] for r in msg_result.fetchall() if r[0]]

        if user_messages:
            # Simple heuristic: if any recent message contains Arabic characters,
            # the client is writing in Arabic
            combined = " ".join(user_messages)
            if any("\u0600" <= c <= "\u06ff" for c in combined):
                return phone, "ar"

        return phone, stored_lang


async def _handle_order_decision(
    client: TelegramClient,
    callback_id: str,
    chat_id: int,
    message_id: int | None,
    mode: str,
    conv_id_str: str,
) -> None:
    """Handle order confirmation or rejection from manager.

    Unlike FAQ responses, order decisions don't require text input.
    The manager clicks a button and the resulting action is immediate.

    CR-1: Idempotency — checks escalation_status before processing.
    CR-2: Removes inline keyboard after processing.
    CR-5: Only resolves escalation after successful WhatsApp send.
    """
    try:
        conv_uuid = uuid.UUID(conv_id_str)
    except ValueError:
        await client.answer_callback_query(callback_id, "❌ Invalid conversation ID")
        return

    # CR-1: Idempotency check — prevent double-click
    async with async_session_factory() as db:
        stmt = select(Conversation).where(Conversation.id == conv_uuid)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            await client.answer_callback_query(callback_id, "❌ Разговор не найден")
            return
        if conv.escalation_status == "resolved":
            await client.answer_callback_query(callback_id, "⚠️ Уже обработано")
            return

    phone, language = await _get_conversation_phone_and_lang(conv_uuid)
    is_confirm = mode == "order_confirm"

    # 1. Ack the button press
    ack_text = "✅ Заказ подтверждён" if is_confirm else "❌ Заказ отклонён"
    await client.answer_callback_query(callback_id, ack_text)

    # CR-2: Remove inline keyboard to prevent re-clicks
    if message_id:
        await client.edit_message_reply_markup(chat_id, message_id)

    # 2. Send confirmation/rejection to client
    if phone:
        from src.integrations.messaging.wazzup import WazzupProvider

        pdf_key = f"quotation_pdf:{conv_id_str}"
        meta_key = f"quotation_meta:{conv_id_str}"
        meta_raw = await redis_client.get(meta_key)
        quote_meta = _parse_quotation_meta(meta_raw)
        if meta_raw and not quote_meta:
            logger.warning(
                "Failed to parse quotation meta for conv %s",
                conv_id_str,
            )
        quote_number = _metadata_text(quote_meta.get("quote_number")) or "DRAFT"
        sale_order_id = _metadata_text(
            quote_meta.get("salesorder_id") or quote_meta.get("zoho_sale_order_id")
        )
        sale_order_number = _metadata_text(
            quote_meta.get("salesorder_number")
            or quote_meta.get("zoho_sale_order_number")
        )
        text_message_id: str | None = None

        if is_confirm:
            # Retrieve PDF from Redis (stored by create_quotation tool)
            pdf_b64_raw = await redis_client.get(pdf_key)

            pdf_bytes: bytes | None = None

            if pdf_b64_raw:
                try:
                    pdf_bytes = base64.b64decode(pdf_b64_raw)
                except Exception:
                    logger.warning(
                        "Failed to decode PDF from Redis for conv %s",
                        conv_id_str,
                    )

            # Send PDF to client via Wazzup if available
            wazzup = WazzupProvider(channel_id=settings.wazzup_channel_id)
            try:
                if pdf_bytes:
                    try:
                        async with async_session_factory() as audit_db:
                            await send_wazzup_media_with_audit(
                                audit_db,
                                provider=wazzup,
                                conversation_id=conv_uuid,
                                chat_id=phone,
                                source="order_confirm_pdf",
                                crm_message_id=deterministic_crm_message_id(
                                    "order",
                                    conv_id_str,
                                    "confirm",
                                    "pdf",
                                    quote_number,
                                ),
                                caption_crm_message_id=deterministic_crm_message_id(
                                    "order",
                                    conv_id_str,
                                    "confirm",
                                    "caption",
                                    quote_number,
                                ),
                                content=pdf_bytes,
                                content_type="application/pdf",
                                caption=f"Your quotation: {quote_number}",
                                file_name=f"quotation_{quote_number}.pdf",
                            )
                            await audit_db.commit()
                    except Exception:
                        logger.exception(
                            "Failed to send PDF to client for conv %s",
                            conv_id_str,
                        )
                        await client.send_message(
                            "⚠️ Не удалось отправить PDF клиенту.",
                            chat_id=str(chat_id),
                        )
                else:
                    await client.send_message(
                        "⚠️ PDF не найден (срок хранения истёк). "
                        "Отправлено только текстовое подтверждение.",
                        chat_id=str(chat_id),
                    )

                # Send text confirmation
                client_msg = (
                    "تم تأكيد طلبك! ✅\nسيتواصل معك المدير قريباً لتأكيد التفاصيل والدفع. شكراً لاختيارك Treejar! 🌳"
                    if language == "ar"
                    else "Your order has been confirmed! ✅\nA manager will contact you shortly to finalize details and payment. Thank you for choosing Treejar! 🌳"
                )
                async with async_session_factory() as audit_db:
                    text_result = await send_wazzup_text_with_audit(
                        audit_db,
                        provider=wazzup,
                        conversation_id=conv_uuid,
                        chat_id=phone,
                        text=client_msg,
                        source="order_confirm_text",
                        crm_message_id=deterministic_crm_message_id(
                            "order",
                            conv_id_str,
                            "confirm",
                            "text",
                            quote_number,
                        ),
                    )
                    text_message_id = text_result.provider_message_id
                    await audit_db.commit()
            except Exception:
                logger.exception("Failed to send order decision to %s", phone)
                await client.send_message(
                    "❌ Не удалось отправить сообщение клиенту. Эскалация не закрыта.",
                    chat_id=str(chat_id),
                )
                return
            finally:
                await wazzup.close()

            # Clean up Redis PDF/meta keys
            try:
                await redis_client.delete(pdf_key, meta_key)
            except Exception:
                logger.warning(
                    "Failed to clean up quotation Redis keys for %s",
                    conv_id_str,
                )
        else:
            # Reject — no PDF sent, just text
            client_msg = (
                "شكراً لاهتمامك! 🙏\nللأسف، لم نتمكن من تأكيد هذا الطلب حالياً. سيتواصل معك أحد المديرين لمناقشة البدائل المتاحة."
                if language == "ar"
                else "Thank you for your interest! 🙏\nUnfortunately, we couldn't confirm this order at the moment. A manager will reach out to discuss available options."
            )

            # CR-5: Send to client FIRST, only resolve if successful
            wazzup = WazzupProvider(channel_id=settings.wazzup_channel_id)
            try:
                async with async_session_factory() as audit_db:
                    text_result = await send_wazzup_text_with_audit(
                        audit_db,
                        provider=wazzup,
                        conversation_id=conv_uuid,
                        chat_id=phone,
                        text=client_msg,
                        source="order_reject_text",
                        crm_message_id=deterministic_crm_message_id(
                            "order",
                            conv_id_str,
                            "reject",
                            "text",
                            quote_number,
                        ),
                    )
                    text_message_id = text_result.provider_message_id
                    await audit_db.commit()
            except Exception:
                logger.exception("Failed to send order decision to %s", phone)
                await client.send_message(
                    "❌ Не удалось отправить сообщение клиенту. Эскалация не закрыта.",
                    chat_id=str(chat_id),
                )
                return
            finally:
                await wazzup.close()

            # Clean up Redis PDF/meta keys (if any)
            try:
                await redis_client.delete(pdf_key, meta_key)
            except Exception:
                logger.warning(
                    "Failed to clean up quotation Redis keys for %s",
                    conv_id_str,
                )

        # Save message and resolve escalation AFTER successful send
        async with async_session_factory() as db:
            stmt = select(Conversation).where(Conversation.id == conv_uuid)
            result = await db.execute(stmt)
            decision_conv = result.scalar_one_or_none()
            if decision_conv:
                _apply_order_decision_metadata(
                    decision_conv,
                    is_confirm=is_confirm,
                    quote_number=quote_number,
                    sale_order_id=sale_order_id,
                    sale_order_number=sale_order_number,
                    decided_at=datetime.now(UTC).isoformat(),
                )
            else:
                logger.warning(
                    "Conversation %s disappeared before order decision metadata write",
                    conv_id_str,
                )

            msg = Message(
                conversation_id=conv_uuid,
                role="assistant",
                content=client_msg,
                model="manager_decision",
                wazzup_message_id=text_message_id,
                created_at=message_created_at_now(),
            )
            db.add(msg)

            resolved_rows = await resolve_conversation_pending_escalations(
                db, conv_uuid
            )
            await db.commit()

        action_label = "подтверждён ✅" if is_confirm else "отклонён ❌"
        await client.send_message(
            f"📦 Заказ {action_label}. Ответ отправлен клиенту.",
            chat_id=str(chat_id),
        )
        logger.info(
            "Order decision resolved escalation for %s; pending_rows=%d",
            conv_id_str,
            resolved_rows,
        )
    else:
        await client.send_message(
            "⚠️ Не удалось найти номер телефона клиента.",
            chat_id=str(chat_id),
        )
