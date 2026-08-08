import asyncio

import httpx

TOKEN = "8651031074:AAG5OJ5KHUOiXZz0v8s6hGXEK5HiuNfg02o"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"


async def setup_bot():
    print("Starting bot configuration...")
    async with httpx.AsyncClient() as client:
        # 1. Set Name
        r = await client.post(
            f"{BASE_URL}/setMyName", json={"name": "TreeJar Manager Assistant 🌳"}
        )
        print("Name:", r.json())

        # 2. Set Short Description (shown when opening the profile)
        r = await client.post(
            f"{BASE_URL}/setMyShortDescription",
            json={
                "short_description": "🤖 A smart assistant for TreeJar managers.\n\nForwards escalations, new leads and WhatsApp notifications instantly."
            },
        )
        print("Short Description:", r.json())

        # 3. Set Description (shown in the empty chat before pressing Start)
        r = await client.post(
            f"{BASE_URL}/setMyDescription",
            json={
                "description": "Hello! I am TreeJar's internal coordinator bot. 🌳\n\nMy job is to help the sales team work more effectively. I will post here:\n🔥 Hot leads that need attention\n📞 Requests to speak to a human manager\n📊 Service quality alerts\n\nJust add me to the managers' working group!"
            },
        )
        print("Description:", r.json())

        # 4. Set Commands Menu
        r = await client.post(
            f"{BASE_URL}/setMyCommands",
            json={
                "commands": [
                    {"command": "status", "description": "Check operational status"},
                    {"command": "help", "description": "Notification help"},
                ]
            },
        )
        print("Commands:", r.json())


if __name__ == "__main__":
    asyncio.run(setup_bot())
