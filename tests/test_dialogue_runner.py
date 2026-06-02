import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from src.dialogue.state import DialogueState
from src.models.conversation import Conversation
from src.schemas.common import SalesStage


def _conversation(*, customer_name: str | None = None) -> Conversation:
    return Conversation(
        id=uuid.uuid4(),
        phone="+971500000001",
        customer_name=customer_name,
        sales_stage=SalesStage.GREETING.value,
        language="en",
        escalation_status="none",
        metadata_=None,
    )


def _product_preference_kernel_state(
    *,
    frame_id: str = "product_preference:test",
    expires_at: str | None = None,
    max_customer_turns: int = 6,
    turns_seen: int = 0,
) -> dict[str, Any]:
    frame: dict[str, Any] = {
        "frame_id": frame_id,
        "flow": "product_selection",
        "question_kind": "product_preference",
        "prompt_key": "workspace_luma_novo_preference",
        "status": "active",
        "priority": 80,
        "max_customer_turns": max_customer_turns,
        "turns_seen": turns_seen,
        "expected_slots": [
            {
                "slot": "workspace_preference",
                "accepted_values": ["open", "private"],
                "aliases": {
                    "open": ["more open", "for team", "novo"],
                },
            }
        ],
        "source_refs": [
            {"kind": "product_family", "value": "SKYLAND NOVO"},
            {"kind": "product_family", "value": "LUMA"},
        ],
    }
    if expires_at is not None:
        frame["expires_at"] = expires_at
    return {
        "version": 1,
        "active_flow": "product_selection",
        "slots": {"customer_name": "Lili"},
        "expected_answer_frames": [frame],
    }


def _product_preference_match(
    *,
    frame_id: str = "product_preference:test",
    extra_note: str | None = None,
    fulfilled: bool = True,
    missing_required_slots: list[str] | None = None,
) -> dict[str, Any]:
    filled_slots: dict[str, Any] = {"workspace_preference": "open"}
    if extra_note is not None:
        filled_slots["note"] = extra_note
    return {
        "matched": True,
        "frame_id": frame_id,
        "confidence": "high",
        "filled_slots": filled_slots,
        "route": "product_preference_answer",
        "interruption": False,
        "blocker": None,
        "fulfilled": fulfilled,
        "missing_required_slots": missing_required_slots or [],
    }


def test_dialogue_kernel_graph_orders_expected_answer_steps() -> None:
    from src.dialogue.runner import _build_graph

    graph = _build_graph()

    assert set(graph.nodes) >= {"expire_frames", "match_expected_answer", "decide"}
    assert graph.edges == {
        ("__start__", "expire_frames"),
        ("expire_frames", "match_expected_answer"),
        ("match_expected_answer", "decide"),
        ("decide", "__end__"),
    }


@pytest.mark.asyncio
async def test_dialogue_kernel_legacy_mode_is_noop() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation()

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="legacy",
        enforced_flows=(),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.handled is False
    assert conv.metadata_ is None


@pytest.mark.asyncio
async def test_dialogue_kernel_legacy_mode_does_not_invoke_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    async def fail_graph(_input: object) -> object:
        raise RuntimeError("graph invoked")

    monkeypatch.setattr(runner, "_COMPILED_GRAPH", SimpleNamespace(ainvoke=fail_graph))
    conv = _conversation()

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="legacy",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "legacy_fallback"
    assert conv.metadata_ is None


@pytest.mark.asyncio
async def test_dialogue_kernel_hydrates_known_customer_name_from_conversation() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lili")

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="enforce",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "product_selection"
    assert result.state.slots.customer_name == "Lili"


