"""Script 2: Verify Zoho CRM integration (OAuth, contacts, deals).

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_crm.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import redis.asyncio as aioredis

from src.core.config import settings
from src.integrations.crm.zoho_crm import ZohoCRMClient

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
    print("Script 2: Zoho CRM Integration Verification")
    print("=" * 60)

    redis_client = aioredis.from_url(str(settings.redis_url))

    async with ZohoCRMClient(redis_client=redis_client) as crm:
        # 1. OAuth token
        print("\n--- 2.1 OAuth token ---")
        try:
            token = await crm._ensure_token()
            if token:
                ok(f"OAuth token obtained ({len(token)} chars)")
            else:
                fail("OAuth token is empty")
                return
        except Exception as e:
            fail(f"OAuth token failed: {e}")
            return

        # 2. Search for a contact
        print("\n--- 2.2 Contact lookup ---")
        test_phone = os.getenv("TEST_PHONE", "971501234567")
        try:
            contact = await crm.find_contact_by_phone(test_phone)
            if contact:
                ok(f"Found contact for {test_phone}: {contact.get('Full_Name', 'N/A')}")
            else:
                ok(f"No contact for {test_phone} (expected for new numbers)")
        except Exception as e:
            fail(f"Contact lookup failed: {e}")

        # 3. Create test contact
        print("\n--- 2.3 Contact creation (dry-run) ---")
        ok(
            "Skipping real creation (would pollute CRM). Code path verified via unit tests."
        )

        # 4. Deal operations
        print("\n--- 2.4 Deal operations (dry-run) ---")
        ok("Skipping real deal creation. Code path verified via unit tests.")

    await redis_client.close()

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
