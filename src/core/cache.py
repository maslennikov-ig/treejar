from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

CRM_NOT_FOUND_SENTINEL: dict[str, bool] = {"__not_found__": True}
CRM_NEGATIVE_CACHE_TTL_SECONDS = 600
CRM_NEGATIVE_CACHE_KEY_PREFIX = "crm_contact_miss:"


def _phone_cache_variants(phone: str) -> list[str]:
    stripped = phone.strip()
    if not stripped:
        return []
    variants = [stripped]
    digits = re.sub(r"\D", "", stripped)
    if digits:
        for candidate in (digits, f"+{digits}"):
            if candidate not in variants:
                variants.append(candidate)
    return variants


async def get_cached_crm_profile(
    redis_client: Any, phone: str
) -> dict[str, Any] | None:
    data = await redis_client.get(f"crm_profile:{phone}")
    if data:
        result: dict[str, Any] = json.loads(data)
        if result == CRM_NOT_FOUND_SENTINEL:
            return None
        return result
    return None


async def set_cached_crm_profile(
    redis_client: Any, phone: str, profile: dict[str, Any], ttl: int = 3600
) -> None:
    await redis_client.set(f"crm_profile:{phone}", json.dumps(profile), ex=ttl)


async def is_crm_contact_negatively_cached(redis_client: Any, phone: str) -> bool:
    """Return True when a recent CRM lookup recorded a negative sentinel for *phone*."""
    if redis_client is None or not phone:
        return False
    try:
        raw = await redis_client.get(f"{CRM_NEGATIVE_CACHE_KEY_PREFIX}{phone}")
    except Exception:
        logger.debug("CRM negative cache read failed", exc_info=True)
        return False
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", errors="ignore")
    if not isinstance(raw, str):
        return False
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return False
    return isinstance(payload, dict) and payload == CRM_NOT_FOUND_SENTINEL


async def set_crm_contact_negative_cache(
    redis_client: Any,
    phone: str,
    *,
    ttl: int = CRM_NEGATIVE_CACHE_TTL_SECONDS,
) -> None:
    """Record a 600s negative-cache sentinel for a missing Zoho CRM contact."""
    if redis_client is None or not phone:
        return
    try:
        await redis_client.set(
            f"{CRM_NEGATIVE_CACHE_KEY_PREFIX}{phone}",
            json.dumps(CRM_NOT_FOUND_SENTINEL, separators=(",", ":")),
            ex=ttl,
        )
    except Exception:
        logger.debug("CRM negative cache write failed", exc_info=True)


async def invalidate_crm_contact_cache(redis_client: Any, phone: str) -> None:
    """Invalidate negative and positive CRM profile cache entries for *phone*."""
    if redis_client is None or not phone:
        return
    for variant in _phone_cache_variants(phone):
        for key in (
            f"{CRM_NEGATIVE_CACHE_KEY_PREFIX}{variant}",
            f"crm_profile:{variant}",
        ):
            try:
                await redis_client.delete(key)
            except Exception:
                logger.debug("CRM cache invalidation failed", exc_info=True)
