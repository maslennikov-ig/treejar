import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.integrations.messaging.wazzup import WazzupProvider

async def main():
    print("--- Testing Wazzup API Connectivity (Channels) ---")
    async with WazzupProvider() as client:
        try:
            # The /channels endpoint returns all active channels connected to this Wazzup account
            response = await client._request("GET", "/channels")
            data = response.json()
            print("✅ Successfully connected to Wazzup API!")
            print(f"Channels found: {len(data)}")
            for ch in data:
                print(f" - {ch.get('channelId')}: {ch.get('state')} ({ch.get('transport')})")
        except Exception as e:
            print(f"❌ Failed to connect to Wazzup API: {e}")

if __name__ == "__main__":
    asyncio.run(main())
