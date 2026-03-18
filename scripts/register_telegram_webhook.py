#!/usr/bin/env python3
"""One-shot script to register the Telegram webhook with the correct secret_token.

Run inside the app Docker container:
  docker exec -it treejar-app-1 python scripts/register_telegram_webhook.py

This script is temporary — delete after successful registration.
"""

import asyncio
import hashlib
import hmac
import os
import sys

import httpx


def compute_webhook_secret(app_secret_key: str, bot_token: str) -> str:
    """Derive the webhook secret token — must match _expected_webhook_secret() in telegram_webhook.py."""
    return hmac.new(
        app_secret_key.encode(),
        bot_token.encode(),
        hashlib.sha256,
    ).hexdigest()[:32]


async def register_webhook() -> None:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    app_secret_key = os.environ.get("APP_SECRET_KEY", "")
    domain = os.environ.get("DOMAIN", "noor.starec.ai")

    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    if not app_secret_key or app_secret_key == "change-me-in-production":
        print("❌ APP_SECRET_KEY not set or is default", file=sys.stderr)
        sys.exit(1)

    webhook_url = f"https://{domain}/api/v1/webhook/telegram"
    secret_token = compute_webhook_secret(app_secret_key, bot_token)

    print(f"🌐 Webhook URL: {webhook_url}")
    print(f"🔑 Secret token (first 6 chars): {secret_token[:6]}...")

    base_url = f"https://api.telegram.org/bot{bot_token}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        # 1. Register webhook
        resp = await client.post(
            f"{base_url}/setWebhook",
            json={
                "url": webhook_url,
                "secret_token": secret_token,
                "allowed_updates": ["callback_query", "message"],
                "drop_pending_updates": True,
            },
        )
        data = resp.json()
        if data.get("ok"):
            print("✅ Webhook registered successfully!")
            print(f"   Description: {data.get('description', '')}")
        else:
            print(f"❌ Failed to register webhook: {data}")
            sys.exit(1)

        # 2. Verify webhook info
        resp2 = await client.get(f"{base_url}/getWebhookInfo")
        info = resp2.json().get("result", {})
        print("\n📋 Webhook info:")
        print(f"   URL: {info.get('url', 'N/A')}")
        print(f"   Has custom certificate: {info.get('has_custom_certificate', False)}")
        print(f"   Pending updates: {info.get('pending_update_count', 0)}")
        print(f"   Last error: {info.get('last_error_message', 'none')}")
        print(f"   Max connections: {info.get('max_connections', 40)}")


if __name__ == "__main__":
    asyncio.run(register_webhook())
