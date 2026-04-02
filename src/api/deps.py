from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from src.core.config import settings
from src.core.database import get_db
from src.core.redis import get_redis

# Re-export for convenient imports
__all__ = ["get_db", "get_redis", "require_api_key"]

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(
    api_key: str | None = Depends(_api_key_header),
) -> str:
    """Validate X-API-Key header for protected internal endpoints.

    In development, an empty settings.api_key keeps internal endpoints open.
    In production, the app fails closed if the key is missing from config,
    and the header must match settings.api_key when configured.
    Uses secrets.compare_digest for timing-attack resistance.
    """
    if not settings.api_key:
        if settings.is_production:
            raise HTTPException(
                status_code=503,
                detail="Internal API authentication is not configured",
            )
        return ""  # No key configured = open in local development
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key
