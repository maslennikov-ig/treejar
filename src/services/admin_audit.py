from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.admin_action_audit import AdminActionAudit

MASKED_VALUE = "[masked]"
SENSITIVE_KEY_FRAGMENTS = (
    "authorization",
    "cookie",
    "password",
    "secret",
    "session",
    "token",
    "api_key",
)


def _is_sensitive_key(key: object) -> bool:
    key_text = str(key).replace("-", "_").lower()
    return any(fragment in key_text for fragment in SENSITIVE_KEY_FRAGMENTS)


def mask_admin_audit_payload(value: Any) -> Any:
    """Return a JSON-safe copy with secret-like fields masked."""

    if isinstance(value, Mapping):
        return {
            str(key): MASKED_VALUE
            if _is_sensitive_key(key)
            else mask_admin_audit_payload(item)
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [mask_admin_audit_payload(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    return value


def _request_path(request: object | None) -> str | None:
    if request is None:
        return None
    url = getattr(request, "url", None)
    path = getattr(url, "path", None)
    if path is None:
        return None
    return str(path)


async def log_admin_action(
    db: AsyncSession,
    *,
    action: str,
    entity_type: str,
    entity_id: object | None = None,
    before: Any = None,
    after: Any = None,
    request: object | None = None,
    actor: str = "admin",
    metadata: Any = None,
) -> AdminActionAudit:
    """Create an audit row and flush it into the caller's transaction."""

    row = AdminActionAudit(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        request_path=_request_path(request),
        before=mask_admin_audit_payload(before),
        after=mask_admin_audit_payload(after),
        metadata_=mask_admin_audit_payload(metadata),
    )
    db.add(row)
    await db.flush()
    return row
