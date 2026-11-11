"""tj-r62i live pilot: large orders reach a manager, a manager reply silences Noor."""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.llm import LLMResponse
from src.llm.escalation_policy import (
    WHOLESALE_HANDOFF_METADATA_KEY,
    b2b_handoff_buckets,
    critical_escalation_decision,
    wholesale_handoff_from_history,
    wholesale_quantity,
)
from src.llm.message_processor import (
    _deterministic_wholesale_handoff,
    _ensure_wholesale_handoff_notice,
)
from src.main import app

CHANNEL = "b49b1b9d-757f-4104-b56d-8f43d62cc515"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Qty.350Nos", 350),
        ("Qty: 50", 50),
        ("quantity 25", 25),
        ("350 nos", 350),
        ("350Nos", 350),
        ("الكمية: 40", 40),
        ("We need 55 workstations", 55),
        ("4 table with 5 chairs like 4 set", 20),
        ("4 sets of 5 chairs", 20),
        ("12 desks and 12 chairs", 24),
    ],
)
def test_bulk_quantity_shorthand_is_a_wholesale_route(text: str, expected: int) -> None:
    assert wholesale_quantity(text) == expected
    assert "wholesale_or_bulk_project" in b2b_handoff_buckets(text)


@pytest.mark.parametrize(
    "text",
    [
        "Work station  with cabinet",
        "AED 500",
        "1600mm desk",
        "WK 360",
        "Qty 2",
        "quantity 1200mm",
        "2 nos",
        "We are furnishing for 25 people",
        "call me 0501234567",
        "Is the 2400 mm NOVO table available?",
    ],
)
def test_non_quantity_numbers_never_route(text: str) -> None:
    assert "wholesale_or_bulk_project" not in b2b_handoff_buckets(text)


RAMA_HISTORY = [
    "user: Hi. I am interested in purchasing office furniture.",
    "assistant: Hello, I'm Noor from Treejar.",
    "user: Qty.350Nos",
    "assistant: Understood, 350 pieces. Which type of furniture?",
    "user: Work station  with cabinet",
]


def test_quantity_and_item_in_separate_turns_still_route() -> None:
    decision = wholesale_handoff_from_history(
        "Work station  with cabinet", RAMA_HISTORY
    )

    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"
    assert "350 units" in decision.reason


def test_assistant_lines_never_trigger_the_route() -> None:
    decision = wholesale_handoff_from_history(
        "Thanks", ["assistant: We stock 350 chairs in Dubai.", "user: Thanks"]
    )
    assert decision.allowed is False


def _turn(
    text: str,
    history: list[str],
    *,
    escalation_status: str = "none",
    metadata: dict[str, Any] | None = None,
) -> Any:
    conversation = SimpleNamespace(
        id="conv-r62i",
        escalation_status=escalation_status,
        metadata_=dict(metadata or {}),
    )
    deps = SimpleNamespace(conversation=conversation, recent_history=history)
    return SimpleNamespace(deps=deps, combined_text=text, db=object())


@pytest.mark.asyncio
async def test_runtime_hands_the_350_unit_lead_to_a_manager() -> None:
    turn = _turn("Work station  with cabinet", RAMA_HISTORY)
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        handed_off = await _deterministic_wholesale_handoff(turn)

    assert handed_off is True
    notify.assert_awaited_once()
    kwargs = notify.await_args.kwargs
    assert kwargs["pause_bot"] is True
    assert "350 units" in kwargs["reason"]
    assert WHOLESALE_HANDOFF_METADATA_KEY in turn.deps.conversation.metadata_


def test_model_may_escalate_on_the_turn_after_the_quantity() -> None:
    decision = critical_escalation_decision(
        customer_text="Work station  with cabinet", recent_history=RAMA_HISTORY
    )
    assert decision.allowed is True
    assert decision.trigger == "wholesale_or_bulk_project"

    after = critical_escalation_decision(
        customer_text="Work station  with cabinet",
        recent_history=RAMA_HISTORY,
        conversation_metadata={WHOLESALE_HANDOFF_METADATA_KEY: "done"},
    )
    assert after.allowed is False


