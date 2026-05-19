from __future__ import annotations

from datetime import UTC, datetime

from src.dialogue.reducer import (
    append_trace_bounded,
    apply_extracted_details,
    build_trace,
    mark_quote_sent,
    set_last_question,
)
from src.dialogue.state import (
    DialogueDecision,
    DialogueSlots,
    DialogueState,
    LastQuestion,
)


def test_dialogue_state_loads_from_metadata_and_emits_patch() -> None:
    metadata = {
        "source": "whatsapp",
        "dialogue_state": {
            "version": 1,
            "active_flow": "quotation",
            "slots": {
                "customer_name": "Mira",
                "company": "Noor",
                "customer_type": "business",
                "delivery_address": "Dubai Marina",
                "selected_items": [{"sku": "CH-616", "quantity": 2}],
                "pending_product_refs": ["SKYLAND NOVO 2400"],
                "quote_sent": True,
                "post_quotation_status": "waiting_customer",
            },
            "last_question": {
                "flow": "quotation",
                "prompt_key": "ask_delivery_address",
                "asked_at": "2026-05-19T09:30:00+00:00",
                "expected_slots": ["delivery_address"],
            },
            "trace_history": [],
        },
    }

    state = DialogueState.from_conversation_metadata(metadata)

    assert state.active_flow == "quotation"
    assert state.slots.customer_name == "Mira"
    assert state.slots.selected_items == [{"sku": "CH-616", "quantity": 2}]
    assert state.last_question == LastQuestion(
        flow="quotation",
        prompt_key="ask_delivery_address",
        asked_at="2026-05-19T09:30:00+00:00",
        expected_slots=["delivery_address"],
    )
    assert state.to_metadata_patch() == {
        "dialogue_kernel": {
            "state": state.model_dump(mode="json"),
            "traces": [],
        }
    }


def test_dialogue_state_load_returns_defaults_for_missing_or_invalid_metadata() -> None:
    assert DialogueState.load(None).slots == DialogueSlots()
    assert (
        DialogueState.load({"dialogue_state": {"slots": "bad"}}).slots
        == DialogueSlots()
    )


def test_dialogue_state_falls_back_to_legacy_state_when_kernel_state_missing() -> None:
    metadata = {
        "dialogue_kernel": {"thread_id": "conversation:fixture", "flow": "legacy"},
        "dialogue_state": {
            "version": 1,
            "active_flow": "quotation",
            "slots": {"customer_name": "Mira"},
        },
    }

    state = DialogueState.load(metadata)

    assert state.thread_id == "conversation:fixture"
    assert state.active_flow == "quotation"
    assert state.slots.customer_name == "Mira"


def test_reducer_functions_return_new_state_without_mutating_original() -> None:
    original = DialogueState(active_flow="intake")
    updated = apply_extracted_details(
        original,
        {
            "customer_name": "Aisha",
            "company": "Treejar",
            "selected_items": [{"sku": "CP-2.1S", "quantity": 1}],
            "pending_product_refs": ["CH 616"],
        },
    )
    asked = set_last_question(
        updated,
        flow="quotation",
        prompt_key="ask_address",
        expected_slots=["delivery_address"],
        asked_at=datetime(2026, 5, 19, 12, 0, tzinfo=UTC),
    )
    quoted = mark_quote_sent(asked, post_quotation_status="sent")

    assert original.slots.customer_name is None
    assert original.slots.selected_items == []
    assert updated is not original
    assert updated.slots.customer_name == "Aisha"
    assert updated.slots.pending_product_refs == ["CH 616"]
    assert asked.last_question is not None
    assert asked.last_question.asked_at == datetime(2026, 5, 19, 12, 0, tzinfo=UTC)
    assert quoted.slots.quote_sent is True
    assert quoted.slots.post_quotation_status == "sent"


def test_build_trace_computes_slot_diff_and_serializes_bounded_payload() -> None:
    before = DialogueState(active_flow="intake")
    after = apply_extracted_details(
        before,
        {
            "customer_name": "Omar",
            "delivery_address": "Business Bay",
        },
    )
    decision = DialogueDecision(
        action="ask_next",
        flow="quotation",
        response_text="Please share the company name.",
        handled=True,
        side_effects_allowed=False,
        metadata={"large": "x" * 500},
    )

    trace = build_trace(
        mode="shadow",
        legacy_route="legacy_quotation",
        kernel_route="quotation",
        decision=decision,
        before_state=before,
        after_state=after,
        mismatch_reason="route_diff",
    )
    serialized = trace.to_bounded_dict(max_text_length=40)

    assert trace.slot_diff == {
        "customer_name": {"before": None, "after": "Omar"},
        "delivery_address": {"before": None, "after": "Business Bay"},
    }
    assert serialized["decision"]["metadata"]["large"].endswith("...")
    assert len(serialized["decision"]["metadata"]["large"]) == 40
    assert serialized["mismatch_reason"] == "route_diff"


def test_append_trace_bounded_keeps_newest_entries() -> None:
    state = DialogueState()

    for index in range(5):
        decision = DialogueDecision(action=f"a{index}", flow="quotation")
        trace = build_trace(
            mode="shadow",
            decision=decision,
            before_state=state,
            after_state=state,
        )
        state = append_trace_bounded(state, trace, limit=3)

    assert [item.decision.action for item in state.trace_history] == ["a2", "a3", "a4"]
