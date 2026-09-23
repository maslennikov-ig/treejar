"""Two quick customer messages get one reply (tj-uz6j.7).

Production conversation fa224cab (2026-09-23): "of course" at 15:59 and "4" at
16:00 produced two replies, 16:00:09 and 16:01:31. The second message arrived
while the first reply was being generated, so the first reply answered without
it and the second answered a conversation whose last reply already missed it.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.llm import LLMResponse
from src.models.conversation import Conversation
from src.models.message import Message
from src.schemas.webhook import WazzupIncomingMessage
from src.services import chat
from src.services.chat import (
    MAX_SUPERSEDED_BATCH_MESSAGES,
    _reply_may_be_superseded,
    process_incoming_batch,
)
from src.services.inbound_batch import inbound_chat_reference, inbound_queue_key
from src.services.runtime_execution_evidence import RuntimeToolTrace

CHAT_ID = "971500000001"
CHANNEL_ID = "chan-1"


@pytest.fixture(autouse=True)
def authorized_chat_batch_unit_fixture() -> Iterator[None]:
    with patch("src.services.outbound_safety._SendScope.check", new_callable=AsyncMock):
        yield


class _FakeRedis:
    """The list, lock and script semantics the inbound batch loop relies on."""

    def __init__(self) -> None:
        self.lists: defaultdict[str, list[str]] = defaultdict(list)
        self.values: dict[str, Any] = {}

    async def set(
        self, key: str, value: Any, ex: int | None = None, nx: bool = False
    ) -> bool | None:
        if nx and key in self.values:
            return None
        self.values[key] = value
        return True

    async def get(self, key: str) -> Any:
        return self.values.get(key)

    async def lrange(self, key: str, _start: int, _end: int) -> list[str]:
        return list(self.lists[key])

    async def lmove(self, source: str, target: str, *_where: str) -> str | None:
        if not self.lists[source]:
            return None
        value = self.lists[source].pop(0)
        self.lists[target].append(value)
        return value

    async def llen(self, key: str) -> int:
        return len(self.lists[key])

    async def lpush(self, key: str, *values: str) -> int:
        for value in values:
            self.lists[key].insert(0, value)
        return len(self.lists[key])

    async def rpush(self, key: str, *values: str) -> int:
        self.lists[key].extend(values)
        return len(self.lists[key])

    async def eval(self, script: str, key_count: int, *args: str) -> int:
        keys, argv = args[:key_count], args[key_count:]
        if script == chat._RELEASE_OR_CONTINUE_INBOUND_SCRIPT:
            if self.values.get(keys[0]) != argv[0]:
                return -1
            if self.lists[keys[1]]:
                return 1
            self.values.pop(keys[0], None)
            return 0
        if script == chat._RELEASE_INBOUND_LOCK_SCRIPT:
            if self.values.get(keys[0]) == argv[0]:
                self.values.pop(keys[0], None)
                return 1
            return 0
        if script == chat._FINALIZE_INBOUND_BATCH_SCRIPT:
            self.lists.pop(keys[0], None)
            return 1
        raise AssertionError("unexpected script")

    def __getattr__(self, name: str) -> AsyncMock:
        return AsyncMock(return_value=None)


def _message(message_id: str, text: str, second: int) -> str:
    return WazzupIncomingMessage(
        messageId=message_id,
        chatId=CHAT_ID,
        chatType="whatsapp",
        type="text",
        text=text,
        channelId=CHANNEL_ID,
        timestamp=1790179140 + second,
    ).model_dump_json()


def _response(text: str, *tool_names: str) -> LLMResponse:
    traces = tuple(
        RuntimeToolTrace(
            call_id=f"call-{index}",
            tool_name=name,
            arguments_digest="0" * 64,
            outcome_digest="1" * 64,
            state="returned",
        )
        for index, name in enumerate(tool_names)
    )
    return LLMResponse(
        text=text,
        tokens_in=1,
        tokens_out=1,
        cost=0.0,
        model="test-model",
        tool_traces=traces,
    )


def test_only_state_only_runs_may_be_withdrawn() -> None:
    state_only = _response("ok", "search_products", "record_customer_requirements")
    assert _reply_may_be_superseded(state_only, 1)
    assert _reply_may_be_superseded(_response("ok"), 1)
    for external in ("create_quotation", "escalate_to_manager", "create_deal"):
        assert not _reply_may_be_superseded(_response("ok", external), 1)
    assert not _reply_may_be_superseded(state_only, MAX_SUPERSEDED_BATCH_MESSAGES)


async def _run_batches(
    first_reply: LLMResponse,
) -> tuple[list[str], AsyncMock, list[object]]:
    redis = _FakeRedis()
    queue_key = inbound_queue_key(inbound_chat_reference(CHAT_ID))
    redis.lists[queue_key].append(_message("m-1", "of course", 0))

    conversation = Conversation(
        id=uuid.uuid4(),
        phone=CHAT_ID,
        language="en",
        escalation_status="none",
        metadata_={"inbound_channel_id": CHANNEL_ID},
    )
    session = AsyncMock()
    added: list[object] = []
    session.add = MagicMock(side_effect=added.append)

    def execute(statement: Any) -> MagicMock:
        result = MagicMock()
        result.scalars.return_value.first.return_value = None
        if "wazzup_message_id" in str(statement):
            # Messages already stored are not stored again.
            result.scalars.return_value.all.return_value = [
                item.wazzup_message_id for item in added if isinstance(item, Message)
            ]
        else:
            result.scalars.return_value.all.return_value = [conversation]
        return result

    session.execute.side_effect = execute

    calls: list[str] = []

    async def process_message(**kwargs: Any) -> LLMResponse:
        calls.append(kwargs["combined_text"])
        if len(calls) == 1:
            # "4" arrives while the first reply is still being generated.
            await redis.rpush(queue_key, _message("m-2", "4", 55))
            return first_reply
        return _response("Recorded 2 x LUMA 9719-4 walnut for eight people.")

    wazzup = AsyncMock()
    wazzup.resolve_channel_phone = AsyncMock(return_value="+971551220665")
    send = AsyncMock()
    with (
        patch("src.services.chat.settings.wazzup_channel_id", CHANNEL_ID),
        patch("src.services.chat.async_session_factory") as session_factory,
        patch("src.services.chat.process_message", side_effect=process_message),
        patch("src.services.chat.WazzupProvider") as provider_cls,
        patch("src.services.chat.ZohoInventoryClient") as inventory_cls,
        patch("src.services.chat.ZohoCRMClient") as crm_cls,
        patch("src.services.chat.EmbeddingEngine"),
        patch("src.services.chat.send_wazzup_text_with_audit", send),
        patch(
            "src.services.chat._enqueue_summary_refresh_if_needed",
            new_callable=AsyncMock,
        ),
    ):
        session_factory.return_value.__aenter__.return_value = session
        provider_cls.return_value.__aenter__ = AsyncMock(return_value=wazzup)
        provider_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        for client_cls in (inventory_cls, crm_cls):
            client_cls.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
            client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
        await process_incoming_batch({"redis": redis}, inbound_chat_reference(CHAT_ID))
    return calls, send, added


@pytest.mark.asyncio
async def test_message_arriving_during_generation_merges_into_one_reply() -> None:
    calls, send, added = await _run_batches(
        _response("Which layout: 2 x 9719-4 or 4 x 9719-2?", "search_products")
    )

    assert calls == ["of course", "of course\n4"]
    send.assert_awaited_once()
    assert send.await_args.kwargs["text"].startswith("Recorded 2 x LUMA 9719-4")
    assistant = [
        item for item in added if isinstance(item, Message) and item.role == "assistant"
    ]
    assert [item.content for item in assistant] == [
        "Recorded 2 x LUMA 9719-4 walnut for eight people."
    ]
    customer = [
        item.wazzup_message_id
        for item in added
        if isinstance(item, Message) and item.role == "user"
    ]
    assert sorted(customer) == ["m-1", "m-2"]


@pytest.mark.asyncio
async def test_reply_after_an_external_action_is_still_sent() -> None:
    calls, send, _added = await _run_batches(
        _response("Your quotation is ready.", "create_quotation")
    )

    assert calls == ["of course", "4"]
    assert send.await_count == 2
    assert send.await_args_list[0].kwargs["text"] == "Your quotation is ready."
