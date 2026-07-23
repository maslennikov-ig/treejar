"""Privacy-safe identifiers for queued inbound message batches."""

from __future__ import annotations

import hashlib
import hmac
import re

from src.core.config import settings

_REFERENCE_PREFIX = "ib1_"
_REFERENCE_RE = re.compile(r"^ib1_[0-9a-f]{24}$")
_QUEUE_PREFIX = "wazzup_msgs:"
_PROCESSING_PREFIX = "wazzup:inbound:processing:"
_LOCK_PREFIX = "wazzup:inbound:lock:"
_EXECUTION_PREFIX = "wazzup:inbound:execution:"


def inbound_chat_reference(chat_id: str) -> str:
    """Return a stable keyed reference that does not expose the chat identifier."""
    digest = hmac.new(
        settings.app_secret_key.encode("utf-8"),
        f"noor-inbound-chat-v1\0{chat_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{_REFERENCE_PREFIX}{digest[:24]}"


def is_inbound_chat_reference(value: str) -> bool:
    """Return whether *value* is a current privacy-safe inbound reference."""
    return _REFERENCE_RE.fullmatch(value) is not None


def inbound_queue_key(batch_ref: str) -> str:
    """Return the Redis list key for a privacy-safe or legacy queue token."""
    return f"{_QUEUE_PREFIX}{batch_ref}"


def inbound_processing_key(batch_ref: str) -> str:
    """Return the durable in-flight list key for one inbound reference."""
    return f"{_PROCESSING_PREFIX}{batch_ref}"


def inbound_lock_key(batch_ref: str) -> str:
    """Return the ownership-lock key for one inbound reference."""
    return f"{_LOCK_PREFIX}{batch_ref}"


def inbound_execution_key(batch_id: str) -> str:
    """Return the replay guard key for one immutable inbound batch."""
    return f"{_EXECUTION_PREFIX}{batch_id}"
