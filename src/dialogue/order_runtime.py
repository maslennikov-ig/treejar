from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from time import perf_counter
from typing import Any, TypedDict, cast

from langgraph.graph import StateGraph

from src.dialogue.order_guards import is_order_selection_blocked
from src.dialogue.order_state import (
    OrderDecision,
    OrderIntent,
    OrderRuntimeTrace,
    OrderState,
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
    return _with_phase_latency(
        {
            **graph_state,
            "state": OrderState.from_legacy_metadata(graph_state.get("metadata")),
        },
        phase="load_state",
        started_at=started_at,
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
        return _with_phase_latency(
            graph_state,
            phase="apply_reducer",
            started_at=started_at,
        )
    return _with_phase_latency(
        {
            **graph_state,
            "state": state.model_copy(update={"lines": intent.lines}, deep=True),
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
    return trace.model_copy(
        update={
            "route": decision.route,
            "handled": decision.handled,
            "reason_codes": decision.reason_codes[:5],
            "source": "catalog_refs",
            "line_count": len(state.lines),
            "total_ms": _elapsed_ms(started_at),
        }
    )


_COMPILED_ORDER_GRAPH = _build_order_graph().compile()
