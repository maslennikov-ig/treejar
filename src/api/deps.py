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

    When settings.api_key is empty (dev mode), all requests pass through.
    In production, the header must match settings.api_key.
    Uses secrets.compare_digest for timing-attack resistance.
    """
    if not settings.api_key:
        return ""  # No key configured = open (dev mode)
    if not api_key or not secrets.compare_digest(api_key, settings.api_key):
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key
