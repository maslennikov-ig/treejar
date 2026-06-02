from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import import_module
from inspect import signature
from typing import Any, Literal, TypedDict, cast

from langgraph.graph import StateGraph

from src.dialogue.catalog_refs import extract_catalog_references
from src.dialogue.reducer import (
    append_trace_bounded,
    apply_extracted_details,
    build_trace,
    expire_expected_answer_frames,
    mark_frame_fulfilled,
    mark_quote_sent,
)
from src.dialogue.state import DialogueDecision, DialogueState
from src.models.conversation import Conversation

DialogueKernelMode = Literal["legacy", "shadow", "enforce"]
SUPPORTED_FLOWS = frozenset(
    {"name_gate", "product_selection", "quote_details", "post_quotation_hold"}
)
TRACE_LIMIT = 20
EXPECTED_ANSWER_TRACE_TEXT_LIMIT = 240
EXPECTED_ANSWER_TRACE_ITEM_LIMIT = 12


@dataclass(frozen=True)
class DialogueKernelResult:
    decision: DialogueDecision
    state: DialogueState
    should_use_kernel: bool


def expected_answer_match_payload(
    result: DialogueKernelResult | None,
    *,
    route: str | None = None,
    confidence: str | None = None,
    require_usable_kernel: bool = True,
) -> dict[str, Any] | None:
    if result is None:
        return None
    if require_usable_kernel and not (
        result.should_use_kernel and result.decision.side_effects_allowed
    ):
        return None
    expected_answer = result.decision.metadata.get("expected_answer")
    if not isinstance(expected_answer, Mapping):
        return None
    match = expected_answer.get("match")
    if not isinstance(match, Mapping):
        return None
    payload = dict(match)
    if route is not None and payload.get("route") != route:
        return None
    if confidence is not None and payload.get("confidence") != confidence:
        return None
    return payload


class _GraphInput(TypedDict):
    state: DialogueState
    text: str
    recent_history: list[str]
    is_first_turn: bool


class _GraphOutput(_GraphInput, total=False):
    decision: DialogueDecision
    after_state: DialogueState
    expected_answer_match: dict[str, Any]


def parse_enforced_flows(
    value: str | tuple[str, ...] | list[str] | None,
) -> tuple[str, ...]:
    if value is None:
        return ()
    raw_items = value.split(",") if isinstance(value, str) else value
    flows: list[str] = []
    for item in raw_items:
        flow = str(item).strip().casefold()
        if flow in SUPPORTED_FLOWS and flow not in flows:
            flows.append(flow)
    return tuple(flows)


async def run_dialogue_kernel(
    *,
    conversation: Conversation,
    text: str,
    recent_history: list[str],
    is_first_turn: bool,
    mode: DialogueKernelMode | str,
    enforced_flows: tuple[str, ...] | list[str] | str | None,
    trace_enabled: bool,
) -> DialogueKernelResult:
    normalized_mode = _normalize_mode(mode)
    before_state = DialogueState.from_conversation(conversation)
    if normalized_mode == "legacy":
        return DialogueKernelResult(
            decision=DialogueDecision(
                action="fallback_legacy",
                flow="legacy_fallback",
                handled=False,
            ),
            state=before_state,
            should_use_kernel=False,
        )

    graph_input: _GraphOutput = {
        "state": before_state,
        "text": text,
        "recent_history": list(recent_history),
        "is_first_turn": is_first_turn,
    }
    graph_output = cast("_GraphOutput", await _COMPILED_GRAPH.ainvoke(graph_input))
    decision = graph_output["decision"]
    after_state = graph_output.get("after_state") or before_state
    allowed_flows = set(parse_enforced_flows(enforced_flows))
    should_use_kernel = (
        normalized_mode == "enforce"
        and decision.flow in allowed_flows
        and decision.handled
    )
    side_effects_allowed = should_use_kernel
    decision = decision.model_copy(
        update={"side_effects_allowed": side_effects_allowed},
        deep=True,
    )

    if trace_enabled:
        trace = build_trace(
            mode=normalized_mode,
            decision=decision,
            before_state=before_state,
            after_state=after_state,
            kernel_route=_trace_kernel_route(decision),
        )
        traced_state = append_trace_bounded(after_state, trace, limit=TRACE_LIMIT)
        after_state = traced_state
    conversation.metadata_ = after_state.to_metadata(conversation.metadata_)

    return DialogueKernelResult(
        decision=decision,
        state=after_state,
        should_use_kernel=should_use_kernel,
    )


