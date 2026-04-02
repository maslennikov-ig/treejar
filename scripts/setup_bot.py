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
                "short_description": "🤖 Умный ассистент для менеджеров TreeJar.\n\nМгновенно пересылает эскалации, новые лиды и уведомления из WhatsApp."
            },
        )
        print("Short Description:", r.json())

        # 3. Set Description (shown in the empty chat before pressing Start)
        r = await client.post(
            f"{BASE_URL}/setMyDescription",
            json={
                "description": "Привет! Я внутренний бот-координатор TreeJar. 🌳\n\nМоя задача — помогать команде продаж работать эффективнее. Я буду присылать сюда:\n🔥 Горячие лиды, требующие внимания\n📞 Запросы на связь с 'живым' менеджером\n📊 Оповещения о качестве обслуживания\n\nПросто добавьте меня в рабочую группу менеджеров!"
            },
        )
        print("Description:", r.json())

        # 4. Set Commands Menu
        r = await client.post(
            f"{BASE_URL}/setMyCommands",
            json={
                "commands": [
                    {"command": "status", "description": "Проверить статус работы"},
                    {"command": "help", "description": "Справка по уведомлениям"},
                ]
            },
        )
        print("Commands:", r.json())


if __name__ == "__main__":
    asyncio.run(setup_bot())
