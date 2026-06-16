from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypedDict, cast

from langgraph.graph import StateGraph

from src.dialogue.order_guards import is_order_selection_blocked
from src.dialogue.order_state import (
    OrderDecision,
    OrderIntent,
    OrderLine,
    OrderRuntimeTrace,
    OrderState,
    PendingQuestionFrame,
    PendingQuestionSourceRef,
    age_pending_question_frame,
    extract_order_intent_from_text,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrderRuntimeResult:
    state: OrderState
    intent: OrderIntent
    decision: OrderDecision
    trace: OrderRuntimeTrace


class _OrderGraphState(TypedDict, total=False):
    text: str
    metadata: Mapping[str, Any]
    state: OrderState
    intent: OrderIntent
    decision: OrderDecision
    trace: Mapping[str, Any]


def run_order_runtime(
    *,
    text: str,
    metadata: Mapping[str, Any] | None,
) -> OrderRuntimeResult:
    started_at = perf_counter()
    graph_input: _OrderGraphState = {
        "text": text,
        "metadata": metadata or {},
        "trace": OrderRuntimeTrace().model_dump(),
    }
    try:
        output = cast("_OrderGraphState", _COMPILED_ORDER_GRAPH.invoke(graph_input))
    except Exception:  # noqa: BLE001 - order runtime must fail closed to legacy.
        logger.warning(
            "Order runtime failed; falling back to legacy path", exc_info=True
        )
        return OrderRuntimeResult(
            state=OrderState.from_legacy_metadata(metadata),
            intent=OrderIntent(source_text=text),
            decision=OrderDecision(
                route="legacy_fallback",
                handled=False,
                reason_codes=["runtime_error"],
            ),
            trace=OrderRuntimeTrace(
                route="legacy_fallback",
                handled=False,
                reason_codes=["runtime_error"],
                source="runtime_error",
                total_ms=_elapsed_ms(started_at),
            ),
        )
    trace = _finalize_trace(output, started_at=started_at)
    return OrderRuntimeResult(
        state=output["state"],
        intent=output["intent"],
        decision=output["decision"],
        trace=trace,
    )


def _build_order_graph() -> Any:
    graph: Any = StateGraph(_OrderGraphState)
    graph.add_node("load_state", _load_state_node)
    graph.add_node("extract_intent", _extract_intent_node)
    graph.add_node("apply_reducer", _apply_reducer_node)
    graph.add_node("decide", _decide_node)
    graph.set_entry_point("load_state")
    graph.add_edge("load_state", "extract_intent")
    graph.add_edge("extract_intent", "apply_reducer")
    graph.add_edge("apply_reducer", "decide")
    graph.set_finish_point("decide")
    return graph


def _load_state_node(graph_state: _OrderGraphState) -> _OrderGraphState:
    started_at = perf_counter()
    metadata = graph_state.get("metadata")
    trace = _trace_from_value(graph_state.get("trace"))
    return _with_phase_latency(
        {
            **graph_state,
            "state": OrderState.from_legacy_metadata(metadata),
            "trace": trace.model_copy(
                update={"legacy_migration_read": _has_legacy_order_metadata(metadata)}
            ).model_dump(),
        },
        phase="load_state",
        started_at=started_at,
    )


def _has_legacy_order_metadata(metadata: Mapping[str, Any] | None) -> bool:
    if not isinstance(metadata, Mapping):
        return False
    return any(
        isinstance(metadata.get(key), Mapping)
        for key in ("pending_quote_selection", "quote_customer_details")
    )


def _extract_intent_node(graph_state: _OrderGraphState) -> _OrderGraphState:
    started_at = perf_counter()
    return _with_phase_latency(
        {
            **graph_state,
            "intent": extract_order_intent_from_text(graph_state.get("text", "")),
        },
        phase="extract_intent",
        started_at=started_at,
    )


def _apply_reducer_node(graph_state: _OrderGraphState) -> _OrderGraphState:
    started_at = perf_counter()
    state = graph_state["state"]
    intent = graph_state["intent"]
    if not intent.lines:
        quantity = _extract_bare_quantity_reply(graph_state.get("text", ""))
        if quantity is not None and state.pending_question_frame is not None:
            answered_state = _answer_pending_quantity_frame(
                state,
                state.pending_question_frame,
                quantity,
            )
            if answered_state is not None:
                return _with_phase_latency(
                    {
                        **graph_state,
                        "state": answered_state,
                    },
                    phase="apply_reducer",
                    started_at=started_at,
                )
        if state.pending_question_frame is not None:
            return _with_phase_latency(
                {
                    **graph_state,
                    "state": state.model_copy(
                        update={
                            "pending_question_frame": age_pending_question_frame(
                                state.pending_question_frame
                            )
                        },
                        deep=True,
                    ),
                },
                phase="apply_reducer",
                started_at=started_at,
            )
        return _with_phase_latency(
            graph_state,
            phase="apply_reducer",
            started_at=started_at,
        )
    pending_question_frame = state.pending_question_frame
    if any(line.status == "needs_quantity" for line in intent.lines):
        pending_question_frame = _quantity_frame_from_lines(intent.lines)
    return _with_phase_latency(
        {
            **graph_state,
            "state": state.model_copy(
                update={
                    "lines": intent.lines,
                    "pending_question_frame": pending_question_frame,
                },
                deep=True,
            ),
        },
        phase="apply_reducer",
        started_at=started_at,
    )


def _decide_node(graph_state: _OrderGraphState) -> _OrderGraphState:
    started_at = perf_counter()
    state = graph_state["state"]
    if is_order_selection_blocked(graph_state.get("text", "")):
        decision = OrderDecision(
            route="legacy_fallback",
            handled=False,
            reason_codes=["selection_blocker"],
        )
    elif any(line.status == "needs_quantity" for line in state.lines):
        decision = OrderDecision(
            route="quantity_clarification",
            handled=True,
            reason_codes=["missing_quantities"],
        )
    elif (
        state.pending_question_frame is not None
        and state.pending_question_frame.status == "answered"
        and state.lines
        and all(line.quantity and line.quantity > 0 for line in state.lines)
    ):
        decision = OrderDecision(
            route="product_selection",
            handled=True,
            reason_codes=["quantity_frame_answered"],
        )
    elif state.lines and all(
        line.quantity and line.quantity > 0 for line in state.lines
    ):
        decision = OrderDecision(
            route="product_selection",
            handled=True,
            reason_codes=["complete_order_lines"],
        )
    else:
        decision = OrderDecision(route="legacy_fallback", handled=False)
    return _with_phase_latency(
        {**graph_state, "decision": decision},
        phase="decide",
        started_at=started_at,
    )


def _elapsed_ms(started_at: float) -> float:
    return round(max((perf_counter() - started_at) * 1000, 0.0), 3)


def _extract_bare_quantity_reply(text: str) -> int | None:
    stripped = " ".join(text.strip(" \t\r\n.,;:!?").split())
    if not stripped:
        return None
    if re.fullmatch(r"\d{1,4}", stripped):
        quantity = int(stripped)
        return quantity if quantity > 0 else None
    word_quantities = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    return word_quantities.get(stripped.casefold())


def _quantity_frame_from_lines(lines: list[OrderLine]) -> PendingQuestionFrame | None:
    refs = [
        PendingQuestionSourceRef(
            catalog_ref=line.catalog_ref,
            source_text=line.source_text or line.catalog_ref,
            sku=line.sku or line.catalog_ref,
            ordinal=index,
        )
        for index, line in enumerate(lines, start=1)
        if line.status == "needs_quantity"
    ]
    if not refs:
        return None
    frame_id = "quantity:" + ":".join(ref.catalog_ref for ref in refs)
    return PendingQuestionFrame(
        frame_id=frame_id,
        question_kind="quantity",
        status="active",
        prompt_key="ask_quantity_for_sku",
        max_customer_turns=2,
        turns_seen=0,
        source_refs=refs,
        order_lines_snapshot=lines,
    )


def _answer_pending_quantity_frame(
    state: OrderState,
    frame: PendingQuestionFrame,
    quantity: int,
) -> OrderState | None:
    if quantity <= 0 or not frame.is_active:
        return None
    lines = _answer_pending_quantity_lines(frame, quantity)
    answered_frame = frame.model_copy(update={"status": "answered"}, deep=True)
    return state.model_copy(
        update={
            "lines": lines,
            "pending_question_frame": answered_frame,
        },
        deep=True,
    )


def _answer_pending_quantity_lines(
    frame: PendingQuestionFrame,
    quantity: int,
) -> list[OrderLine]:
    if frame.order_lines_snapshot:
        return [
            line.model_copy(
                update={
                    "quantity": quantity,
                    "status": "resolved",
                },
                deep=True,
            )
            if line.status == "needs_quantity"
            else line
            for line in frame.order_lines_snapshot
        ]
    return [
        OrderLine(
            catalog_ref=ref.catalog_ref,
            quantity=quantity,
            source_text=ref.source_text,
            sku=ref.sku or ref.catalog_ref,
            status="resolved",
        )
        for ref in frame.source_refs
    ]


def _trace_from_value(value: Any) -> OrderRuntimeTrace:
    if isinstance(value, OrderRuntimeTrace):
        return value
    if isinstance(value, Mapping):
        return OrderRuntimeTrace.model_validate(value)
    return OrderRuntimeTrace()


def _with_phase_latency(
    graph_state: _OrderGraphState,
    *,
    phase: str,
    started_at: float,
) -> _OrderGraphState:
    trace = _trace_from_value(graph_state.get("trace"))
    phase_ms = dict(trace.phase_ms)
    phase_ms[phase] = _elapsed_ms(started_at)
    return {
        **graph_state,
        "trace": trace.model_copy(update={"phase_ms": phase_ms}).model_dump(),
    }


def _finalize_trace(
    graph_state: _OrderGraphState,
    *,
    started_at: float,
) -> OrderRuntimeTrace:
    state = graph_state["state"]
    decision = graph_state["decision"]
    trace = _trace_from_value(graph_state.get("trace"))
    frame = state.pending_question_frame
    return trace.model_copy(
        update={
            "route": decision.route,
            "handled": decision.handled,
            "reason_codes": decision.reason_codes[:5],
            "source": "catalog_refs",
            "frame_id": frame.frame_id if frame is not None else None,
            "frame_status": frame.status if frame is not None else None,
            "resolved_line_count": sum(
                1 for line in state.lines if line.quantity and line.quantity > 0
            ),
            "unresolved_line_count": sum(
                1 for line in state.lines if line.status == "needs_quantity"
            ),
            "line_count": len(state.lines),
            "total_ms": _elapsed_ms(started_at),
        }
    )


_COMPILED_ORDER_GRAPH = _build_order_graph().compile()
