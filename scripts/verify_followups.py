"""Script 9: Verify follow-up and feedback collection logic.

Run inside Docker:
    cd /opt/noor && docker compose exec app python scripts/verify_followups.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from src.core.database import async_session_factory

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
    print("Script 9: Follow-ups & Feedback Verification")
    print("=" * 60)

    # 1. Module imports
    print("\n--- 9.1 Module imports ---")
    try:
        from src.services.followup import (  # noqa: F401
            run_automatic_followups,
            run_feedback_requests,
        )

        ok("Follow-up modules imported OK")
    except ImportError as e:
        fail(f"Import error: {e}")

    # 2. Feedback model
    print("\n--- 9.2 Feedback model ---")
    try:
        from src.models.feedback import Feedback  # noqa: F401

        ok("Feedback model imported OK")
    except ImportError as e:
        fail(f"Feedback model import error: {e}")

    # 3. LLM tool: save_feedback
    print("\n--- 9.3 LLM feedback tool ---")
    try:
        from src.llm.engine import save_feedback  # noqa: F401

        ok("save_feedback LLM tool imported OK")
    except ImportError as e:
        fail(f"save_feedback import error: {e}")

    # 4. DB data check
    print("\n--- 9.4 Database state ---")
    async with async_session_factory() as db:
        # Feedback entries
        result = await db.execute(text("SELECT COUNT(*) FROM feedbacks"))
        count = result.scalar()
        ok(f"Feedback entries in DB: {count}")

        # Conversations eligible for follow-up (stale active ones)
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM conversations "
                "WHERE status = 'active' "
                "AND updated_at < NOW() - INTERVAL '24 hours'"
            )
        )
        stale = result.scalar()
        ok(f"Conversations eligible for follow-up (stale > 24h): {stale}")

        # Conversations eligible for feedback (completed without feedback)
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM conversations c "
                "WHERE c.status IN ('completed', 'closed') "
                "AND NOT EXISTS (SELECT 1 FROM feedbacks f WHERE f.conversation_id = c.id)"
            )
        )
        needs_feedback = result.scalar()
        ok(f"Completed conversations without feedback: {needs_feedback}")

    # 5. Worker cron registration
    print("\n--- 9.5 Worker cron ---")
    try:
        import importlib

        worker = importlib.import_module("src.worker")
        with open(worker.__file__) as f:  # type: ignore
            source = f.read()
        if "run_automatic_followups" in source:
            ok("run_automatic_followups registered in worker.py")
        else:
            fail("run_automatic_followups NOT found in worker.py")

        if "run_feedback_requests" in source:
            ok("run_feedback_requests registered in worker.py")
        else:
            fail("run_feedback_requests NOT found in worker.py")
    except Exception as e:
        fail(f"Worker check failed: {e}")

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