def record_legacy_route(
    conversation: Conversation,
    result: DialogueKernelResult | None,
    *,
    legacy_route: str,
) -> None:
    if result is None:
        return
    state = DialogueState.load(conversation.metadata_)
    if not state.trace_history:
        return
    traces = list(state.trace_history)
    latest = traces[-1].model_copy(
        update={
            "legacy_route": legacy_route,
            "mismatch_reason": _mismatch_reason(
                legacy_route=legacy_route,
                kernel_route=traces[-1].kernel_route,
            ),
        },
        deep=True,
    )
    state = state.model_copy(update={"trace_history": [*traces[:-1], latest]})
    conversation.metadata_ = state.to_metadata(conversation.metadata_)


def _normalize_mode(mode: str) -> DialogueKernelMode:
    normalized = str(mode or "").strip().casefold()
    if normalized in {"shadow", "enforce"}:
        return normalized  # type: ignore[return-value]
    return "legacy"


def _build_graph() -> StateGraph[_GraphOutput]:
    graph: StateGraph[_GraphOutput] = StateGraph(_GraphOutput)
    graph.add_node("expire_frames", _expire_frames_node)
    graph.add_node("match_expected_answer", _match_expected_answer_node)
    graph.add_node("decide", _decide_node)
    graph.set_entry_point("expire_frames")
    graph.add_edge("expire_frames", "match_expected_answer")
    graph.add_edge("match_expected_answer", "decide")
    graph.set_finish_point("decide")
    return graph


def _expire_frames_node(state: _GraphInput) -> _GraphOutput:
    return {
        "state": expire_expected_answer_frames(state["state"]),
        "text": state["text"],
        "recent_history": state["recent_history"],
        "is_first_turn": state["is_first_turn"],
    }


def _match_expected_answer_node(state: _GraphInput) -> _GraphOutput:
    return {
        "state": state["state"],
        "text": state["text"],
        "recent_history": state["recent_history"],
        "is_first_turn": state["is_first_turn"],
        "expected_answer_match": _normalize_expected_answer_match(
            _match_expected_answer(
                dialogue_state=state["state"],
                text=state["text"],
                recent_history=state["recent_history"],
            )
        ),
    }


