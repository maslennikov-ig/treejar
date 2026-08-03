from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from src.dialogue.state import (
    DialogueDecision,
    DialogueSlots,
    DialogueState,
    DialogueTrace,
    ExpectedAnswerFrame,
    LastQuestion,
    QuoteConsent,
    QuoteLifecycle,
)

MAX_ACTIVE_EXPECTED_ANSWER_FRAMES = 8
MAX_EXPECTED_ANSWER_HISTORY = 20


def apply_extracted_details(
    state: DialogueState, details: dict[str, Any]
) -> DialogueState:
    slot_updates: dict[str, Any] = {}
    for key in DialogueSlots.model_fields:
        if key in details:
            slot_updates[key] = details[key]

    address = slot_updates.get("delivery_address")
    if isinstance(address, str) and _looks_like_budget_artifact(address):
        slot_updates.pop("delivery_address", None)
    company = slot_updates.get("company", state.slots.company)
    if isinstance(company, str) and company.strip():
        slot_updates["customer_type"] = None

    if not slot_updates:
        return state.model_copy(deep=True)

    return state.model_copy(
        update={"slots": state.slots.model_copy(update=slot_updates, deep=True)},
        deep=True,
    )


def reconcile_dialogue_state(state: DialogueState) -> DialogueState:
    """Return a coherent state derived from confirmed typed facts only."""
    slot_updates: dict[str, Any] = {}
    if state.slots.company and state.slots.customer_type == "individual":
        slot_updates["customer_type"] = None
    if _looks_like_budget_artifact(state.slots.delivery_address):
        slot_updates["delivery_address"] = None
    slots = (
        state.slots.model_copy(update=slot_updates, deep=True)
        if slot_updates
        else state.slots.model_copy(deep=True)
    )

    consent = state.quote_consent
    lifecycle = state.quote_lifecycle
    active_flow = state.active_flow
    if slots.quote_sent:
        consent = QuoteConsent.GRANTED
        lifecycle = QuoteLifecycle.CREATED
        active_flow = "post_quotation_hold"
    elif consent is not QuoteConsent.GRANTED:
        if consent is QuoteConsent.DECLINED:
            lifecycle = QuoteLifecycle.CONSULTATION
        elif slots.selected_items or lifecycle is not QuoteLifecycle.CONSULTATION:
            lifecycle = QuoteLifecycle.QUOTE_OFFERED
        active_flow = "product_selection" if slots.selected_items else active_flow
    elif slots.selected_items:
        lifecycle = (
            lifecycle
            if lifecycle in {QuoteLifecycle.CREATING, QuoteLifecycle.CREATED}
            else QuoteLifecycle.COLLECTING_DETAILS
        )
        active_flow = "quote_details"
    else:
        lifecycle = QuoteLifecycle.QUOTE_REQUESTED

    sales_stage = _reconciled_sales_stage(
        state.sales_stage,
        slots=slots,
        consent=consent,
        lifecycle=lifecycle,
    )

    return state.model_copy(
        update={
            "version": 2,
            "slots": slots,
            "quote_consent": consent,
            "quote_lifecycle": lifecycle,
            "active_flow": active_flow,
            "sales_stage": sales_stage,
        },
        deep=True,
    )


_SALES_STAGE_ORDER = (
    "greeting",
    "qualifying",
    "needs_analysis",
    "solution",
    "company_details",
    "quoting",
    "closing",
    "feedback",
)


def _reconciled_sales_stage(
    current: str | None,
    *,
    slots: DialogueSlots,
    consent: QuoteConsent,
    lifecycle: QuoteLifecycle,
) -> str:
    if lifecycle is QuoteLifecycle.CREATED:
        desired = "quoting"
    elif consent is QuoteConsent.GRANTED and lifecycle in {
        QuoteLifecycle.COLLECTING_DETAILS,
        QuoteLifecycle.CREATING,
    }:
        desired = "company_details"
    elif slots.selected_items:
        desired = "solution"
    elif slots.pending_product_refs:
        desired = "needs_analysis"
    elif slots.customer_name:
        desired = "qualifying"
    else:
        desired = "greeting"
    if current not in _SALES_STAGE_ORDER:
        return desired
    return max((current, desired), key=_SALES_STAGE_ORDER.index)


