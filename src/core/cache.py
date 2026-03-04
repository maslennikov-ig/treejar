import json
from typing import Any


async def get_cached_crm_profile(
    redis_client: Any, phone: str
) -> dict[str, Any] | None:
    data = await redis_client.get(f"crm_profile:{phone}")
    if data:
        result: dict[str, Any] = json.loads(data)
        return result
    return None


async def set_cached_crm_profile(
    redis_client: Any, phone: str, profile: dict[str, Any], ttl: int = 3600
) -> None:
    await redis_client.set(f"crm_profile:{phone}", json.dumps(profile), ex=ttl)
