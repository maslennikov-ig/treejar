"""Script 7: Verify quality evaluator (LLM-as-a-judge).

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_quality.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text

from src.core.database import async_session_factory
from src.models.conversation import Conversation

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
    print("Script 7: Quality Evaluator Verification")
    print("=" * 60)

    # 1. Module imports
    print("\n--- 7.1 Module imports ---")
    try:
        from src.quality.evaluator import evaluate_conversation  # noqa: F401
        from src.quality.job import evaluate_completed_conversations  # noqa: F401
        from src.quality.schemas import EvaluationResult  # noqa: F401
        from src.quality.service import get_reviews, save_review  # noqa: F401

        ok("All quality modules imported OK")
    except ImportError as e:
        fail(f"Import error: {e}")
        return

    # 2. Check existing reviews in DB
    print("\n--- 7.2 Existing quality reviews ---")
    async with async_session_factory() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM quality_reviews"))
        count = result.scalar()
        ok(f"Quality reviews in DB: {count}")

        # Check for reviewable conversations
        result = await db.execute(
            text(
                "SELECT COUNT(*) FROM conversations "
                "WHERE status IN ('completed', 'closed')"
            )
        )
        reviewable = result.scalar()
        ok(f"Conversations eligible for review: {reviewable}")

    # 3. Manager evaluator
    print("\n--- 7.3 Manager evaluator ---")
    try:
        from src.quality.manager_evaluator import evaluate_manager_conversation  # noqa: F401
        from src.quality.manager_job import evaluate_escalated_conversations  # noqa: F401

        ok("Manager evaluator modules imported OK")
    except ImportError as e:
        fail(f"Manager evaluator import error: {e}")

    async with async_session_factory() as db:
        result = await db.execute(text("SELECT COUNT(*) FROM manager_reviews"))
        count = result.scalar()
        ok(f"Manager reviews in DB: {count}")

    # 4. API endpoint check
    print("\n--- 7.4 API endpoints ---")
    try:
        from src.api.v1.quality import router as quality_router  # noqa: F401
        from src.api.v1.manager_reviews import router as manager_router  # noqa: F401

        ok("Quality API routers imported OK")
    except ImportError as e:
        fail(f"API router import error: {e}")

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
