import asyncio
import logging
import sys
import uuid

from escalation_guard import maybe_suppress_external_escalation_alerts

from src.core.database import async_session_factory
from src.core.redis import redis_client
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.engine import process_message
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage

# Configure simple logging for REPL
logging.basicConfig(level=logging.WARNING, format="%(message)s")
logger = logging.getLogger(__name__)

# Suppress some noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class REPLMessagingProvider(MessagingProvider):
    """Mock messaging provider that prints to the terminal instead of sending via Wazzup."""

    async def send_text(self, chat_id: str, text: str) -> str:
        print(f"\n[BOT (Text)]: {text}\n")
        return "mock_msg_id"

    async def send_media(
        self,
        chat_id: str,
        url: str | None = None,
        caption: str | None = None,
        content: bytes | None = None,
        content_type: str | None = None,
    ) -> str:
        print("\n[BOT (Media)]: 📎 Media message sent!")
        print(f"  Caption: {caption}")
        if url:
            print(f"  URL: {url}")
        if content:
            print(f"  Content Bytes: {len(content)} bytes of type {content_type}")
        print()
        return "mock_media_msg_id"

    async def mark_read(self, chat_id: str, message_id: str) -> bool:
        return True


async def main() -> None:
    print("=" * 60)
    print("🤖 Treejar AI Sales Bot - REPL Simulation")
    print("=" * 60)
    print("Type your messages to simulate a WhatsApp conversation.")
    print("Available commands:")
    print("  /quit  - Exit the REPL")
    print("  /stage - Show current SalesStage of the conversation")
    print("  /reset - Reset the conversation stage to GREETING and start over")
    print("-" * 60 + "\n")

    # Generate a deterministic but random-looking phone number for the session
    # or use a fixed one to test CRM loading.
    session_phone = "971500000001"

    redis = redis_client

    # Init external dependencies
    embedding_engine = EmbeddingEngine()
    zoho_inventory = ZohoInventoryClient(redis)
    zoho_crm = ZohoCRMClient(redis)
    messaging_client = REPLMessagingProvider()

    async with async_session_factory() as db:
        # Setup or fetch conversation
        from sqlalchemy.future import select

        stmt = select(Conversation).where(Conversation.phone == session_phone)
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()

        if not conv:
            conv = Conversation(
                phone=session_phone, sales_stage=SalesStage.GREETING.value
            )
            db.add(conv)
            await db.commit()
            print(f"[SYSTEM] Created new Conversation with mock phone: {session_phone}")
        else:
            print(
                f"[SYSTEM] Loaded existing Conversation for mock phone: {session_phone}"
            )
            print(f"[SYSTEM] Current Database Stage: {conv.sales_stage}")

        while True:
            try:
                user_input = input("You: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting REPL.")
                break

            if not user_input:
                continue

            if user_input.lower() == "/quit":
                print("Goodbye!")
                break

            if user_input.lower() == "/stage":
                await db.refresh(conv)
                print(f"[SYSTEM] Current Stage: {conv.sales_stage}")
                continue

            if user_input.lower() == "/reset":
                conv.sales_stage = SalesStage.GREETING.value
                db.add(conv)
                await db.commit()
                # Optionally clear redis history if applying
                await redis.delete(f"msgs:{conv.id}")
                # Also delete DB messages to truly reset context
                from sqlalchemy import delete

                from src.models.message import Message

                await db.execute(
                    delete(Message).where(Message.conversation_id == conv.id)
                )
                await db.commit()
                print(
                    "[SYSTEM] Conversation stage reset to GREETING and history cleared."
                )
                continue

            print("[SYSTEM] Thinking...")

            # Mocking incoming WazzupMessage mapping
            msg_id = f"cli_{uuid.uuid4().hex[:8]}"

            # We need to save the user message to DB to simulate webhook behavior.
            # Actually, `process_message` assumes the user message is handled OUTSIDE it
            # OR is passed in `combined_text` and the system relies on `build_message_history`.
            # Let's look at `process_message()`: it gets `combined_text`, builds history, and runs LLM.
            # Does it save the messages? No, `process_message` just generates the response.
            # The chat service `process_incoming_batch` usually handles saving.

            from src.models.message import Message

            new_msg = Message(
                wazzup_message_id=msg_id,
                conversation_id=conv.id,
                role="user",
                content=user_input,
            )
            db.add(new_msg)
            await db.commit()

            # Let process_message do the heavy lifting
            try:
                import time

                start_time = time.time()

                with maybe_suppress_external_escalation_alerts():
                    response = await process_message(
                        conversation_id=conv.id,
                        combined_text=user_input,
                        db=db,
                        redis=redis,
                        embedding_engine=embedding_engine,
                        zoho_client=zoho_inventory,
                        messaging_client=messaging_client,
                        crm_client=zoho_crm,
                    )

                elapsed = time.time() - start_time

                # Save AI response to DB
                ai_msg = Message(
                    wazzup_message_id=f"ai_{uuid.uuid4().hex[:8]}",
                    conversation_id=conv.id,
                    role="assistant",
                    content=response.text,
                )
                db.add(ai_msg)
                # We also commit the conversation changes (e.g. stage advance)
                await db.commit()

                # Print response details
                print("-" * 40)
                print(
                    f"🤖 Bot ({elapsed:.2f}s | model: {response.model} | {response.tokens_in} in / {response.tokens_out} out tokens):"
                )
                print(response.text)
                print("-" * 40)
                print()

            except Exception as e:
                logger.exception("Error processing message")
                print(f"❌ Error processing message: {e}")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
