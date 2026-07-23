from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

import httpx

ZohoOAuthFailureKind = Literal[
    "http_status",
    "invalid_credentials",
    "invalid_expires_in",
    "invalid_json",
    "invalid_payload",
    "invalid_token_type",
    "lock_timeout",
    "oauth_error",
    "transport",
]

_ACCESS_TOKEN_VALIDITY_SECONDS = 3600
_CACHE_EXPIRY_BUFFER_SECONDS = 60
ZOHO_OAUTH_REFRESH_TIMEOUT_SECONDS = 15.0
ZOHO_OAUTH_REFRESH_LOCK_TTL_SECONDS = 20
ZOHO_OAUTH_LOCK_POLL_ATTEMPTS = 40
ZOHO_OAUTH_LOCK_POLL_INTERVAL_SECONDS = 0.5
_TERMINAL_OAUTH_ERROR_CODES = {
    "invalid_client",
    "invalid_client_secret",
    "invalid_code",
    "invalid_grant",
    "invalid_refresh_token",
    "unauthorized_client",
}
_RELEASE_LOCK_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class ZohoOAuthError(RuntimeError):
    """Sanitized token-refresh failure with explicit retry semantics."""

    def __init__(
        self,
        kind: ZohoOAuthFailureKind,
        *,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(f"Zoho OAuth token refresh failed ({kind})")
        self.kind = kind
        self.retryable = retryable
        self.status_code = status_code


@dataclass(frozen=True, slots=True)
class ZohoOAuthToken:
    access_token: str
    cache_ttl_seconds: int


def _retryable_http_status(status_code: int) -> bool:
    return status_code == 429 or status_code >= 500


def _normalized_error_code(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip().lower().replace(" ", "_")


def parse_zoho_oauth_response(response: httpx.Response) -> ZohoOAuthToken:
    """Validate a Zoho token response without exposing its body or credentials."""
    status_code = response.status_code
    try:
        payload = response.json()
    except (TypeError, ValueError, UnicodeDecodeError) as exc:
        raise ZohoOAuthError(
            "invalid_json",
            retryable=status_code < 400 or _retryable_http_status(status_code),
            status_code=status_code,
        ) from exc

    if not isinstance(payload, Mapping):
        raise ZohoOAuthError(
            "invalid_payload",
            retryable=status_code < 400 or _retryable_http_status(status_code),
            status_code=status_code,
        )

    error_code = _normalized_error_code(payload.get("error"))
    if error_code:
        terminal = error_code in _TERMINAL_OAUTH_ERROR_CODES
        raise ZohoOAuthError(
            "invalid_credentials" if terminal else "oauth_error",
            retryable=not terminal,
            status_code=status_code,
        )

    if not 200 <= status_code < 300:
        raise ZohoOAuthError(
            "http_status",
            retryable=_retryable_http_status(status_code),
            status_code=status_code,
        )

    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise ZohoOAuthError(
            "invalid_payload",
            retryable=True,
            status_code=status_code,
        )

    token_type = payload.get("token_type")
    if token_type is not None and (
        not isinstance(token_type, str) or token_type.strip().lower() != "bearer"
    ):
        raise ZohoOAuthError(
            "invalid_token_type",
            retryable=True,
            status_code=status_code,
        )

    expires_in_raw = payload.get("expires_in", _ACCESS_TOKEN_VALIDITY_SECONDS)
    try:
        if isinstance(expires_in_raw, bool):
            raise ValueError
        expires_in = int(expires_in_raw)
    except (TypeError, ValueError) as exc:
        raise ZohoOAuthError(
            "invalid_expires_in",
            retryable=True,
            status_code=status_code,
        ) from exc

    if expires_in <= 0:
        raise ZohoOAuthError(
            "invalid_expires_in",
            retryable=True,
            status_code=status_code,
        )

    bounded_validity = min(expires_in, _ACCESS_TOKEN_VALIDITY_SECONDS)
    cache_ttl = max(1, bounded_validity - _CACHE_EXPIRY_BUFFER_SECONDS)
    return ZohoOAuthToken(
        access_token=access_token.strip(),
        cache_ttl_seconds=cache_ttl,
    )


def zoho_oauth_transport_error() -> ZohoOAuthError:
    return ZohoOAuthError("transport", retryable=True)


async def release_zoho_oauth_lock(
    redis: Any,
    *,
    lock_key: str,
    owner_token: str,
) -> bool:
    """Release a refresh lock only when this caller still owns its lease."""
    released = await redis.eval(
        _RELEASE_LOCK_SCRIPT,
        1,
        lock_key,
        owner_token,
    )
    return bool(released)
