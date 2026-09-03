"""Fail-closed authorization for audited Wazzup side effects.

The scope is local to one audited call and one asyncio task. It is not a
cached permission: the transport rechecks database state before each attempt.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Any, NoReturn

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.conversation import Conversation
from src.models.system_config import SystemConfig

logger = logging.getLogger(__name__)


class OutboundSendBlocked(RuntimeError):
    """No outbound side effect is authorized; callers must not report success."""


def _deny(reason: str) -> NoReturn:
    logger.warning("Wazzup outbound blocked: %s", reason)
    raise OutboundSendBlocked(reason)


@dataclass(frozen=True)
class _SendScope:
    db: AsyncSession
    provider: Any
    conversation_id: uuid.UUID
    chat_id: str
    task: asyncio.Task[Any] | None

    async def check(self) -> None:
        allowed = settings.wazzup_outbound_allowed_channel_id
        if not allowed or settings.wazzup_channel_id != allowed:
            _deny("sender_not_allowed")
        if self.provider.channel_id != allowed:
            _deny("provider_channel_not_allowed")

        # Select columns, not cached ORM objects: a retained identity-map value
        # must not override a newly disabled bot or updated inbound channel.
        enabled = await self.db.scalar(
            select(SystemConfig.value).where(SystemConfig.key == "bot_enabled")
        )
        if enabled is not True and not (
            isinstance(enabled, str) and enabled.lower() == "true"
        ):
            _deny("bot_not_enabled")
        result = await self.db.execute(
            select(Conversation.phone, Conversation.metadata_).where(
                Conversation.id == self.conversation_id
            )
        )
        row = result.one_or_none()
        if row is None:
            _deny("conversation_missing")
        phone, metadata = row
        if phone != self.chat_id:
            _deny("recipient_mismatch")
        if (
            not isinstance(metadata, dict)
            or metadata.get("inbound_channel_id") != allowed
        ):
            _deny("inbound_channel_not_allowed")


_send_scope: ContextVar[_SendScope | None] = ContextVar(
    "wazzup_send_scope", default=None
)


def guarded_wazzup_send[Result](
    func: Callable[..., Awaitable[Result]],
) -> Callable[..., Awaitable[Result]]:
    """Bind the persisted conversation to a single audited send operation."""

    @wraps(func)
    async def wrapped(db: AsyncSession, **kwargs: Any) -> Result:
        scope = _SendScope(
            db=db,
            provider=kwargs["provider"],
            conversation_id=kwargs["conversation_id"],
            chat_id=kwargs["chat_id"],
            task=asyncio.current_task(),
        )
        await scope.check()
        token = _send_scope.set(scope)
        try:
            return await func(db, **kwargs)
        finally:
            _send_scope.reset(token)

    return wrapped


async def require_wazzup_send(
    provider: Any, *, chat_id: object, channel_id: object
) -> None:
    """Check before uploads and every outbound HTTP attempt, including retries."""
    scope = _send_scope.get()
    if (
        scope is None
        or scope.provider is not provider
        or scope.task is not asyncio.current_task()
    ):
        _deny("audited_send_scope_required")
    if channel_id != settings.wazzup_outbound_allowed_channel_id:
        _deny("payload_channel_not_allowed")
    if chat_id != provider.outbound_chat_id(scope.chat_id):
        _deny("payload_recipient_mismatch")
    await scope.check()
