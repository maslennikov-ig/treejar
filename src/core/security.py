from __future__ import annotations

import hashlib
import hmac


def compute_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for payload verification."""
    return hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
