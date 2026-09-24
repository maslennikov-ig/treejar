"""Background retry of a quotation Zoho refused (tj-i0n0)."""

from __future__ import annotations

import datetime
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.integrations.inventory.zoho_inventory import ZohoRateLimitError
from src.llm import quotation_deferral
from src.llm.quotation_deferral import PENDING_QUOTATION_KEY, defer_quotation
from src.services import quotation_retry
from src.services.quotation_retry import (
    RETRY_DELAYS_SECONDS,
    retry_delay_seconds,
    retry_pending_quotation,
)

_CONV_ID = "fa224cab-0000-0000-0000-000000000000"
_PHONE = "+79689818825"
_SKU = "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut"


def _rate_limit(retry_after: float | None = None) -> ZohoRateLimitError:
    request = httpx.Request("POST", "https://www.zohoapis.eu/inventory/v1/salesorders")
    return ZohoRateLimitError(
        "429 Too Many Requests",
        request=request,
        response=httpx.Response(429, request=request),
        retry_after_seconds=retry_after,
    )


class _ArqRedis:
    def __init__(self, *, lock_free: bool = True) -> None:
        self.lock_free = lock_free
        self.jobs: list[dict[str, Any]] = []
        self.released: list[str] = []

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> object:
        self.jobs.append({"name": name, "args": args, **kwargs})
        return object()

    async def set(self, key: str, value: Any, ex: Any = None, nx: bool = False) -> bool:
        return self.lock_free

    async def eval(self, script: str, numkeys: int, *args: Any) -> int:
        self.released.append(args[0])
        return 1

    async def get(self, key: str) -> Any:
        return None


def _now_iso(minutes_ago: int = 0) -> str:
    return (
        datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=minutes_ago)
    ).isoformat()


def _conversation(pending: dict[str, Any] | None = None) -> SimpleNamespace:
    metadata: dict[str, Any] = {
        "order_runtime": {
            "quote_workflow": {
                "version": 2,
                "consent": "granted",
                "lifecycle": "quote_requested",
            }
        }
    }
    if pending is not None:
        metadata[PENDING_QUOTATION_KEY] = pending
    return SimpleNamespace(id=_CONV_ID, phone=_PHONE, language="en", metadata_=metadata)


def _pending(**extra: Any) -> dict[str, Any]:
    return {
        "version": 1,
        "status": "pending",
        "items": [{"sku": _SKU, "quantity": 2}],
        "reason": "inventory_rate_limited",
        "first_deferred_at": _now_iso(2),
        "deferred_at": _now_iso(2),
        "source_message_id": "wa-msg-1",
        "attempts": 1,
        "manager_notified": False,
        **extra,
    }


def test_retry_schedule_is_bounded_and_honours_retry_after() -> None:
    assert [retry_delay_seconds(n) for n in range(1, 6)] == list(RETRY_DELAYS_SECONDS)
    assert retry_delay_seconds(6) is None
    assert retry_delay_seconds(0) is None
    assert retry_delay_seconds(1, retry_after=300) == 300
    assert retry_delay_seconds(1, retry_after=10) == 60
    assert retry_delay_seconds(1, retry_after=99999) == 3600


@pytest.mark.asyncio
async def test_deferral_schedules_one_background_retry() -> None:
    redis = _ArqRedis()
    conversation = _conversation()
    deps = SimpleNamespace(
        conversation=conversation, db=AsyncMock(), redis=redis, source_message_id="m1"
    )
    items = [SimpleNamespace(sku=_SKU, quantity=2)]
    with patch.object(
        quotation_deferral,
        "alert_managers_for_conversation",
        AsyncMock(return_value=True),
    ):
        await defer_quotation(deps, items, _rate_limit())
        # The customer's next turn is refused again: no second job.
        deps.source_message_id = "m2"
        await defer_quotation(deps, items, _rate_limit())

    assert len(redis.jobs) == 1
    job = redis.jobs[0]
    assert job["name"] == "retry_pending_quotation"
    assert job["args"] == (_CONV_ID, 1)
    assert job["_defer_by"] == RETRY_DELAYS_SECONDS[0]
    pending = conversation.metadata_[PENDING_QUOTATION_KEY]
    assert pending["background_attempt"] == 1
    assert pending["retry_scheduled_for"]
    assert pending["attempts"] == 2


@asynccontextmanager
async def _session(conversation: Any):  # type: ignore[no-untyped-def]
    db = AsyncMock()
    db.get.return_value = conversation
    db.add = MagicMock()
    yield db


def _job_patches(conversation: Any, create: AsyncMock) -> list[Any]:
    deps = SimpleNamespace(
        conversation=conversation,
        db=AsyncMock(),
        quotation_created=False,
        messaging_client=AsyncMock(),
    )

    async def fake_create(ctx: Any, items: Any) -> str:
        return await create(ctx, items)

    return [
        patch(
            "src.core.database.async_session_factory", lambda: _session(conversation)
        ),
        patch.object(quotation_retry, "_build_deps", lambda *a: deps),
        patch("src.llm.engine._create_quotation", fake_create),
    ]


