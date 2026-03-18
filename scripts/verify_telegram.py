"""Script 8: Verify Telegram notification system.

Run inside Docker:
    docker compose -p treejar-prod exec app python scripts/verify_telegram.py

Set SEND_TEST=1 to actually send a test message to Telegram.
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings

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
    print("Script 8: Telegram Notifications Verification")
    print("=" * 60)

    # 1. Configuration
    print("\n--- 8.1 Configuration ---")
    bot_token = settings.telegram_bot_token if hasattr(settings, "telegram_bot_token") else ""
    chat_id = settings.telegram_chat_id if hasattr(settings, "telegram_chat_id") else ""

    if bot_token and len(bot_token) > 10:
        ok(f"Telegram bot token present ({len(bot_token)} chars)")
    else:
        fail("TELEGRAM_BOT_TOKEN missing or too short")

    if chat_id:
        ok(f"Telegram chat ID: {chat_id}")
    else:
        fail("TELEGRAM_CHAT_ID missing")

    # 2. Client import and init
    print("\n--- 8.2 Client initialization ---")
    try:
        from src.integrations.notifications.telegram import TelegramClient

        client = TelegramClient(bot_token=bot_token, chat_id=chat_id)
        if client.is_configured:
            ok("TelegramClient is configured")
        else:
            fail("TelegramClient.is_configured() returned False")
    except Exception as e:
        fail(f"TelegramClient init failed: {e}")
        client = None

    # 3. Message formatting
    print("\n--- 8.3 Message formatting ---")
    try:
        from uuid import uuid4

        from src.services.notifications import (
            format_escalation_message,
            format_quality_alert_message,
        )

        esc_msg = format_escalation_message("971501234567", uuid4(), "Customer unhappy")
        if esc_msg and len(esc_msg) > 20:
            ok(f"Escalation message formatted ({len(esc_msg)} chars)")
        else:
            fail("Escalation message format returned empty/short result")

        quality_msg = format_quality_alert_message(uuid4(), 25.0, "good", "Very poor greeting")
        if quality_msg and len(quality_msg) > 20:
            ok(f"Quality alert formatted ({len(quality_msg)} chars)")
        else:
            fail("Quality alert format returned empty/short result")

    except Exception as e:
        fail(f"Message formatting failed: {e}")

    # 4. Optionally send a real test message
    print("\n--- 8.4 Live message ---")
    if os.getenv("SEND_TEST") == "1" and client and client.is_configured():
        try:
            await client.send_message("🤖 TreeJar verification test — if you see this, notifications work!")
            ok("Test message sent to Telegram successfully")
        except Exception as e:
            fail(f"Send failed: {e}")
    else:
        ok("Skipping live send (set SEND_TEST=1 to test)")

    print("\n" + "=" * 60)
    print(f"RESULT: {passed} passed, {failed} failed")
    print("=" * 60)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    asyncio.run(main())
