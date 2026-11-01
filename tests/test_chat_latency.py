from __future__ import annotations

import json
from collections.abc import Iterator

import pytest

from src.services.chat_latency import (
    CHAT_LATENCY_EVENT,
    ChatLatencyTrace,
    parse_chat_latency_line,
    summarize_chat_latency,
)


def _clock(values: list[float]) -> Iterator[float]:
    yield from values


def test_chat_latency_trace_emits_only_bounded_phase_metadata() -> None:
    values = _clock([10.0, 11.0, 13.0, 14.0, 17.0])
    trace = ChatLatencyTrace(clock=lambda: next(values))
    trace.set_queue_wait_ms(250.1239)

    llm_started = trace.start_phase()
    trace.finish_phase("llm", llm_started)
    trace.mark_text_delivered()

    payload = trace.snapshot(status="sent")

    assert payload == {
        "event": CHAT_LATENCY_EVENT,
        "schema_version": 1,
        "status": "sent",
        "latency_ms": {
            "llm": 2000.0,
            "queue_wait": 250.124,
            "to_text_delivery": 4000.0,
            "total": 7000.0,
        },
    }
    assert set(payload) == {"event", "schema_version", "status", "latency_ms"}
    assert "message" not in json.dumps(payload).casefold()
    assert "phone" not in json.dumps(payload).casefold()


def test_chat_latency_trace_rejects_unknown_phase() -> None:
    trace = ChatLatencyTrace()

    with pytest.raises(ValueError, match="Unsupported chat latency phase"):
        trace.finish_phase("customer_text", trace.start_phase())


def test_chat_latency_parser_and_summary_find_dominant_phase() -> None:
    lines = [
        'INFO noor_chat_latency {"event":"noor_chat_latency","schema_version":1,'
        '"status":"sent","latency_ms":{"queue_wait":3000,"pre_llm":40,'
        '"llm":12000,"model_tools":11000,"persist_response":20,"outbound_text":100,'
        '"summary_refresh_enqueue":500,"to_text_delivery":15160,"total":15660}}',
        'INFO noor_chat_latency {"event":"noor_chat_latency","schema_version":1,'
        '"status":"sent","latency_ms":{"queue_wait":3000,"pre_llm":60,'
        '"llm":18000,"model_tools":17000,"persist_response":25,"outbound_text":120,'
        '"summary_refresh_enqueue":450,"to_text_delivery":21205,"total":21655}}',
    ]

    samples = [parse_chat_latency_line(line) for line in lines]
    summary = summarize_chat_latency([sample for sample in samples if sample])

    assert summary["sample_count"] == 2
    assert summary["to_text_delivery_ms"] == {
        "p50": 18182.5,
        "p95": 20902.75,
        "max": 21205.0,
    }
    assert summary["dominant_phase"] == "model_tools"


@pytest.mark.parametrize(
    "line",
    [
        '{"event":"noor_chat_latency","schema_version":1,"status":"sent",'
        '"latency_ms":{"llm":10},"phone":"+971500000000"}',
        '{"event":"noor_chat_latency","schema_version":1,"status":"sent",'
        '"latency_ms":{"message_text":10}}',
    ],
)
def test_chat_latency_parser_rejects_payloads_with_unapproved_fields(line: str) -> None:
    assert parse_chat_latency_line(line) is None


def test_chat_latency_tracks_arq_queue_wait_without_skewing_dominant_phase() -> None:
    values = _clock([10.0, 11.0, 12.0, 13.0])
    trace = ChatLatencyTrace(clock=lambda: next(values))
    trace.set_queue_wait_ms(5200.0)
    trace.set_arq_queue_wait_ms(5185.4321)
    pre_started = trace.start_phase()
    trace.finish_phase("pre_llm", pre_started)

    payload = trace.snapshot(status="skipped")
    assert payload["latency_ms"]["queue_wait"] == 5200.0
    assert payload["latency_ms"]["arq_queue_wait"] == 5185.432
    assert payload["latency_ms"]["pre_llm"] == 1000.0

    summary = summarize_chat_latency([payload])
    assert summary["queue_wait_ms"] == {"p50": 5200.0, "p95": 5200.0, "max": 5200.0}
    assert summary["arq_queue_wait_ms"] == {
        "p50": 5185.432,
        "p95": 5185.432,
        "max": 5185.432,
    }
    assert summary["dominant_phase"] == "queue_wait"
    assert "arq_queue_wait" not in summary["phase_ms"]
