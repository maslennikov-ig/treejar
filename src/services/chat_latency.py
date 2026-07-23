"""Bounded, privacy-safe latency evidence for the inbound chat path."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

CHAT_LATENCY_EVENT = "noor_chat_latency"
CHAT_LATENCY_SCHEMA_VERSION = 1

_PHASES = frozenset(
    {
        "queue_wait",
        "pre_llm",
        "llm",
        "llm_context",
        "faq_rag",
        "behavior_rag",
        "model_tools",
        "persist_response",
        "outbound_text",
        "summary_refresh_enqueue",
        "deferred_media",
        "to_text_delivery",
        "total",
    }
)
_DERIVED_PHASES = frozenset({"to_text_delivery", "total"})
_DOMINANT_EXCLUDED_PHASES = frozenset({"llm", "to_text_delivery", "total"})
_STATUSES = frozenset(
    {
        "sent",
        "send_failed",
        "voice_fallback",
        "escalation_fallback",
        "manual_takeover",
        "skipped",
        "timeout",
        "error",
    }
)
_ROOT_FIELDS = frozenset({"event", "schema_version", "status", "latency_ms"})


def _milliseconds(seconds: float) -> float:
    return round(max(seconds * 1000.0, 0.0), 3)


@dataclass(slots=True)
class ChatLatencyTrace:
    """Collect timings without accepting identifiers, text, or arbitrary labels."""

    clock: Callable[[], float] = field(default=perf_counter, repr=False)
    _started_at: float = field(init=False, repr=False)
    _phase_ms: dict[str, float] = field(default_factory=dict, init=False, repr=False)
    _queue_wait_ms: float | None = field(default=None, init=False, repr=False)
    _text_delivered_at: float | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    def start_phase(self) -> float:
        return self.clock()

    def finish_phase(self, phase: str, started_at: float) -> None:
        if phase not in _PHASES or phase in _DERIVED_PHASES:
            raise ValueError(f"Unsupported chat latency phase: {phase}")
        elapsed_ms = _milliseconds(self.clock() - started_at)
        self._phase_ms[phase] = round(
            self._phase_ms.get(phase, 0.0) + elapsed_ms,
            3,
        )

    def set_queue_wait_ms(self, value: float) -> None:
        if not math.isfinite(value) or value < 0:
            raise ValueError("queue wait must be a finite non-negative number")
        self._queue_wait_ms = round(value, 3)

    def mark_text_delivered(self) -> None:
        if self._text_delivered_at is None:
            self._text_delivered_at = self.clock()

    def snapshot(self, *, status: str) -> dict[str, Any]:
        safe_status = status if status in _STATUSES else "error"
        finished_at = self.clock()
        latency_ms = dict(self._phase_ms)
        if self._queue_wait_ms is not None:
            latency_ms["queue_wait"] = self._queue_wait_ms
        if self._text_delivered_at is not None:
            latency_ms["to_text_delivery"] = _milliseconds(
                self._text_delivered_at - self._started_at
            )
        latency_ms["total"] = _milliseconds(finished_at - self._started_at)
        return {
            "event": CHAT_LATENCY_EVENT,
            "schema_version": CHAT_LATENCY_SCHEMA_VERSION,
            "status": safe_status,
            "latency_ms": dict(sorted(latency_ms.items())),
        }


def format_chat_latency(trace: ChatLatencyTrace, *, status: str) -> str:
    """Return a stable JSON payload suitable for a single structured log line."""
    return json.dumps(
        trace.snapshot(status=status),
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_chat_latency_line(line: str) -> dict[str, Any] | None:
    """Parse only the allowlisted latency schema from an application log line."""
    payload_start = line.find("{")
    if payload_start < 0:
        return None
    try:
        payload = json.loads(line[payload_start:])
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(payload, dict) or set(payload) != _ROOT_FIELDS:
        return None
    if (
        payload.get("event") != CHAT_LATENCY_EVENT
        or payload.get("schema_version") != CHAT_LATENCY_SCHEMA_VERSION
        or payload.get("status") not in _STATUSES
    ):
        return None

    timings = payload.get("latency_ms")
    if not isinstance(timings, dict) or not timings:
        return None
    normalized: dict[str, float] = {}
    for phase, value in timings.items():
        if phase not in _PHASES:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        numeric_value = float(value)
        if not math.isfinite(numeric_value) or numeric_value < 0:
            return None
        normalized[phase] = round(numeric_value, 3)

    return {
        "event": CHAT_LATENCY_EVENT,
        "schema_version": CHAT_LATENCY_SCHEMA_VERSION,
        "status": payload["status"],
        "latency_ms": normalized,
    }


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = percentile * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _metric(values: list[float]) -> dict[str, float]:
    return {
        "p50": round(_percentile(values, 0.5), 3),
        "p95": round(_percentile(values, 0.95), 3),
        "max": round(max(values), 3),
    }


def summarize_chat_latency(samples: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate already-validated, PII-free latency records."""
    valid_samples = [
        parsed
        for sample in samples
        if (parsed := parse_chat_latency_line(json.dumps(dict(sample)))) is not None
    ]
    if not valid_samples:
        return {
            "sample_count": 0,
            "status_counts": {},
            "dominant_phase": None,
        }

    status_counts: dict[str, int] = {}
    phase_values: dict[str, list[float]] = {}
    for sample in valid_samples:
        status = str(sample["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
        timings = sample["latency_ms"]
        for phase, value in timings.items():
            phase_values.setdefault(phase, []).append(float(value))

    candidate_phases = {
        phase: values
        for phase, values in phase_values.items()
        if phase not in _DOMINANT_EXCLUDED_PHASES
    }
    dominant_phase = (
        max(
            candidate_phases,
            key=lambda phase: (
                sum(candidate_phases[phase]) / len(candidate_phases[phase])
            ),
        )
        if candidate_phases
        else None
    )

    summary: dict[str, Any] = {
        "sample_count": len(valid_samples),
        "status_counts": dict(sorted(status_counts.items())),
        "dominant_phase": dominant_phase,
    }
    for phase in ("queue_wait", "to_text_delivery", "total"):
        if values := phase_values.get(phase):
            summary[f"{phase}_ms"] = _metric(values)
    summary["phase_ms"] = {
        phase: _metric(values) for phase, values in sorted(candidate_phases.items())
    }
    return summary