@pytest.mark.parametrize("status", ["pending", "in_progress", "manual_takeover"])
@pytest.mark.asyncio
async def test_no_second_handoff_while_a_human_owns_the_dialogue(status: str) -> None:
    turn = _turn("Qty.350Nos", RAMA_HISTORY, escalation_status=status)
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        assert await _deterministic_wholesale_handoff(turn) is False
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolved_handoff_does_not_reroute_on_old_history() -> None:
    turn = _turn(
        "Thanks, one more question",
        RAMA_HISTORY,
        escalation_status="resolved",
        metadata={WHOLESALE_HANDOFF_METADATA_KEY: "2026-11-05T14:10:00+00:00"},
    )
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        assert await _deterministic_wholesale_handoff(turn) is False
    notify.assert_not_awaited()


@pytest.mark.asyncio
async def test_small_order_stays_with_noor() -> None:
    turn = _turn("I need 4 chairs", ["user: Hi", "user: I need 4 chairs"])
    notify = AsyncMock()
    with patch(
        "src.integrations.notifications.escalation.notify_manager_escalation", notify
    ):
        assert await _deterministic_wholesale_handoff(turn) is False
    notify.assert_not_awaited()


def _response(text: str) -> LLMResponse:
    return LLMResponse(text=text, tokens_in=0, tokens_out=0, cost=0.0, model="m")


def test_reply_always_tells_the_customer_a_manager_takes_over() -> None:
    silent = _response("Here are two workstation options.")
    _ensure_wholesale_handoff_notice(silent, "en")
    assert "manager" in silent.text

    arabic = _response("إليك خيارين.")
    _ensure_wholesale_handoff_notice(arabic, "ar")
    assert "مدير" in arabic.text

    already = _response("A manager will contact you shortly.")
    _ensure_wholesale_handoff_notice(already, "en")
    assert already.text == "A manager will contact you shortly."


def _post(message: dict[str, Any], audit_matches: tuple[set[str], set[str]]) -> Any:
    app.state.redis = AsyncMock()
    app.state.redis.get = AsyncMock(return_value=None)
    app.state.arq_pool = AsyncMock()
    db_cm = AsyncMock()
    db_cm.__aenter__.return_value = AsyncMock()
    db_cm.__aexit__.return_value = False
    with (
        patch("src.api.v1.webhook._parse_allowed_networks", return_value=[]),
        patch("src.api.v1.webhook.async_session_factory", return_value=db_cm),
        patch("src.api.v1.webhook.update_wazzup_statuses", AsyncMock(return_value=0)),
        patch(
            "src.api.v1.webhook.apply_proposal_read_statuses",
            AsyncMock(return_value=0),
        ),
        patch(
            "src.api.v1.webhook.find_noor_outbound_audit_matches",
            AsyncMock(return_value=audit_matches),
        ),
        patch("src.api.v1.webhook.settings.wazzup_channel_id", CHANNEL),
    ):
        return TestClient(app).post(
            "/api/v1/webhook/wazzup", json={"messages": [message]}
        )


def _echo(status: str, message_id: str = "MANAGER-1") -> dict[str, Any]:
    return {
        "messageId": message_id,
        "channelId": CHANNEL,
        "chatId": "971501112233",
        "chatType": "whatsapp",
        "type": "text",
        "text": "Hello, this is Israullah from Treejar.",
        "dateTime": "2026-11-05T14:12:00.000Z",
        "status": status,
        "isEcho": True,
    }


@pytest.mark.parametrize("status", ["delivered", "read"])
def test_manager_echo_forwarded_only_with_a_later_status_still_takes_over(
    status: str,
) -> None:
    response = _post(_echo(status), (set(), set()))

    assert response.status_code == 200
    app.state.redis.rpush.assert_awaited_once()
    queued = json.loads(app.state.redis.rpush.await_args.args[1])
    assert queued["authorType"] == "manager"
    app.state.arq_pool.enqueue_job.assert_awaited_once()


def test_noor_own_delivered_echo_is_dropped_and_logged(caplog: Any) -> None:
    with caplog.at_level(logging.INFO, logger="uvicorn.error"):
        response = _post(_echo("delivered", "NOOR-1"), ({"NOOR-1"}, set()))

    assert response.status_code == 200
    app.state.redis.rpush.assert_not_called()
    assert "reason=noor_self_echo status=delivered isEcho=True" in caplog.text
    assert "Israullah" not in caplog.text
