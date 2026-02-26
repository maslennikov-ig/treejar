import asyncio
import os
import sys
import traceback

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.rag.embeddings import EmbeddingEngine
from src.core.config import settings
from src.core.database import async_session_factory as async_session_maker
from src.rag.pipeline import search_products
from src.schemas.product import ProductSearchQuery

async def main():
    print("--- Verifying RAG (Embedding & Qdrant) Integration ---")
    
    # Initialize Embedding Engine
    # Force a supported model for testing if the one in settings is not available
    import fastembed
    supported = [m["model"] for m in fastembed.TextEmbedding.list_supported_models()]
    if settings.embedding_model not in supported:
        print(f"Model {settings.embedding_model} not supported, falling back to 'BAAI/bge-large-en-v1.5'")
        settings.embedding_model = "BAAI/bge-large-en-v1.5"
        
    engine = EmbeddingEngine()
    
    query_text = "ищу удобное кресло недорого"
    print(f"\nSearching for query: '{query_text}'")
    
    query = ProductSearchQuery(query=query_text, limit=3)

    async with async_session_maker() as db:
        try:
             results = await search_products(
                 db=db,
                 query=query,
                 embedding_engine=engine
             )
             
             print(f"\n✅ Found {results.total_found} products.")
             for p in results.products:
                  print(f"- {p.name_en} (SKU: {p.sku}) | Price: {p.price} | Stock: {p.stock}")

        except Exception as e:
             print(f"❌ Search failed: {e}")
             traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