def _decide_node(state: _GraphOutput) -> _GraphOutput:
    dialogue_state = state["state"]
    text = state["text"]
    expected_answer_decision = _expected_answer_decision(
        dialogue_state,
        state.get("expected_answer_match"),
    )
    if expected_answer_decision:
        after_state = dialogue_state
        expected_answer = expected_answer_decision.metadata.get("expected_answer")
        raw_match = (
            expected_answer.get("match") if isinstance(expected_answer, dict) else None
        )
        match_payload: dict[str, Any] = raw_match if isinstance(raw_match, dict) else {}
        frame_id = match_payload.get("frame_id")
        raw_filled_slots = match_payload.get("filled_slots")
        filled_slots = raw_filled_slots if isinstance(raw_filled_slots, dict) else None
        if isinstance(frame_id, str) and frame_id and match_payload.get("fulfilled"):
            after_state = mark_frame_fulfilled(
                dialogue_state,
                frame_id,
                filled_slots=filled_slots,
            )
        return {
            **state,
            "decision": expected_answer_decision,
            "after_state": after_state,
        }

    if (
        dialogue_state.active_flow == "name_gate"
        and not dialogue_state.slots.customer_name
        and _looks_like_bare_name(text)
    ):
        after_state = apply_extracted_details(
            dialogue_state,
            {"customer_name": " ".join(text.strip().split())},
        )
        return {
            **state,
            "decision": DialogueDecision(
                action="delegate_name_gate_resume_to_legacy",
                flow="name_gate",
                handled=False,
                metadata={"customer_name": after_state.slots.customer_name},
            ),
            "after_state": after_state,
        }

    if state["is_first_turn"] and not dialogue_state.slots.customer_name:
        after_state = dialogue_state.model_copy(update={"active_flow": "name_gate"})
        return {
            **state,
            "decision": DialogueDecision(
                action="ask_name",
                flow="name_gate",
                response_text="Hello",
                handled=True,
            ),
            "after_state": after_state,
        }

    if _is_post_quotation_context(dialogue_state, state["recent_history"]):
        after_state = mark_quote_sent(
            dialogue_state,
            post_quotation_status="awaiting_customer_decision",
        ).model_copy(update={"active_flow": "post_quotation_hold"})
        return {
            **state,
            "decision": DialogueDecision(
                action="hold_post_quotation",
                flow="post_quotation_hold",
                response_text=(
                    "Thank you, I have noted your reply about the quotation. "
                    "I will keep the quotation context and avoid restarting the "
                    "conversation."
                ),
                handled=True,
            ),
            "after_state": after_state,
        }

    if _is_quote_details_context(dialogue_state, state["recent_history"]):
        details = _extract_quote_details(text)
        after_state = apply_extracted_details(dialogue_state, details)
        missing = _missing_quote_details(after_state)
        if details or missing:
            return {
                **state,
                "decision": DialogueDecision(
                    action="collect_quote_details",
                    flow="quote_details",
                    response_text=_quote_details_response(missing),
                    handled=True,
                    metadata={
                        "quote_customer_details": details,
                        "missing_required": missing,
                    },
                ),
                "after_state": after_state.model_copy(
                    update={"active_flow": "quote_details"},
                    deep=True,
                ),
            }

    refs = extract_catalog_references(text)
    if refs:
        refs_payload = [
            {
                "raw": ref.raw,
                "normalized": ref.normalized,
                "quantity": ref.quantity,
            }
            for ref in refs
        ]
        after_state = dialogue_state.model_copy(
            update={"active_flow": "product_selection"}
        )
        after_state = after_state.model_copy(
            update={
                "slots": after_state.slots.model_copy(
                    update={
                        "pending_product_refs": [
                            ref.normalized for ref in refs if ref.normalized
                        ]
                    },
                    deep=True,
                )
            },
            deep=True,
        )
        if any(ref.quantity is not None for ref in refs):
            after_state = after_state.model_copy(
                update={
                    "slots": after_state.slots.model_copy(
                        update={
                            "selected_items": [
                                {
                                    "sku": ref.normalized,
                                    "quantity": ref.quantity,
                                }
                                for ref in refs
                                if ref.quantity is not None
                            ]
                        },
                        deep=True,
                    )
                },
                deep=True,
            )
            return {
                **state,
                "decision": DialogueDecision(
                    action="delegate_quantity_selection_to_legacy",
                    flow="product_selection",
                    handled=False,
                    metadata={"refs": refs_payload},
                ),
                "after_state": after_state,
            }
        return {
            **state,
            "decision": DialogueDecision(
                action="clarify_product_selection",
                flow="product_selection",
                response_text=(
                    "I have the product reference. Please confirm the quantity "
                    "for each item so I can continue accurately."
                ),
                handled=True,
                metadata={"refs": refs_payload},
            ),
            "after_state": after_state,
        }

    return {
        **state,
        "decision": DialogueDecision(
            action="fallback_legacy",
            flow="legacy_fallback",
            handled=False,
        ),
        "after_state": dialogue_state,
    }


def _is_post_quotation_context(
    state: DialogueState,
    recent_history: list[str],
) -> bool:
    if state.slots.quote_sent or state.active_flow == "post_quotation_hold":
        return True
    last_assistant = next(
        (
            item.removeprefix("assistant: ").casefold()
            for item in reversed(recent_history)
            if item.startswith("assistant: ")
        ),
        "",
    )
    return "quotation" in last_assistant and (
        "sent" in last_assistant
        or "pdf" in last_assistant
        or "shared" in last_assistant
        or "proceed" in last_assistant
    )


def _is_quote_details_context(
    state: DialogueState,
    recent_history: list[str],
) -> bool:
    if state.slots.selected_items:
        return True
    if state.active_flow == "quote_details" and _has_active_flow_frame(
        state, "quote_details"
    ):
        return True
    last_assistant = next(
        (
            item.removeprefix("assistant: ").casefold()
            for item in reversed(recent_history)
            if item.startswith("assistant: ")
        ),
        "",
    )
    return "quotation" in last_assistant and (
        "company" in last_assistant or "address" in last_assistant
    )


def _has_active_flow_frame(state: DialogueState, flow: str) -> bool:
    return any(
        frame.status == "active" and frame.flow == flow
        for frame in state.expected_answer_frames
    )


