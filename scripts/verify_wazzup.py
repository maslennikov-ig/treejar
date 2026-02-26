import asyncio
import os
import sys

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.messaging.wazzup import WazzupProvider


async def main():
    print("--- Verifying Wazzup Integration ---")
    test_phone = os.getenv("TEST_PHONE", "")
    if not test_phone:
        print("Please set TEST_PHONE env variable. Using a mock number for now.")
        test_phone = "1234567890"

    print(f"Attempting to send a text message to: {test_phone}")
    
    async with WazzupProvider() as client:
        try:
            message_id = await client.send_text(test_phone, "Hello! This is an integration verification test from Treejar API.")
            print(f"✅ Success! Message ID: {message_id}")
        except Exception as e:
            print(f"❌ Failed to send message: {e}")


if __name__ == "__main__":
    asyncio.run(main())
