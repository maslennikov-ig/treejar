from __future__ import annotations

from datetime import datetime
from typing import Any

from src.dialogue.state import (
    DialogueDecision,
    DialogueSlots,
    DialogueState,
    DialogueTrace,
    LastQuestion,
)


def apply_extracted_details(
    state: DialogueState, details: dict[str, Any]
) -> DialogueState:
    slot_updates: dict[str, Any] = {}
    for key in DialogueSlots.model_fields:
        if key in details:
            slot_updates[key] = details[key]

    if not slot_updates:
        return state.model_copy(deep=True)

    return state.model_copy(
        update={"slots": state.slots.model_copy(update=slot_updates, deep=True)},
        deep=True,
    )


def set_last_question(
    state: DialogueState,
    *,
    flow: str,
    prompt_key: str,
    expected_slots: list[str],
    asked_at: str | datetime | None = None,
) -> DialogueState:
    return state.model_copy(
        update={
            "active_flow": flow,
            "last_question": LastQuestion(
                flow=flow,
                prompt_key=prompt_key,
                asked_at=asked_at,
                expected_slots=list(expected_slots),
            ),
        },
        deep=True,
    )


def mark_quote_sent(
    state: DialogueState,
    *,
    post_quotation_status: str | None = None,
) -> DialogueState:
    slots = state.slots.model_copy(
        update={
            "quote_sent": True,
            "post_quotation_status": post_quotation_status,
        },
        deep=True,
    )
    return state.model_copy(update={"slots": slots}, deep=True)


def build_trace(
    *,
    mode: str,
    decision: DialogueDecision,
    before_state: DialogueState,
    after_state: DialogueState,
    legacy_route: str | None = None,
    kernel_route: str | None = None,
    mismatch_reason: str | None = None,
) -> DialogueTrace:
    return DialogueTrace(
        mode=mode,
        legacy_route=legacy_route,
        kernel_route=kernel_route,
        decision=decision,
        slot_diff=_slot_diff(before_state, after_state),
        mismatch_reason=mismatch_reason,
    )


def append_trace_bounded(
    state: DialogueState, trace: DialogueTrace, *, limit: int = 20
) -> DialogueState:
    bounded_limit = max(limit, 0)
    traces = [*state.trace_history, trace]
    traces = traces[-bounded_limit:] if bounded_limit else []
    return state.model_copy(update={"trace_history": traces}, deep=True)


def _slot_diff(
    before_state: DialogueState, after_state: DialogueState
) -> dict[str, dict[str, Any]]:
    before = before_state.slots.model_dump(mode="json")
    after = after_state.slots.model_dump(mode="json")
    diff: dict[str, dict[str, Any]] = {}
    for key in before.keys() | after.keys():
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value != after_value:
            diff[key] = {"before": before_value, "after": after_value}
    return diff