def _extract_quote_details(text: str) -> dict[str, str]:
    stripped = " ".join(text.strip(" \t\r\n.;:!?").split())
    if not stripped or len(stripped) > 220 or "?" in stripped:
        return {}

    details: dict[str, str] = {}
    normalized = stripped.casefold()
    if re.search(
        r"\b(?:individual|personal|private customer|for myself)\b", normalized
    ):
        details["customer_type"] = "individual"

    parts = [
        part.strip(" \t\r\n,.;:-")
        for part in re.split(r"[,;\n]+", stripped, maxsplit=1)
        if part.strip(" \t\r\n,.;:-")
    ]
    if len(parts) >= 2 and _looks_like_bare_name(parts[0]):
        details["customer_name"] = parts[0]
        details["delivery_address"] = parts[1]
    return details


def _missing_quote_details(state: DialogueState) -> list[str]:
    missing: list[str] = []
    if not state.slots.company and state.slots.customer_type != "individual":
        missing.append("company_or_individual")
    if not _is_specific_delivery_address(state.slots.delivery_address):
        missing.append("specific_delivery_address")
    return missing


def _quote_details_response(missing: list[str]) -> str:
    if missing == ["company_or_individual"]:
        return "Please confirm the company name, or tell me if the quotation should be for you as an individual."
    if missing == ["specific_delivery_address"]:
        return "Please share the specific delivery address for the quotation."
    if missing:
        return "Please share the company name or confirm individual, and the specific delivery address for the quotation."
    return "Thank you, I have the quotation details and will keep the current quote context."


def _is_specific_delivery_address(value: str | None) -> bool:
    if not value:
        return False
    normalized = " ".join(value.casefold().split())
    if normalized in {"dubai", "dubay", "uae", "дубай"}:
        return False
    return bool(re.search(r"\d", value)) or len(normalized.split()) >= 2


def _looks_like_bare_name(text: str) -> bool:
    stripped = " ".join(text.strip(" \t\r\n,.;:!?").split())
    if not stripped:
        return False
    words = stripped.split()
    if len(words) > 4:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    normalized = stripped.casefold()
    if normalized in {"yes", "ok", "okay", "no", "thanks", "thank you"}:
        return False
    return all(any(char.isalpha() for char in word) for word in words)


def _mismatch_reason(*, legacy_route: str, kernel_route: str | None) -> str | None:
    if not kernel_route:
        return None
    return None if kernel_route in legacy_route else "route_diff"


def _match_expected_answer(
    *,
    dialogue_state: DialogueState,
    text: str,
    recent_history: list[str],
) -> Any:
    try:
        matcher_module = import_module("src.dialogue.expected_answers")
    except ImportError:
        return {"matched": False}
    match_expected_answer = getattr(matcher_module, "match_expected_answer", None)
    if not callable(match_expected_answer):
        return {"matched": False}

    try:
        parameters = signature(match_expected_answer).parameters
    except (TypeError, ValueError):
        return match_expected_answer(dialogue_state, text)

    kwargs: dict[str, Any] = {}
    if "dialogue_state" in parameters:
        kwargs["dialogue_state"] = dialogue_state
    elif "state" in parameters:
        kwargs["state"] = dialogue_state
    else:
        return match_expected_answer(dialogue_state, text)
    if "text" in parameters:
        kwargs["text"] = text
    if "recent_history" in parameters:
        kwargs["recent_history"] = recent_history
    return match_expected_answer(**kwargs)


def _normalize_expected_answer_match(match: Any) -> dict[str, Any]:
    if match is None:
        return {"matched": False}
    if isinstance(match, Mapping):
        payload = dict(match)
    elif hasattr(match, "model_dump"):
        payload = cast("dict[str, Any]", match.model_dump())
    else:
        payload = {
            key: getattr(match, key)
            for key in (
                "matched",
                "frame_id",
                "confidence",
                "filled_slots",
                "route",
                "interruption",
                "ambiguous_frame_ids",
                "blocker",
                "flow",
            )
            if hasattr(match, key)
        }
    normalized = {str(key): value for key, value in payload.items()}
    normalized["matched"] = bool(normalized.get("matched"))
    normalized.setdefault("confidence", "none")
    normalized.setdefault("route", "legacy_fallback")
    normalized.setdefault("interruption", False)
    normalized.setdefault("blocker", None)
    normalized["fulfilled"] = bool(normalized.get("fulfilled"))
    if not isinstance(normalized.get("filled_slots"), dict):
        normalized["filled_slots"] = {}
    if not isinstance(normalized.get("missing_required_slots"), list):
        normalized["missing_required_slots"] = []
    if not isinstance(normalized.get("ambiguous_frame_ids"), list):
        normalized["ambiguous_frame_ids"] = []
    return normalized


