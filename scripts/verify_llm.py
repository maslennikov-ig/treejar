import asyncio
import os
import sys
import traceback
import uuid
from contextlib import nullcontext

# Set dummy key for testing initialization without real API hits if none exists
if not os.environ.get("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-mock-key-for-local-testing"

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis.asyncio as aioredis

from src.core.config import settings
from src.core.database import async_session_factory as async_session_maker
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.llm.engine import process_message
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage


async def main():
    print("--- Verifying PydanticAI (LLM Engine) ---")

    engine = EmbeddingEngine()
    redis = aioredis.from_url(str(settings.redis_url))  # type: ignore
    inventory_client = ZohoInventoryClient(redis_client=redis)
    crm_client = ZohoCRMClient(redis_client=redis)

    test_phone = os.getenv("TEST_PHONE", "+971500000000")
    conversation_id = uuid.uuid4()

    # 1. We need to create a dummy conversation in DB first or mock it
    # We will try to create a real conversation in DB for full integration test
    async with async_session_maker() as db:
        try:
            # Create conversation record to satisfy the agent
            conv = Conversation(
                id=conversation_id,
                phone=test_phone,
                sales_stage=SalesStage.GREETING.value,
                language="ru",
            )
            db.add(conv)
            await db.commit()
            print(f"✅ Created test conversation: {conversation_id}")

            # Call the process_message workflow
            query = "Какие у вас есть компьютерные столы?"
            print(f"\nSending agent query: '{query}'")

            from unittest.mock import AsyncMock, patch

            # Call engine directly instead of the webhook route
            escalation_guard = (
                patch(
                    "src.integrations.notifications.escalation.notify_manager_escalation",
                    new=AsyncMock(),
                )
                if os.getenv("ALLOW_REAL_ESCALATIONS") != "1"
                else nullcontext()
            )
            with escalation_guard:
                response = await process_message(
                    conversation_id=conversation_id,
                    combined_text=query,
                    db=db,
                    redis=redis,
                    messaging_client=AsyncMock(),
                    embedding_engine=engine,
                    zoho_client=inventory_client,
                    crm_client=crm_client,
                )

            print(f"\n✅ Agent Response:\n{response.text}\n")
            print(f"Usage: IN={response.tokens_in} OUT={response.tokens_out}")

        except Exception as e:
            print(f"❌ LLM verification failed: {e}")
            traceback.print_exc()

        finally:
            # Cleanup test conversation
            try:
                await db.delete(conv)
                await db.commit()
                print(f"Cleaned up conversation {conversation_id}")
            except Exception:
                pass
            await redis.close()


if __name__ == "__main__":
    asyncio.run(main())
