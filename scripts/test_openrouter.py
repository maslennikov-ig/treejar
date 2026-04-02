import asyncio

import aiohttp

from src.core.config import settings


async def main() -> None:
    print(f"Testing OpenRouter API with key: {settings.openrouter_api_key[:10]}...")
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "HTTP-Referer": "https://treejar.com",
        "X-Title": "Treejar AI Bot",
    }
    payload = {
        "model": settings.openrouter_model_fast,
        "messages": [{"role": "user", "content": "Say hello!"}],
    }
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            json=payload,
        ) as response,
    ):
        result = await response.json()
        if response.status == 200:
            print("✅ OpenRouter OK!")
            print(result["choices"][0]["message"]["content"])
        else:
            print("❌ OpenRouter Failed:", result)


asyncio.run(main())
