"""Script 1: Verify database schema, tables, and data integrity.

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_db.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import inspect, text

from src.core.database import async_session_factory, engine

EXPECTED_TABLES = [
    "conversations",
    "messages",
    "products",
    "knowledge_base",
    "quality_reviews",
    "escalations",
    "feedbacks",
    "referrals",
    "manager_reviews",
    "metrics_snapshots",
    "system_configs",
    "system_prompts",
]

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
    print("Script 1: Database & Models Verification")
    print("=" * 60)

    # 1. Check connection
    print("\n--- 1.1 Database connection ---")
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT 1"))
            assert result.scalar() == 1
        ok("PostgreSQL connection OK")
    except Exception as e:
        fail(f"Cannot connect to DB: {e}")
        return

    # 2. Check tables exist
    print("\n--- 1.2 Table existence ---")
    async with engine.begin() as conn:
        # Use run_sync to call the sync inspector
        def get_table_names(sync_conn):  # type: ignore
            insp = inspect(sync_conn)
            return insp.get_table_names(schema="public")

        existing_tables = await conn.run_sync(get_table_names)

    for table in EXPECTED_TABLES:
        if table in existing_tables:
            ok(f"Table '{table}' exists")
        else:
            fail(f"Table '{table}' MISSING")

    # 3. Check Alembic is up-to-date
    print("\n--- 1.3 Alembic migration status ---")
    async with engine.begin() as conn:
        try:
            result = await conn.execute(
                text("SELECT version_num FROM alembic_version")
            )
            version = result.scalar()
            if version:
                ok(f"Alembic version: {version}")
            else:
                fail("No Alembic version found (empty alembic_version table)")
        except Exception:
            fail("alembic_version table does not exist — migrations never run?")

    # 4. Data sanity checks
    print("\n--- 1.4 Data integrity ---")
    async with async_session_factory() as db:
        # Products count
        result = await db.execute(text("SELECT COUNT(*) FROM products"))
        count = result.scalar()
        if count and count > 0:
            ok(f"Products table has {count} rows")
        else:
            fail("Products table is EMPTY (Zoho sync may not have run)")

        # Knowledge base count
        result = await db.execute(text("SELECT COUNT(*) FROM knowledge_base"))
        count = result.scalar()
        if count and count > 0:
            ok(f"Knowledge base has {count} entries")
        else:
            fail("Knowledge base is EMPTY (indexer may not have run)")

        # Knowledge base embeddings
        result = await db.execute(
            text("SELECT COUNT(*) FROM knowledge_base WHERE embedding IS NOT NULL")
        )
        embed_count = result.scalar()
        if embed_count and embed_count > 0:
            ok(f"Knowledge base: {embed_count} entries with embeddings")
        else:
            fail("Knowledge base has NO embeddings at all")

        # Conversations count
        result = await db.execute(text("SELECT COUNT(*) FROM conversations"))
        count = result.scalar()
        ok(f"Conversations: {count} total")

        # Messages count
        result = await db.execute(text("SELECT COUNT(*) FROM messages"))
        count = result.scalar()
        ok(f"Messages: {count} total")

    # Summary
    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