def _expected_answer_decision(
    state: DialogueState,
    match: dict[str, Any] | None,
) -> DialogueDecision | None:
    if _is_expected_answer_clarification(match):
        assert match is not None
        flow = state.active_flow or "product_selection"
        metadata = {
            "expected_answer": {
                "match": _bounded_expected_answer_payload(
                    {
                        "matched": False,
                        "frame_id": None,
                        "confidence": match.get("confidence"),
                        "route": "expected_answer_clarify",
                        "filled_slots": {},
                        "fulfilled": False,
                        "missing_required_slots": [],
                        "interruption": False,
                        "blocker": None,
                        "ambiguous_frame_ids": match.get("ambiguous_frame_ids", []),
                    }
                ),
                "proposal": {
                    "action": "expected_answer_clarify",
                    "flow": flow,
                    "handled": True,
                },
            }
        }
        return DialogueDecision(
            action="expected_answer_clarify",
            flow=flow,
            response_text=(
                "I have a couple of pending questions. Please clarify which one "
                "you are answering."
            ),
            handled=True,
            metadata=metadata,
        )
    if not _is_high_confidence_expected_answer(match):
        return None
    assert match is not None
    flow = _expected_answer_flow(state, match)
    metadata = {
        "expected_answer": {
            "match": _bounded_expected_answer_payload(
                {
                    "matched": match["matched"],
                    "frame_id": match.get("frame_id"),
                    "confidence": match.get("confidence"),
                    "route": match.get("route"),
                    "filled_slots": match.get("filled_slots", {}),
                    "fulfilled": match.get("fulfilled", False),
                    "missing_required_slots": match.get("missing_required_slots", []),
                    "interruption": match.get("interruption", False),
                    "blocker": match.get("blocker"),
                    "ambiguous_frame_ids": match.get("ambiguous_frame_ids", []),
                }
            ),
            "proposal": {
                "action": match["route"],
                "flow": flow,
                "handled": True,
            },
        }
    }
    return DialogueDecision(
        action=match["route"],
        flow=flow,
        response_text=(
            "Thank you, I noted your preference and will continue with matching "
            "products."
        ),
        handled=True,
        metadata=metadata,
    )


def _is_high_confidence_expected_answer(match: dict[str, Any] | None) -> bool:
    if not match or not match.get("matched"):
        return False
    return (
        match.get("route") == "product_preference_answer"
        and match.get("confidence") == "high"
        and match.get("fulfilled") is True
        and not match.get("missing_required_slots")
        and not match.get("interruption")
        and not match.get("blocker")
        and bool(match.get("frame_id"))
    )


def _is_expected_answer_clarification(match: dict[str, Any] | None) -> bool:
    if not match:
        return False
    return (
        match.get("route") == "expected_answer_clarify"
        and match.get("confidence") == "ambiguous"
        and bool(match.get("ambiguous_frame_ids"))
        and not match.get("blocker")
    )


def _expected_answer_flow(state: DialogueState, match: dict[str, Any]) -> str:
    flow = match.get("flow")
    if isinstance(flow, str) and flow.strip():
        return flow.strip()
    frame_id = match.get("frame_id")
    for frame in state.expected_answer_frames:
        if frame.frame_id == frame_id and frame.flow:
            return frame.flow
    if match.get("route") == "product_preference_answer":
        return "product_selection"
    return state.active_flow or "legacy_fallback"


def _bounded_expected_answer_payload(value: Any) -> Any:
    if isinstance(value, str):
        if len(value) <= EXPECTED_ANSWER_TRACE_TEXT_LIMIT:
            return value
        return f"{value[: EXPECTED_ANSWER_TRACE_TEXT_LIMIT - 3]}..."
    if isinstance(value, list):
        return [
            _bounded_expected_answer_payload(item)
            for item in value[:EXPECTED_ANSWER_TRACE_ITEM_LIMIT]
        ]
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= EXPECTED_ANSWER_TRACE_ITEM_LIMIT:
                break
            bounded[str(key)] = _bounded_expected_answer_payload(item)
        return bounded
    return value


def _trace_kernel_route(decision: DialogueDecision) -> str:
    expected_answer = decision.metadata.get("expected_answer")
    if isinstance(expected_answer, dict):
        match = expected_answer.get("match")
        if isinstance(match, dict):
            route = match.get("route")
            if isinstance(route, str) and route:
                return route
    return decision.flow


_COMPILED_GRAPH: Any = _build_graph().compile()
