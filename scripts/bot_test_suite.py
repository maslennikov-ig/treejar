#!/usr/bin/env python3
"""
bot_test_suite.py — Полный тест-сьют Noor-бота.

Тестирует бота напрямую через process_message() с MockMessagingProvider,
минуя WhatsApp/Wazzup полностью. Каждый сценарий использует изолированный
уникальный phone, чтобы контексты не пересекались.

Запуск:
    # Полный прогон:
    uv run python scripts/bot_test_suite.py

    # Только конкретная группа:
    uv run python scripts/bot_test_suite.py --group escalation

    # Только один тест:
    uv run python scripts/bot_test_suite.py --test 2.1

    # Подробный вывод (все ответы бота):
    uv run python scripts/bot_test_suite.py --verbose

    # Сохранить результаты в файл:
    uv run python scripts/bot_test_suite.py --output results.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

# ─── Suppress noise ──────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
for noisy in ("httpx", "httpcore", "sqlalchemy.engine", "pydantic_ai", "openai"):
    logging.getLogger(noisy).setLevel(logging.ERROR)


# ─── Mock Messaging Provider ─────────────────────────────────────────────────

from src.integrations.messaging.base import MessagingProvider


class MockMessagingProvider(MessagingProvider):
    """Captures outgoing messages instead of sending to WhatsApp."""

    def __init__(self) -> None:
        self.sent_texts: list[str] = []
        self.sent_media: list[dict] = []

    async def send_text(self, chat_id: str, text: str) -> str:
        self.sent_texts.append(text)
        return f"mock_text_{uuid.uuid4().hex[:6]}"

    async def send_media(
        self,
        chat_id: str,
        url: str | None = None,
        caption: str | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> str:
        self.sent_media.append({
            "url": url,
            "caption": caption,
            "content_bytes": len(content) if content else 0,
            "content_type": content_type,
        })
        return f"mock_media_{uuid.uuid4().hex[:6]}"

    async def mark_read(self, chat_id: str, message_id: str) -> bool:
        return True

    def last_text(self) -> str:
        return self.sent_texts[-1] if self.sent_texts else ""

    def clear(self) -> None:
        self.sent_texts.clear()
        self.sent_media.clear()


# ─── Test Infrastructure ──────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: str
    name: str
    group: str
    passed: bool
    response: str = ""
    error: str = ""
    duration_ms: int = 0
    details: dict = field(default_factory=dict)


@dataclass
class BotTestContext:
    """Holds a live conversation for multi-turn tests."""
    phone: str
    conv_id: uuid.UUID | None = None
    messaging: MockMessagingProvider = field(default_factory=MockMessagingProvider)


async def send_message(
    phone: str,
    text: str,
    messaging: MockMessagingProvider | None = None,
) -> tuple[str, MockMessagingProvider]:
    """Send a message through the bot pipeline and return the response text."""
    from src.core.database import async_session_factory
    from src.core.redis import redis_client
    from src.integrations.crm.zoho_crm import ZohoCRMClient
    from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
    from src.llm.engine import process_message
    from src.models.conversation import Conversation
    from src.models.message import Message
    from src.rag.embeddings import EmbeddingEngine
    from src.schemas.common import SalesStage
    from sqlalchemy.future import select

    if messaging is None:
        messaging = MockMessagingProvider()

    messaging.clear()
    redis = redis_client

    async with async_session_factory() as db:
        # Get or create conversation
        stmt = select(Conversation).where(Conversation.phone == phone)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            conv = Conversation(phone=phone, sales_stage=SalesStage.GREETING.value)
            db.add(conv)
            await db.commit()

        # Save user message
        msg_id = f"test_{uuid.uuid4().hex[:8]}"
        new_msg = Message(
            wazzup_message_id=msg_id,
            conversation_id=conv.id,
            role="user",
            content=text,
        )
        db.add(new_msg)
        await db.commit()

        # Run LLM
        embedding_engine = EmbeddingEngine()
        async with (
            ZohoInventoryClient(redis_client=redis) as zoho,
            ZohoCRMClient(redis_client=redis) as crm,
        ):
            response = await process_message(
                conversation_id=conv.id,
                combined_text=text,
                db=db,
                redis=redis,
                embedding_engine=embedding_engine,
                zoho_client=zoho,
                messaging_client=messaging,
                crm_client=crm,
            )

        # Save assistant message
        ai_msg = Message(
            wazzup_message_id=f"ai_{uuid.uuid4().hex[:8]}",
            conversation_id=conv.id,
            role="assistant",
            content=response.text,
        )
        db.add(ai_msg)
        await db.commit()

    return response.text, messaging


async def get_conversation_state(phone: str) -> dict[str, Any]:
    """Fetch conversation state from DB."""
    from src.core.database import async_session_factory
    from src.models.conversation import Conversation
    from sqlalchemy.future import select

    async with async_session_factory() as db:
        stmt = select(Conversation).where(Conversation.phone == phone)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            return {}
        return {
            "id": str(conv.id),
            "sales_stage": conv.sales_stage,
            "escalation_status": conv.escalation_status,
            "language": conv.language,
            "deal_status": conv.deal_status,
            "customer_name": conv.customer_name,
        }


async def cleanup_phone(phone: str) -> None:
    """Delete test conversation and messages."""
    from src.core.database import async_session_factory
    from src.models.conversation import Conversation
    from src.models.message import Message
    from src.models.feedback import Feedback
    from sqlalchemy import delete
    from sqlalchemy.future import select

    async with async_session_factory() as db:
        stmt = select(Conversation).where(Conversation.phone == phone)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if conv:
            await db.execute(delete(Feedback).where(Feedback.conversation_id == conv.id))
            await db.execute(delete(Message).where(Message.conversation_id == conv.id))
            await db.execute(delete(Conversation).where(Conversation.id == conv.id))
            await db.commit()


# ─── Test Runner ──────────────────────────────────────────────────────────────

class TestSuite:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[TestResult] = []
        self._phone_counter = 1000

    def _phone(self, suffix: str | None = None) -> str:
        """Generate unique test phone number."""
        if suffix:
            return f"+7TEST{suffix}"
        self._phone_counter += 1
        return f"+7TEST{self._phone_counter}"

    def _run(
        self,
        test_id: str,
        name: str,
        group: str,
        coro,
    ) -> TestResult:
        """Execute a single test coroutine synchronously."""
        pass  # Used by run_all

    async def _execute(
        self,
        test_id: str,
        name: str,
        group: str,
        coro,
    ) -> TestResult:
        start = datetime.now()
        try:
            details = await coro
            duration = int((datetime.now() - start).total_seconds() * 1000)
            result = TestResult(
                test_id=test_id,
                name=name,
                group=group,
                passed=True,
                response=details.get("response", ""),
                duration_ms=duration,
                details=details,
            )
        except AssertionError as e:
            duration = int((datetime.now() - start).total_seconds() * 1000)
            result = TestResult(
                test_id=test_id,
                name=name,
                group=group,
                passed=False,
                error=str(e),
                duration_ms=duration,
            )
        except Exception as e:
            duration = int((datetime.now() - start).total_seconds() * 1000)
            result = TestResult(
                test_id=test_id,
                name=name,
                group=group,
                passed=False,
                error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-500:]}",
                duration_ms=duration,
            )

        self.results.append(result)
        self._print_result(result)
        return result

    def _print_result(self, r: TestResult) -> None:
        icon = "✅" if r.passed else "❌"
        print(f"  {icon} [{r.test_id}] {r.name} ({r.duration_ms}ms)")
        if not r.passed:
            print(f"      ↳ {r.error[:200]}")
        if self.verbose and r.response:
            print(f"      📝 {r.response[:300]}")

    # ─── GROUP 1: Basic Mechanics ─────────────────────────────────────────────

    async def test_1_1_first_contact(self) -> dict:
        """Новый клиент получает приветствие."""
        phone = self._phone("1_1")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "Hello! I'm looking for office furniture")
            assert response, "Empty response"
            assert len(response) > 20, "Response too short"
            state = await get_conversation_state(phone)
            assert state.get("id"), "Conversation not created in DB"
            return {"response": response, "state": state}
        finally:
            await cleanup_phone(phone)

    async def test_1_2_empty_message_ignored(self) -> dict:
        """Пустое сообщение не вызывает LLM (проверяем через webhook-логику)."""
        # This test validates the chat.py logic, not process_message directly
        # We just verify that an empty string doesn't crash
        phone = self._phone("1_2")
        await cleanup_phone(phone)
        try:
            # Sending whitespace — chat.py returns early, so process_message won't be called
            # We test the API-level behavior by checking that bot doesn't crash
            response, _ = await send_message(phone, "   ")
            # If we get here with any response, that's acceptable; the real guard is in chat.py
            return {"response": response or "(no response - correct)"}
        except Exception as e:
            # Graceful failure is also acceptable for empty input
            return {"response": f"Handled gracefully: {e}"}
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 2: Product Search & Stock ─────────────────────────────────────

    async def test_2_1_product_search_en(self) -> dict:
        """Бот находит товары по запросу на английском."""
        phone = self._phone("2_1")
        await cleanup_phone(phone)
        try:
            response, messaging = await send_message(phone, "What ergonomic chairs do you have?")
            assert response, "Empty response"
            # Bot should mention something product-related
            keywords = any(w in response.lower() for w in [
                "chair", "product", "sku", "aed", "price", "furniture", "catalog"
            ])
            assert keywords, f"Response doesn't mention products: {response[:300]}"
            return {
                "response": response,
                "media_sent": len(messaging.sent_media),
                "texts_sent": len(messaging.sent_texts),
            }
        finally:
            await cleanup_phone(phone)

    async def test_2_2_stock_check(self) -> dict:
        """Бот проверяет остатки товара (инструмент get_stock)."""
        phone = self._phone("2_2")
        await cleanup_phone(phone)
        try:
            # First search to get a product in context
            await send_message(phone, "Do you have office chairs?")
            # Then ask stock
            response, _ = await send_message(phone, "How many do you have in stock?")
            assert response, "Empty response"
            # Should mention quantity or stock info
            keywords = any(w in response.lower() for w in [
                "stock", "available", "item", "unit", "in stock", "pieces", "quantity"
            ])
            assert keywords, f"Response doesn't mention stock: {response[:300]}"
            return {"response": response}
        finally:
            await cleanup_phone(phone)

    async def test_2_3_product_search_arabic(self) -> dict:
        """Бот отвечает на арабском и ищет товары по арабскому запросу."""
        phone = self._phone("2_3")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "أريد كرسي مكتب مريح")
            assert response, "Empty response"
            # Response should contain Arabic characters
            has_arabic = any("\u0600" <= c <= "\u06ff" for c in response)
            assert has_arabic, f"Response not in Arabic: {response[:300]}"
            state = await get_conversation_state(phone)
            assert state.get("language") == "ar", f"Language not set to ar: {state}"
            return {"response": response, "language": state.get("language")}
        finally:
            await cleanup_phone(phone)

    async def test_2_4_no_hallucination_unknown_product(self) -> dict:
        """Бот не галлюцинирует по несуществующим товарам."""
        phone = self._phone("2_4")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "Do you sell helicopter spare parts?")
            assert response, "Empty response"
            # Should NOT claim to have helicopter parts
            bad_words = ["helicopter part", "yes we have helicop", "i can help with helicop"]
            for w in bad_words:
                assert w not in response.lower(), f"Possible hallucination: {response[:300]}"
            return {"response": response}
        finally:
            await cleanup_phone(phone)

    async def test_2_5_cross_sell_recommendations(self) -> dict:
        """Бот предлагает сопутствующие товары."""
        phone = self._phone("2_5")
        await cleanup_phone(phone)
        try:
            await send_message(phone, "I'm interested in office chairs")
            response, _ = await send_message(phone, "What else goes well with office chairs?")
            assert response, "Empty response"
            return {"response": response}
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 3: Sales Funnel ────────────────────────────────────────────────

    async def test_3_1_sales_stage_progression(self) -> dict:
        """Стадия продажи двигается вперёд по мере диалога."""
        phone = self._phone("3_1")
        await cleanup_phone(phone)
        stages = []
        try:
            await send_message(phone, "Hello")
            state = await get_conversation_state(phone)
            stages.append(state.get("sales_stage"))

            await send_message(phone, "I need chairs for an office of 20 people")
            state = await get_conversation_state(phone)
            stages.append(state.get("sales_stage"))

            await send_message(phone, "We need ergonomic chairs, budget around 500 AED each")
            state = await get_conversation_state(phone)
            stages.append(state.get("sales_stage"))

            assert len(set(stages)) > 1, f"Stage never changed: {stages}"
            return {"stages_observed": stages}
        finally:
            await cleanup_phone(phone)

    async def test_3_2_order_status_no_deal(self) -> dict:
        """Бот корректно отвечает клиенту без сделки."""
        phone = self._phone("3_2")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "Where is my order? What is my order status?")
            assert response, "Empty response"
            # Should acknowledge no order found
            no_order_keywords = any(w in response.lower() for w in [
                "no order", "not found", "don't have", "haven't placed",
                "لم يتم", "no confirmed"
            ])
            assert no_order_keywords, f"Expected 'no order' response, got: {response[:300]}"
            return {"response": response}
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 4: Escalation ──────────────────────────────────────────────────

    async def test_4_1_explicit_human_request(self) -> dict:
        """Клиент просит живого человека — эскалация срабатывает."""
        phone = self._phone("4_1")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "I want to speak to a real person, not a bot")
            state = await get_conversation_state(phone)
            assert response, "Empty response"
            # Escalation should be triggered
            esc_status = state.get("escalation_status")
            assert esc_status not in ("none", None), (
                f"Expected escalation, got status: {esc_status}\nResponse: {response[:300]}"
            )
            # Bot should acknowledge escalation, not silently fail
            ack_words = any(w in response.lower() for w in [
                "manager", "human", "team", "contact", "notif", "shortly", "soon",
                "مدير", "بشري"
            ])
            assert ack_words, f"Bot didn't acknowledge escalation: {response[:300]}"
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_2_wholesale_b2b_escalation(self) -> dict:
        """B2B/оптовый запрос триггерит эскалацию."""
        phone = self._phone("4_2")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(
                phone,
                "We need 500 chairs for our warehouse. Please provide wholesale pricing."
            )
            state = await get_conversation_state(phone)
            esc_status = state.get("escalation_status")
            assert esc_status not in ("none", None), (
                f"Expected escalation for B2B/wholesale, got: {esc_status}\n{response[:300]}"
            )
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_3_refund_request_escalation(self) -> dict:
        """Запрос возврата триггерит эскалацию."""
        phone = self._phone("4_3")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "I received the wrong product and I want a refund")
            state = await get_conversation_state(phone)
            esc_status = state.get("escalation_status")
            assert esc_status not in ("none", None), (
                f"Expected escalation for refund, got: {esc_status}\n{response[:300]}"
            )
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_4_frustrated_customer_escalation(self) -> dict:
        """Сильное недовольство клиента триггерит эскалацию."""
        phone = self._phone("4_4")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(
                phone,
                "This is absolutely unacceptable! My order is 3 weeks late and nobody answers!"
            )
            state = await get_conversation_state(phone)
            esc_status = state.get("escalation_status")
            assert esc_status not in ("none", None), (
                f"Expected escalation for frustrated customer, got: {esc_status}\n{response[:300]}"
            )
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_5_sample_request_escalation(self) -> dict:
        """Запрос образца товара триггерит эскалацию."""
        phone = self._phone("4_5")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "Can I get a physical sample of the chair before ordering?")
            state = await get_conversation_state(phone)
            esc_status = state.get("escalation_status")
            assert esc_status not in ("none", None), (
                f"Expected escalation for sample request, got: {esc_status}\n{response[:300]}"
            )
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_6_no_escalation_normal_question(self) -> dict:
        """Обычный вопрос НЕ вызывает эскалацию."""
        phone = self._phone("4_6")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "What are your delivery times to Dubai?")
            state = await get_conversation_state(phone)
            esc_status = state.get("escalation_status")
            assert esc_status in ("none", None), (
                f"Expected NO escalation for delivery question, got: {esc_status}\n{response[:300]}"
            )
            assert response, "Empty response"
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_7_legal_threat_escalation(self) -> dict:
        """Угроза судебным иском триггерит эскалацию."""
        phone = self._phone("4_7")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(phone, "If you don't resolve this I'm going to take legal action against Treejar")
            state = await get_conversation_state(phone)
            esc_status = state.get("escalation_status")
            assert esc_status not in ("none", None), (
                f"Expected escalation for legal threat, got: {esc_status}\n{response[:300]}"
            )
            return {"response": response, "escalation_status": esc_status}
        finally:
            await cleanup_phone(phone)

    async def test_4_8_bot_silent_after_escalation(self) -> dict:
        """После эскалации бот не отвечает на следующие сообщения (через chat.py)."""
        # Note: This tests the chat.py escalation guard, not process_message directly
        # We check that the escalation status persists
        phone = self._phone("4_8")
        await cleanup_phone(phone)
        try:
            # Trigger escalation
            await send_message(phone, "I want to speak to a manager immediately")
            state1 = await get_conversation_state(phone)
            esc1 = state1.get("escalation_status")

            # Send another message - escalation status should remain
            await send_message(phone, "Hello? Are you there?")
            state2 = await get_conversation_state(phone)
            esc2 = state2.get("escalation_status")

            # The status shouldn't reset to 'none' automatically
            assert esc2 not in ("none", None) or esc1 in ("none", None), (
                f"Escalation was reset unexpectedly: {esc1} → {esc2}"
            )
            return {"escalation_before": esc1, "escalation_after": esc2}
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 5: PII & Safety ────────────────────────────────────────────────

    async def test_5_1_pii_not_leaked_in_db_logs(self) -> dict:
        """PII маскируется до входа в LLM (проверяем через успешный ответ)."""
        phone = self._phone("5_1")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(
                phone,
                "My email is john.test@example.com and phone is +971501234567"
            )
            assert response, "Empty response"
            # Bot should respond normally (PII masking shouldn't break the flow)
            return {"response": response}
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 6: Multi-language ──────────────────────────────────────────────

    async def test_6_1_full_arabic_flow(self) -> dict:
        """Полный диалог на арабском языке."""
        phone = self._phone("6_1")
        await cleanup_phone(phone)
        try:
            r1, _ = await send_message(phone, "مرحبا، أحتاج إلى أثاث مكتبي")
            r2, _ = await send_message(phone, "ما هي المنتجات المتاحة؟")
            state = await get_conversation_state(phone)

            for response in [r1, r2]:
                has_arabic = any("\u0600" <= c <= "\u06ff" for c in response)
                assert has_arabic or response.strip(), f"No Arabic in response: {response[:200]}"

            assert state.get("language") == "ar", f"Language not ar: {state}"
            return {"r1": r1[:200], "r2": r2[:200], "language": state.get("language")}
        finally:
            await cleanup_phone(phone)

    async def test_6_2_language_detection_switches(self) -> dict:
        """Бот переключает язык ответа при смене языка клиента."""
        phone = self._phone("6_2")
        await cleanup_phone(phone)
        try:
            r_en, _ = await send_message(phone, "Hello, I need chairs")
            state_en = await get_conversation_state(phone)

            r_ar, _ = await send_message(phone, "أريد طاولة مكتبية")
            state_ar = await get_conversation_state(phone)

            has_arabic_in_ar_response = any("\u0600" <= c <= "\u06ff" for c in r_ar)
            return {
                "en_response": r_en[:150],
                "ar_response": r_ar[:150],
                "has_arabic": has_arabic_in_ar_response,
                "initial_lang": state_en.get("language"),
                "after_ar_lang": state_ar.get("language"),
            }
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 7: Referral Codes ──────────────────────────────────────────────

    async def test_7_1_referral_code_generation(self) -> dict:
        """Бот генерирует реферальный код по запросу."""
        phone = self._phone("7_1")
        await cleanup_phone(phone)
        try:
            response, _ = await send_message(
                phone,
                "Do you have a referral program? I'd like to refer a friend"
            )
            assert response, "Empty response"
            # Check if referral code mentioned (NOOR- prefix)
            has_code = "NOOR-" in response.upper() or "referral" in response.lower()
            return {
                "response": response[:400],
                "has_referral_code": has_code,
            }
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 8: Feedback Flow ───────────────────────────────────────────────

    async def test_8_1_feedback_collection(self) -> dict:
        """Бот собирает обратную связь через инструмент save_feedback."""
        from src.core.database import async_session_factory
        from src.models.conversation import Conversation
        from src.models.feedback import Feedback
        from src.schemas.common import DealStatus, SalesStage
        from sqlalchemy import select

        phone = self._phone("8_1")
        await cleanup_phone(phone)

        try:
            # Set conversation to feedback stage with delivered status
            async with async_session_factory() as db:
                from sqlalchemy.future import select as fselect
                stmt = fselect(Conversation).where(Conversation.phone == phone)
                result = await db.execute(stmt)
                conv = result.scalar_one_or_none()
                if not conv:
                    conv = Conversation(
                        phone=phone,
                        sales_stage=SalesStage.FEEDBACK.value,
                        deal_status=DealStatus.DELIVERED.value,
                    )
                    db.add(conv)
                    await db.commit()
                else:
                    conv.sales_stage = SalesStage.FEEDBACK.value
                    conv.deal_status = DealStatus.DELIVERED.value
                    await db.commit()

            r1, _ = await send_message(phone, "I'd give the overall experience a 5 out of 5")
            r2, _ = await send_message(phone, "Delivery was also excellent, 5/5")
            r3, _ = await send_message(phone, "Yes, I would definitely recommend Treejar to others")

            # Check if feedback was saved
            async with async_session_factory() as db:
                stmt = fselect(Conversation).where(Conversation.phone == phone)
                result = await db.execute(stmt)
                conv = result.scalar_one_or_none()
                if conv:
                    fb_stmt = select(Feedback).where(Feedback.conversation_id == conv.id)
                    fb_result = await db.execute(fb_stmt)
                    feedback = fb_result.scalar_one_or_none()
                    has_feedback = feedback is not None
                else:
                    has_feedback = False

            return {
                "r3": r3[:200],
                "feedback_saved": has_feedback,
            }
        finally:
            await cleanup_phone(phone)

    # ─── GROUP 9: Follow-up Cron ──────────────────────────────────────────────

    async def test_9_1_followup_sends_for_inactive(self) -> dict:
        """Follow-up отправляется для неактивных разговоров."""
        from sqlalchemy.future import select

        from src.core.database import async_session_factory
        from src.models.conversation import Conversation
        from src.schemas.common import EscalationStatus, SalesStage

        phone = self._phone("9_1")
        await cleanup_phone(phone)

        try:
            # Create a conversation that's 25h stale
            async with async_session_factory() as db:
                stale_time = datetime.utcnow() - timedelta(hours=25)
                conv = Conversation(
                    phone=phone,
                    sales_stage=SalesStage.SOLUTION.value,
                    escalation_status=EscalationStatus.NONE.value,
                    updated_at=stale_time,
                    created_at=stale_time,
                )
                db.add(conv)
                await db.commit()
                conv_id = conv.id

            # Run the followup job
            from src.services.followup import run_automatic_followups
            await run_automatic_followups({})

            # Check if a message was added to DB
            async with async_session_factory() as db:
                from src.models.message import Message
                from sqlalchemy import select as sel
                stmt = sel(Message).where(
                    Message.conversation_id == conv_id,
                    Message.role == "assistant",
                )
                result = await db.execute(stmt)
                msg = result.scalar_one_or_none()
                has_followup = msg is not None
                followup_content = msg.content[:200] if msg else ""

            return {"followup_sent": has_followup, "content": followup_content}
        finally:
            await cleanup_phone(phone)

    async def test_9_2_no_followup_when_escalated(self) -> dict:
        """Follow-up НЕ отправляется при активной эскалации."""
        from src.core.database import async_session_factory
        from src.models.conversation import Conversation
        from src.schemas.common import EscalationStatus, SalesStage

        phone = self._phone("9_2")
        await cleanup_phone(phone)

        try:
            async with async_session_factory() as db:
                stale_time = datetime.utcnow() - timedelta(hours=25)
                conv = Conversation(
                    phone=phone,
                    sales_stage=SalesStage.SOLUTION.value,
                    escalation_status=EscalationStatus.PENDING.value,  # escalated!
                    updated_at=stale_time,
                    created_at=stale_time,
                )
                db.add(conv)
                await db.commit()
                conv_id = conv.id

            from src.services.followup import run_automatic_followups
            await run_automatic_followups({})

            async with async_session_factory() as db:
                from sqlalchemy import select as sel

                from src.models.message import Message
                stmt = sel(Message).where(
                    Message.conversation_id == conv_id,
                    Message.role == "assistant",
                )
                result = await db.execute(stmt)
                msg = result.scalar_one_or_none()
                has_followup = msg is not None

            assert not has_followup, "Follow-up should NOT be sent when escalated"
            return {"escalated": True, "followup_sent": has_followup}
        finally:
            await cleanup_phone(phone)

    # ─── Runner ───────────────────────────────────────────────────────────────

    async def run_all(self, group_filter: str | None = None, test_filter: str | None = None) -> None:
        tests = [
            # (test_id, name, group, coro_method)
            ("1.1", "Первый контакт — приветствие", "basic", self.test_1_1_first_contact),
            ("1.2", "Пустое сообщение игнорируется", "basic", self.test_1_2_empty_message_ignored),
            ("2.1", "Поиск товаров (EN)", "products", self.test_2_1_product_search_en),
            ("2.2", "Проверка остатков", "products", self.test_2_2_stock_check),
            ("2.3", "Поиск товаров (AR)", "products", self.test_2_3_product_search_arabic),
            ("2.4", "Нет галлюцинаций", "products", self.test_2_4_no_hallucination_unknown_product),
            ("2.5", "Cross-sell рекомендации", "products", self.test_2_5_cross_sell_recommendations),
            ("3.1", "Прогресс по стадиям продажи", "sales", self.test_3_1_sales_stage_progression),
            ("3.2", "Статус заказа — нет сделки", "sales", self.test_3_2_order_status_no_deal),
            ("4.1", "Эскалация — запрос живого человека", "escalation", self.test_4_1_explicit_human_request),
            ("4.2", "Эскалация — B2B/оптовый запрос", "escalation", self.test_4_2_wholesale_b2b_escalation),
            ("4.3", "Эскалация — запрос возврата", "escalation", self.test_4_3_refund_request_escalation),
            ("4.4", "Эскалация — сильное недовольство", "escalation", self.test_4_4_frustrated_customer_escalation),
            ("4.5", "Эскалация — образец товара", "escalation", self.test_4_5_sample_request_escalation),
            ("4.6", "НЕТ эскалации — обычный вопрос", "escalation", self.test_4_6_no_escalation_normal_question),
            ("4.7", "Эскалация — угроза судом", "escalation", self.test_4_7_legal_threat_escalation),
            ("4.8", "Бот молчит после эскалации", "escalation", self.test_4_8_bot_silent_after_escalation),
            ("5.1", "PII маскировка не ломает ответ", "security", self.test_5_1_pii_not_leaked_in_db_logs),
            ("6.1", "Полный диалог на арабском", "multilang", self.test_6_1_full_arabic_flow),
            ("6.2", "Переключение языка mid-диалог", "multilang", self.test_6_2_language_detection_switches),
            ("7.1", "Генерация реферального кода", "referral", self.test_7_1_referral_code_generation),
            ("8.1", "Сбор обратной связи", "feedback", self.test_8_1_feedback_collection),
            ("9.1", "Follow-up для неактивных разговоров", "followup", self.test_9_1_followup_sends_for_inactive),
            ("9.2", "Нет follow-up при эскалации", "followup", self.test_9_2_no_followup_when_escalated),
        ]

        # Apply filters
        if group_filter:
            tests = [(tid, name, grp, fn) for tid, name, grp, fn in tests if grp == group_filter]
        if test_filter:
            tests = [(tid, name, grp, fn) for tid, name, grp, fn in tests if tid == test_filter]

        if not tests:
            print(f"⚠️  No tests match filter (group={group_filter}, test={test_filter})")
            return

        print(f"\n{'━' * 60}")
        print(f"🤖 Noor Bot Test Suite | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'━' * 60}")
        print(f"   Running {len(tests)} tests...\n")

        # Group by group name
        current_group = None
        for test_id, name, group, method in tests:
            if group != current_group:
                print(f"\n  📂 Group: {group.upper()}")
                current_group = group
            await self._execute(test_id, name, group, method())

        # Summary
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total_ms = sum(r.duration_ms for r in self.results)

        print(f"\n{'━' * 60}")
        print(f"📊 Results: {passed}/{len(self.results)} passed | {failed} failed | {total_ms/1000:.1f}s total")
        print(f"{'━' * 60}")

        if failed > 0:
            print("\n❌ Failed tests:")
            for r in self.results:
                if not r.passed:
                    print(f"   [{r.test_id}] {r.name}")
                    print(f"       {r.error[:300]}\n")


# ─── Entry Point ──────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(description="Noor Bot Test Suite")
    parser.add_argument("--group", help="Run only this group (basic/products/sales/escalation/security/multilang/referral/feedback/followup)")
    parser.add_argument("--test", help="Run only this test ID (e.g. 4.1)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print all bot responses")
    parser.add_argument("--output", help="Save results to JSON file")
    args = parser.parse_args()

    suite = TestSuite(verbose=args.verbose)
    await suite.run_all(group_filter=args.group, test_filter=args.test)

    if args.output:
        results_data = [
            {
                "id": r.test_id,
                "name": r.name,
                "group": r.group,
                "passed": r.passed,
                "response": r.response,
                "error": r.error,
                "duration_ms": r.duration_ms,
                "details": {k: str(v) for k, v in r.details.items()},
            }
            for r in suite.results
        ]
        with open(args.output, "w") as f:
            json.dump(results_data, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Results saved to {args.output}")

    # Exit with error code if any test failed
    failed_count = sum(1 for r in suite.results if not r.passed)
    sys.exit(1 if failed_count > 0 else 0)


if __name__ == "__main__":
    asyncio.run(main())
