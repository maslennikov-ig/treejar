"""Privacy-safe identifiers and scheduling policy for queued inbound batches."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import time
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


def serialize_inbound_message(
    msg: Any,
    *,
    received_at: float | None = None,
) -> str:
    """Serialize an inbound message with server-side webhook receipt epoch time."""
    payload = msg.model_dump(mode="json")
    payload["received_at"] = time.time() if received_at is None else float(received_at)
    return json.dumps(payload, separators=(",", ":"))


def _queued_customer_receipt(raw: str | bytes) -> tuple[bool, float | None]:
    """Return (is_manager, received_at) for one queued inbound payload."""
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return False, None
    if not isinstance(payload, dict):
        return False, None
    author_type = payload.get("authorType")
    is_manager = author_type == "manager" or (
        payload.get("isEcho") is True and author_type != "bot"
    )
    value = payload.get("received_at")
    if isinstance(value, bool) or not isinstance(value, int | float):
        return is_manager, None
    return is_manager, float(value)


def inbound_quiet_wait_seconds(
    received_ats: list[float],
    *,
    now: float,
    quiet_seconds: float,
    max_wait_seconds: float,
) -> float:
    """Seconds left before a burst of customer messages counts as finished.

    The newest message must be ``quiet_seconds`` old, but the oldest one never
    waits past ``max_wait_seconds`` so a customer who keeps typing still gets a
    reply.
    """
    if not received_ats or quiet_seconds <= 0:
        return 0.0
    until_quiet = max(received_ats) + quiet_seconds - now
    until_cap = min(received_ats) + max(quiet_seconds, max_wait_seconds) - now
    return max(0.0, min(until_quiet, until_cap))


async def wait_for_inbound_quiet(
    redis: Any,
    queue_key: str,
    *,
    sleep: Any = None,
    clock: Any = time.time,
) -> float:
    """Hold an owned batch until the customer has stopped typing.

    WhatsApp customers split one request into several messages 10-40 seconds
    apart; answering after the first produced two or three replies, some of
    them contradicting each other (pilot dialogues of 2026-11-05). Returns the
    total seconds waited. Any Redis failure stops waiting instead of blocking.
    """
    import asyncio

    sleeper = sleep or asyncio.sleep
    quiet = float(settings.inbound_quiet_seconds)
    max_wait = float(settings.inbound_quiet_max_wait_seconds)
    waited = 0.0
    if quiet <= 0:
        return waited
    while True:
        try:
            queued = await redis.lrange(queue_key, 0, -1)
        except Exception:
            logger.warning("Could not inspect inbound queue for quiet window")
            return waited
        receipts = [_queued_customer_receipt(raw) for raw in queued or []]
        if any(is_manager for is_manager, _ in receipts):
            # A human took over; record it now instead of waiting for quiet.
            return waited
        received = [value for _, value in receipts if value is not None]
        remaining = inbound_quiet_wait_seconds(
            received,
            now=clock(),
            quiet_seconds=quiet,
            max_wait_seconds=max_wait,
        )
        if remaining <= 0:
            return waited
        step = min(remaining, 5.0)
        await sleeper(step)
        waited += step