async def _run(
    conversation: Any, create: AsyncMock, redis: _ArqRedis, attempt: int = 1
) -> tuple[str, AsyncMock, AsyncMock]:
    send = AsyncMock()
    alert = AsyncMock(return_value=True)
    patches = _job_patches(conversation, create)
    with (
        patches[0],
        patches[1],
        patches[2],
        patch.object(quotation_retry, "_send_confirmation", send),
        patch.object(quotation_retry, "alert_managers_for_conversation", alert),
    ):
        result = await retry_pending_quotation({"redis": redis}, _CONV_ID, attempt)
    return result, send, alert


@pytest.mark.asyncio
async def test_background_retry_sends_the_quotation_and_clears_pending() -> None:
    conversation = _conversation(_pending())
    redis = _ArqRedis()

    async def created(ctx: Any, items: Any) -> str:
        assert [(i.sku, i.quantity) for i in items] == [(_SKU, 2)]
        ctx.deps.quotation_created = True
        return "Quotation SO-1 has been prepared and sent to you."

    result, send, alert = await _run(
        conversation, AsyncMock(side_effect=created), redis
    )

    assert result == "created"
    assert PENDING_QUOTATION_KEY not in conversation.metadata_
    send.assert_awaited_once()
    assert "SO-1" in send.await_args.args[1]
    alert.assert_not_awaited()
    assert redis.released
    assert redis.jobs == []


@pytest.mark.asyncio
async def test_background_retry_reschedules_on_another_rate_limit() -> None:
    conversation = _conversation(_pending())
    redis = _ArqRedis()
    create = AsyncMock(side_effect=_rate_limit(retry_after=240))

    result, send, alert = await _run(conversation, create, redis, attempt=1)

    assert result == "rescheduled"
    assert redis.jobs[0]["args"] == (_CONV_ID, 2)
    assert redis.jobs[0]["_defer_by"] == 240
    pending = conversation.metadata_[PENDING_QUOTATION_KEY]
    assert pending["status"] == "pending"
    assert pending["attempts"] == 2
    send.assert_not_awaited()
    alert.assert_not_awaited()


@pytest.mark.asyncio
async def test_exhausted_retries_alert_managers_and_keep_it_pending() -> None:
    conversation = _conversation(_pending())
    redis = _ArqRedis()
    create = AsyncMock(side_effect=_rate_limit())

    result, send, alert = await _run(
        conversation, create, redis, attempt=len(RETRY_DELAYS_SECONDS)
    )

    assert result == "exhausted"
    assert redis.jobs == []
    alert.assert_awaited_once()
    assert alert.await_args.kwargs["final"] is True
    pending = conversation.metadata_[PENDING_QUOTATION_KEY]
    # The customer's next message can still finish it.
    assert pending["status"] == "pending"
    assert pending["manager_notified"] is True


@pytest.mark.asyncio
async def test_busy_chat_defers_to_the_customer_turn() -> None:
    conversation = _conversation(_pending())
    redis = _ArqRedis(lock_free=False)
    create = AsyncMock()

    result, _, _ = await _run(conversation, create, redis, attempt=3)

    assert result == "chat_busy"
    create.assert_not_awaited()
    assert redis.jobs[0]["args"] == (_CONV_ID, 3)
    assert redis.jobs[0]["_defer_by"] == 30


@pytest.mark.asyncio
async def test_retry_stops_when_nothing_is_pending_or_consent_was_withdrawn() -> None:
    create = AsyncMock()
    result, _, _ = await _run(_conversation(None), create, _ArqRedis())
    assert result == "nothing_pending"

    withdrawn = _conversation(_pending())
    withdrawn.metadata_["order_runtime"]["quote_workflow"]["consent"] = "declined"
    result, _, _ = await _run(withdrawn, create, _ArqRedis())
    assert result == "not_eligible"

    stale = _conversation(_pending(first_deferred_at=_now_iso(60 * 24 * 8)))
    result, _, _ = await _run(stale, create, _ArqRedis())
    assert result == "not_eligible"
    create.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_transient_outcome_hands_over_to_managers() -> None:
    conversation = _conversation(_pending())
    create = AsyncMock(return_value="Catalog and inventory disagree for this item.")

    result, send, alert = await _run(conversation, create, _ArqRedis())

    assert result == "needs_manager"
    send.assert_not_awaited()
    alert.assert_awaited_once()
    assert conversation.metadata_[PENDING_QUOTATION_KEY]["status"] == "needs_manager"


@pytest.mark.asyncio
async def test_retry_of_an_already_sent_quotation_stops_quietly() -> None:
    """tj-2ey4: the tool drops a pending request whose document was already sent."""

    from src.llm.quotation_deferral import clear_pending_quotation

    conversation = _conversation(_pending())

    async def already_sent(ctx: Any, items: Any) -> str:
        clear_pending_quotation(ctx.deps.conversation)
        return "Quotation SO-1, already sent to you, covers exactly these items."

    result, send, alert = await _run(
        conversation, AsyncMock(side_effect=already_sent), _ArqRedis()
    )

    assert result == "already_sent"
    assert PENDING_QUOTATION_KEY not in conversation.metadata_
    send.assert_not_awaited()
    alert.assert_not_awaited()
