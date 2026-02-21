from __future__ import annotations

import hashlib
import hmac

from fastapi import Header, HTTPException, status


async def verify_wazzup_webhook(
    x_webhook_secret: str = Header(..., alias="X-Webhook-Secret"),
) -> None:
    """Verify Wazzup webhook authenticity via shared secret header."""
    from src.core.config import settings

    if not settings.wazzup_webhook_secret:
        return  # Skip verification in development

    if not hmac.compare_digest(x_webhook_secret, settings.wazzup_webhook_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret",
        )


def compute_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for payload verification."""
    return hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
