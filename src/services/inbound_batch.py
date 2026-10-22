"""Privacy-safe identifiers and scheduling policy for queued inbound batches."""

from __future__ import annotations

import hashlib
import hmac
import logging
import re
from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.core.config import get_system_config, settings

logger = logging.getLogger(__name__)

_REFERENCE_PREFIX = "ib1_"
_REFERENCE_RE = re.compile(r"^ib1_[0-9a-f]{24}$")
_QUEUE_PREFIX = "wazzup_msgs:"
_PROCESSING_PREFIX = "wazzup:inbound:processing:"
_LOCK_PREFIX = "wazzup:inbound:lock:"
_EXECUTION_PREFIX = "wazzup:inbound:execution:"
_GRACE_PREFIX = "wazzup:inbound:grace:"

# Standard batching window for every inbound turn.
DEFAULT_INBOUND_BATCH_DEFER_SECONDS = 5

# AC08: optional first-turn window that lets a human manager answer a brand-new
# conversation before Noor does. Default 0 keeps Noor instant.
FIRST_TURN_MANAGER_GRACE_SECONDS_KEY = "first_turn_manager_grace_seconds"
FIRST_TURN_GRACE_WEEKDAYS_ONLY_KEY = "first_turn_grace_weekdays_only"
FIRST_TURN_MANAGER_GRACE_MAX_SECONDS = 1800
# The grace marker outlives the deferred job by this margin so a client message
# arriving while the grace job is still running does not open a second window.
FIRST_TURN_GRACE_MARKER_BUFFER_SECONDS = 120
_UAE_TZ = ZoneInfo("Asia/Dubai")
_FALSE_VALUES = frozenset({"false", "0", "no", "off"})


def _parse_grace_seconds(raw: str) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return 0
    return max(0, min(FIRST_TURN_MANAGER_GRACE_MAX_SECONDS, value))


def _parse_weekdays_only(raw: str) -> bool:
    return str(raw).strip().lower() not in _FALSE_VALUES


async def _phone_has_prior_messages(db: Any, phone: str) -> bool:
    from sqlalchemy import select

    from src.models.conversation import Conversation
    from src.models.message import Message

    stmt = (
        select(Message.id)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(Conversation.phone == phone)
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalars().first() is not None


async def resolve_inbound_batch_defer_seconds(
    db: Any,
    *,
    phone: str,
    now_utc: datetime | None = None,
) -> int:
    """Return the batch defer for a client message from *phone*.

    Turn 1 of a brand-new conversation on an eligible UAE day waits for the
    configured manager grace; every other case uses the standard window. Any
    failure falls back to the standard window so inbound is never blocked.
    """
    default = DEFAULT_INBOUND_BATCH_DEFER_SECONDS
    try:
        grace = _parse_grace_seconds(
            await get_system_config(db, FIRST_TURN_MANAGER_GRACE_SECONDS_KEY, "0")
        )
        if grace <= 0:
            return default
        weekdays_only = _parse_weekdays_only(
            await get_system_config(db, FIRST_TURN_GRACE_WEEKDAYS_ONLY_KEY, "true")
        )
        if weekdays_only:
            now = now_utc or datetime.now(UTC)
            if now.astimezone(_UAE_TZ).weekday() in {5, 6}:
                return default
        if await _phone_has_prior_messages(db, phone):
            return default
        return max(default, grace)
    except Exception:
        logger.exception("Failed to resolve first-turn grace; using standard defer")
        return default


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


def inbound_grace_key(batch_ref: str) -> str:
    """Return the marker key for an open first-turn manager grace window."""
    return f"{_GRACE_PREFIX}{batch_ref}"