@pytest.mark.asyncio
async def test_dialogue_kernel_shadow_records_bounded_trace_without_handling() -> None:
    from src.dialogue.runner import record_legacy_route, run_dialogue_kernel

    conv = _conversation()

    result = await run_dialogue_kernel(
        conversation=conv,
        text="Hello, I need SKYLAND NOVO 2400 and CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="shadow",
        enforced_flows=("name_gate", "product_selection"),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "name_gate"
    assert result.decision.side_effects_allowed is False

    record_legacy_route(conv, result, legacy_route="mock-model|name-gate")

    assert conv.metadata_ is not None
    traces = conv.metadata_["dialogue_kernel"]["traces"]
    assert len(traces) == 1
    assert traces[0]["mode"] == "shadow"
    assert traces[0]["kernel_route"] == "name_gate"
    assert traces[0]["legacy_route"] == "mock-model|name-gate"
    assert traces[0]["decision"]["side_effects_allowed"] is False


@pytest.mark.asyncio
async def test_dialogue_kernel_enforce_handles_only_allowlisted_flow() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation()

    blocked = await run_dialogue_kernel(
        conversation=conv,
        text="Hello, I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="enforce",
        enforced_flows=("quote_details",),
        trace_enabled=True,
    )
    assert blocked.should_use_kernel is False
    assert blocked.decision.flow == "name_gate"

    allowed = await run_dialogue_kernel(
        conversation=conv,
        text="Hello, I need CH 616",
        recent_history=[],
        is_first_turn=True,
        mode="enforce",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert allowed.should_use_kernel is True
    assert allowed.decision.flow == "name_gate"
    assert allowed.decision.response_text == "Hello"
    assert allowed.decision.side_effects_allowed is True


@pytest.mark.asyncio
async def test_dialogue_kernel_quantity_selection_delegates_to_legacy_when_allowlisted() -> (
    None
):
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lil")

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I need 6 CH 616",
        recent_history=[
            "assistant: For ergonomic chairs, choose CH 616, CH-190, or CH 620."
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert result.decision.flow == "product_selection"
    assert result.decision.handled is False
    assert result.should_use_kernel is False
    assert result.decision.metadata["refs"][0]["quantity"] == 6


@pytest.mark.asyncio
async def test_dialogue_kernel_expires_expected_answer_frames_before_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    seen_frame_statuses: list[str] = []

    def fake_match_expected_answer(
        *,
        dialogue_state: DialogueState,
        text: str,
        recent_history: list[str],
    ) -> dict[str, Any]:
        assert text == "open"
        assert recent_history == [
            "assistant: Would you prefer NOVO/open or LUMA/private?"
        ]
        seen_frame_statuses.extend(
            frame.status for frame in dialogue_state.expected_answer_frames
        )
        return {"matched": False}

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        fake_match_expected_answer,
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {
        "dialogue_kernel": {
            "state": _product_preference_kernel_state(max_customer_turns=0)
        }
    }

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="open",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="shadow",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert seen_frame_statuses == ["expired"]
    assert result.decision.flow == "legacy_fallback"
    assert (
        conv.metadata_["dialogue_kernel"]["state"]["expected_answer_frames"][0][
            "status"
        ]
        == "expired"
    )


@pytest.mark.asyncio
async def test_dialogue_kernel_persists_expired_frame_state_without_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        lambda **_kwargs: {"matched": False},
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {
        "dialogue_kernel": {
            "state": _product_preference_kernel_state(max_customer_turns=0)
        }
    }

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="open",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="shadow",
        enforced_flows=("product_selection",),
        trace_enabled=False,
    )

    assert result.state.expected_answer_frames[0].status == "expired"
    assert (
        conv.metadata_["dialogue_kernel"]["state"]["expected_answer_frames"][0][
            "status"
        ]
        == "expired"
    )
    assert conv.metadata_["dialogue_kernel"]["traces"] == []


@pytest.mark.asyncio
async def test_dialogue_kernel_enforce_handles_allowlisted_expected_answer_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        lambda **_kwargs: _product_preference_match(),
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {"dialogue_kernel": {"state": _product_preference_kernel_state()}}

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I prefer more open for team",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is True
    assert result.decision.action == "product_preference_answer"
    assert result.decision.flow == "product_selection"
    assert result.decision.side_effects_allowed is True
    frame = result.state.expected_answer_frames[0]
    assert frame.status == "fulfilled"
    assert frame.filled_slots == {"workspace_preference": "open"}


@pytest.mark.asyncio
async def test_dialogue_kernel_persists_fulfilled_frame_state_without_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        lambda **_kwargs: _product_preference_match(),
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {"dialogue_kernel": {"state": _product_preference_kernel_state()}}

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I prefer more open for team",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("product_selection",),
        trace_enabled=False,
    )

    assert result.should_use_kernel is True
    assert result.state.expected_answer_frames[0].status == "fulfilled"
    persisted_frame = conv.metadata_["dialogue_kernel"]["state"][
        "expected_answer_frames"
    ][0]
    assert persisted_frame["status"] == "fulfilled"
    assert persisted_frame["filled_slots"] == {"workspace_preference": "open"}
    assert conv.metadata_["dialogue_kernel"]["traces"] == []


@pytest.mark.asyncio
async def test_dialogue_kernel_uses_real_expected_answer_matcher_with_expiring_frame() -> (
    None
):
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {
        "dialogue_kernel": {
            "state": _product_preference_kernel_state(
                expires_at="2999-06-02T10:30:00+00:00"
            )
        }
    }

    result = await run_dialogue_kernel(
        conversation=conv,
        text="I prefer more open for team",
        recent_history=[
            "assistant: Would you prefer a private LUMA setup or open NOVO for team?"
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is True
    assert result.decision.action == "product_preference_answer"
    assert result.state.expected_answer_frames[0].status == "fulfilled"
    assert result.state.expected_answer_frames[0].filled_slots == {
        "workspace_preference": "open"
    }


@pytest.mark.asyncio
async def test_dialogue_kernel_does_not_fulfill_partial_required_slot_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        lambda **_kwargs: _product_preference_match(
            fulfilled=False,
            missing_required_slots=["delivery_address"],
        ),
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {"dialogue_kernel": {"state": _product_preference_kernel_state()}}

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I prefer more open for team",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.flow == "legacy_fallback"
    assert result.state.expected_answer_frames[0].status == "active"
    assert result.state.expected_answer_frames[0].filled_slots == {}


@pytest.mark.asyncio
async def test_dialogue_kernel_unallowlisted_expected_answer_match_falls_back_to_legacy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        lambda **_kwargs: _product_preference_match(),
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {"dialogue_kernel": {"state": _product_preference_kernel_state()}}

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I prefer more open for team",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("name_gate",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.action == "product_preference_answer"
    assert result.decision.side_effects_allowed is False


@pytest.mark.asyncio
async def test_dialogue_kernel_shadow_records_bounded_expected_answer_trace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from src.dialogue import runner

    monkeypatch.setattr(
        runner,
        "_match_expected_answer",
        lambda **_kwargs: _product_preference_match(extra_note="x" * 500),
        raising=False,
    )
    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {"dialogue_kernel": {"state": _product_preference_kernel_state()}}

    result = await runner.run_dialogue_kernel(
        conversation=conv,
        text="I prefer more open for team",
        recent_history=["assistant: Would you prefer NOVO/open or LUMA/private?"],
        is_first_turn=False,
        mode="shadow",
        enforced_flows=("product_selection",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is False
    assert result.decision.side_effects_allowed is False
    trace = conv.metadata_["dialogue_kernel"]["traces"][-1]
    expected_answer = trace["decision"]["metadata"]["expected_answer"]
    assert expected_answer["match"]["frame_id"] == "product_preference:test"
    assert expected_answer["proposal"] == {
        "action": "product_preference_answer",
        "flow": "product_selection",
        "handled": True,
    }
    assert len(expected_answer["match"]["filled_slots"]["note"]) == 240
    assert expected_answer["match"]["filled_slots"]["note"].endswith("...")


@pytest.mark.asyncio
async def test_dialogue_kernel_post_quotation_hold_preserves_context() -> None:
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Lili")
    conv.metadata_ = {
        "dialogue_kernel": {
            "state": {
                "version": 1,
                "active_flow": "post_quotation_hold",
                "slots": {
                    "customer_name": "Lili",
                    "selected_items": [{"sku": "CH-616", "quantity": 1}],
                    "quote_sent": True,
                    "post_quotation_status": "awaiting_customer_decision",
                },
                "last_question": {
                    "flow": "post_quotation_hold",
                    "prompt_key": "quote_sent_check",
                    "expected_slots": ["post_quotation_status"],
                },
            }
        }
    }

    result = await run_dialogue_kernel(
        conversation=conv,
        text="ok",
        recent_history=[
            "assistant: I sent the quotation PDF. Please let me know if it works for you."
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("post_quotation_hold",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is True
    assert result.decision.flow == "post_quotation_hold"
    assert "quotation" in (result.decision.response_text or "").lower()
    assert conv.metadata_["dialogue_kernel"]["state"]["slots"]["quote_sent"] is True


@pytest.mark.asyncio
async def test_dialogue_kernel_post_quotation_hold_loads_legacy_quote_metadata() -> (
    None
):
    from src.dialogue.runner import run_dialogue_kernel

    conv = _conversation(customer_name="Vituzone Buyer")
    conv.metadata_ = {
        "last_quote_status": "sent",
        "pending_quote_selection": {
            "source": "quotation_sent",
            "items": [{"sku": "CH 616", "quantity": 12}],
        },
    }

    result = await run_dialogue_kernel(
        conversation=conv,
        text="Can you send a sample first and give a better discount?",
        recent_history=[
            "assistant: I have shared the quotation for 12 chairs. Please let me know if you would like to proceed.",
            "user: Can you send a sample first and give a better discount?",
        ],
        is_first_turn=False,
        mode="enforce",
        enforced_flows=("post_quotation_hold",),
        trace_enabled=True,
    )

    assert result.should_use_kernel is True
    assert result.decision.flow == "post_quotation_hold"
    assert result.state.slots.quote_sent is True
    assert result.state.slots.selected_items == [{"sku": "CH 616", "quantity": 12}]
