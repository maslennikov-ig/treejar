import asyncio
import os
import sys
import traceback

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.database import async_session_factory as async_session_maker
from src.rag.embeddings import EmbeddingEngine
from src.rag.pipeline import search_products
from src.schemas.product import ProductSearchQuery


async def main() -> None:
    print("--- Verifying RAG (Embedding & Qdrant) Integration ---")

    engine = EmbeddingEngine()

    query_text = "ищу удобное кресло недорого"
    print(f"\nSearching for query: '{query_text}'")

    query = ProductSearchQuery(query=query_text, limit=3)

    async with async_session_maker() as db:
        try:
            results = await search_products(
                db=db,
                query=query,
                embedding_engine=engine,
            )

            print(f"\n✅ Found {results.total_found} products.")
            for p in results.products:
                print(
                    f"- {p.name_en} (SKU: {p.sku}) | Price: {p.price} | Stock: {p.stock}"
                )

        except Exception as e:
            print(f"❌ Search failed: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
