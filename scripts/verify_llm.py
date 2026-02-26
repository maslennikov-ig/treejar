import asyncio
import os
import sys
import uuid
import traceback

# Set dummy key for testing initialization without real API hits if none exists
if not os.environ.get("OPENROUTER_API_KEY"):
    os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-mock-key-for-local-testing"

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm.engine import process_message, sales_agent, SalesDeps
from src.models.conversation import Conversation
from src.core.config import settings
from src.core.database import async_session_factory as async_session_maker
from src.rag.embeddings import EmbeddingEngine
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.schemas.common import SalesStage
import redis.asyncio as aioredis


async def main():
    print("--- Verifying PydanticAI (LLM Engine) ---")
    
    # Needs to connect to real services: DB, Redis, APIs
    import fastembed
    supported = [m["model"] for m in fastembed.TextEmbedding.list_supported_models()]
    if settings.embedding_model not in supported:
        print(f"Model {settings.embedding_model} not supported, falling back to 'BAAI/bge-large-en-v1.5'")
        settings.embedding_model = "BAAI/bge-large-en-v1.5"
        
    engine = EmbeddingEngine()
    redis = aioredis.from_url(settings.redis_url)
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
                 language="ru"
             )
             db.add(conv)
             await db.commit()
             print(f"✅ Created test conversation: {conversation_id}")
             
             # Call the process_message workflow
             query = "Какие у вас есть компьютерные столы?"
             print(f"\nSending agent query: '{query}'")
             
             # Call engine directly instead of the webhook route
             response = await process_message(
                 conversation_id=conversation_id,
                 combined_text=query,
                 db=db,
                 redis=redis,
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
