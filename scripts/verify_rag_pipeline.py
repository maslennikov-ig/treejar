"""Script 5: Verify RAG pipeline — embeddings and product search.

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_rag_pipeline.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from src.core.config import settings
from src.core.database import async_session_factory
from src.rag.embeddings import EmbeddingEngine

passed = 0
failed = 0


def ok(msg: str) -> None:
    global passed
    passed += 1
    print(f"  ✅ {msg}")


def fail(msg: str) -> None:
    global failed
    failed += 1
    print(f"  ❌ {msg}")


async def main() -> None:
    print("=" * 60)
    print("Script 5: RAG Pipeline Verification")
    print("=" * 60)

    # 1. Embedding generation
    print("\n--- 5.1 Embedding engine ---")
    try:
        engine = EmbeddingEngine()
        vector = await engine.embed_async("ergonomic office chair for home work")
        dim = len(vector)
        expected_dim = settings.embedding_dimension
        if dim == expected_dim:
            ok(f"Embedding generated: {dim} dimensions (matches config)")
        else:
            fail(f"Embedding dimension {dim} != config {expected_dim}")
    except Exception as e:
        fail(f"Embedding engine failed: {e}")
        print(f"       Error: {e}")
        print("\n" + "=" * 60)
        print(f"RESULT: {passed} passed, {failed} failed")
        print("=" * 60)
        sys.exit(1)
        return

    # 2. Search products in DB
    print("\n--- 5.2 Product search via embeddings ---")
    async with async_session_factory() as db:
        try:
            # Check if there are products with embeddings
            result = await db.execute(
                text("SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL")
            )
            count = result.scalar()
            if count and count > 0:
                ok(f"{count} products have embeddings")
            else:
                fail("No products with embeddings — RAG search will return nothing")

            # Check knowledge base embeddings
            result = await db.execute(
                text("SELECT COUNT(*) FROM knowledge_base WHERE embedding IS NOT NULL")
            )
            kb_count = result.scalar()
            if kb_count and kb_count > 0:
                ok(f"{kb_count} knowledge base entries have embeddings")
            else:
                fail("No knowledge base entries with embeddings")

        except Exception as e:
            fail(f"DB query failed: {e}")

    # 3. Multi-language embedding check
    print("\n--- 5.3 Multi-language embeddings ---")
    try:
        vec_en = await engine.embed_async("office chair")
        vec_ar = await engine.embed_async("كرسي مكتب")
        if len(vec_en) == len(vec_ar) == expected_dim:
            ok(f"EN and AR embeddings both {expected_dim}-dim")
        else:
            fail(f"Dimension mismatch: EN={len(vec_en)}, AR={len(vec_ar)}")
    except Exception as e:
        fail(f"Multi-language embedding failed: {e}")

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