def _looks_like_budget_artifact(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = " ".join(value.casefold().split())
    if not normalized:
        return False
    if "budget" in normalized or "total" in normalized:
        return bool(any(char.isdigit() for char in normalized))
    return normalized.strip(" ,.").isdigit()


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


def push_expected_answer_frame(
    state: DialogueState,
    frame: ExpectedAnswerFrame,
) -> DialogueState:
    frames = [
        existing
        for existing in state.expected_answer_frames
        if existing.frame_id != frame.frame_id
    ]
    frames.append(frame)
    return state.model_copy(
        update={
            "active_flow": frame.flow,
            "expected_answer_frames": _bound_expected_answer_frames(frames),
        },
        deep=True,
    )


def mark_frame_fulfilled(
    state: DialogueState,
    frame_id: str,
    *,
    filled_slots: dict[str, Any] | None = None,
) -> DialogueState:
    return _update_expected_answer_frame(
        state,
        frame_id,
        status="fulfilled",
        filled_slots=filled_slots,
    )


def mark_frame_interrupted(
    state: DialogueState,
    frame_id: str,
) -> DialogueState:
    return _update_expected_answer_frame(state, frame_id, status="interrupted")


def expire_expected_answer_frames(
    state: DialogueState,
    *,
    now: datetime | None = None,
) -> DialogueState:
    frames: list[ExpectedAnswerFrame] = []
    for frame in state.expected_answer_frames:
        if frame.status != "active":
            frames.append(frame)
            continue
        turns_seen = frame.turns_seen + 1
        status = "expired" if _frame_is_expired(frame, turns_seen, now) else "active"
        frames.append(
            frame.model_copy(
                update={"turns_seen": turns_seen, "status": status},
                deep=True,
            )
        )
    return state.model_copy(
        update={"expected_answer_frames": _bound_expected_answer_frames(frames)},
        deep=True,
    )


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


def _update_expected_answer_frame(
    state: DialogueState,
    frame_id: str,
    *,
    status: str,
    filled_slots: dict[str, Any] | None = None,
) -> DialogueState:
    frames: list[ExpectedAnswerFrame] = []
    matched = False
    for frame in state.expected_answer_frames:
        if frame.frame_id != frame_id:
            frames.append(frame)
            continue
        matched = True
        updates: dict[str, Any] = {"status": status}
        if filled_slots:
            updates["filled_slots"] = {**frame.filled_slots, **filled_slots}
        frames.append(frame.model_copy(update=updates, deep=True))
    if not matched:
        return state.model_copy(deep=True)
    return state.model_copy(
        update={"expected_answer_frames": _bound_expected_answer_frames(frames)},
        deep=True,
    )


def _bound_expected_answer_frames(
    frames: list[ExpectedAnswerFrame],
) -> list[ExpectedAnswerFrame]:
    active_frames = sorted(
        (frame for frame in frames if frame.status == "active"),
        key=lambda frame: frame.priority,
        reverse=True,
    )[:MAX_ACTIVE_EXPECTED_ANSWER_FRAMES]
    history_frames = [frame for frame in frames if frame.status != "active"][
        -MAX_EXPECTED_ANSWER_HISTORY:
    ]
    return [*active_frames, *history_frames]


def _frame_is_expired(
    frame: ExpectedAnswerFrame,
    turns_seen: int,
    now: datetime | None,
) -> bool:
    if frame.max_customer_turns is not None and turns_seen > frame.max_customer_turns:
        return True
    expires_at = _parse_frame_datetime(frame.expires_at)
    if not expires_at:
        return False
    current = now or datetime.now(tz=expires_at.tzinfo or UTC)
    if expires_at.tzinfo and current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    if current.tzinfo and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=current.tzinfo)
    return current >= expires_at


def _parse_frame_datetime(value: str | datetime | None) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


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
