from __future__ import annotations

from src.dialogue.order_runtime import run_order_runtime
from src.dialogue.order_state import pending_question_frame_to_metadata


def test_order_runtime_selects_product_route_for_complete_order_lines() -> None:
    result = run_order_runtime(
        text="I need 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs",
        metadata={},
    )

    assert result.decision.route == "product_selection"
    assert result.decision.handled is True
    assert [
        (line.catalog_ref, line.quantity, line.sku) for line in result.state.lines
    ] == [
        ("SKYLAND NOVO 2400", 2, "SKYLAND NOVO 2400"),
        ("CH-616", 4, "CH-616"),
    ]
    assert [(line.catalog_ref, line.source_text) for line in result.state.lines] == [
        ("SKYLAND NOVO 2400", "SKYLAND NOVO 2400 Meeting Table"),
        ("CH-616", "CH 616 chairs"),
    ]


def test_order_runtime_ignores_sku_like_email_local_part() -> None:
    result = run_order_runtime(
        text=(
            "Hi Noor, I need 2 CH 616 black chairs. My name is Victor Cutover, "
            "email cutover-all-20260616094954@example.com"
        ),
        metadata={},
    )

    assert result.decision.route == "product_selection"
    assert result.state.pending_question_frame is None
    assert [
        (line.catalog_ref, line.quantity, line.source_text, line.status, line.sku)
        for line in result.state.lines
    ] == [("CH-616", 2, "CH 616 black chairs", "unresolved", "CH-616")]


def test_order_runtime_trace_is_bounded_and_records_phase_latency() -> None:
    result = run_order_runtime(
        text="I need 2 CH 616 chairs",
        metadata={},
    )

    trace = result.trace.model_dump()
    assert trace["route"] == "product_selection"
    assert trace["handled"] is True
    assert trace["reason_codes"] == ["complete_order_lines"]
    assert trace["source"] == "catalog_refs"
    assert trace["line_count"] == 1
    assert trace["total_ms"] >= 0
    assert set(trace["phase_ms"]) == {
        "load_state",
        "extract_intent",
        "apply_reducer",
        "decide",
    }
    assert all(value >= 0 for value in trace["phase_ms"].values())
    assert "text" not in trace
    assert "source_text" not in trace


def test_order_runtime_trace_records_legacy_migration_read() -> None:
    result = run_order_runtime(
        text="4 position CH 616 chairs",
        metadata={
            "quote_customer_details": {
                "name": "Lilia",
                "company": "Del company",
                "address": "2 street",
            }
        },
    )

    assert result.trace.legacy_migration_read is True


def test_order_runtime_merges_legacy_state_with_new_order_lines() -> None:
    result = run_order_runtime(
        text="4 position CH 616 chairs",
        metadata={
            "quote_customer_details": {
                "name": "Lilia",
                "company": "Del company",
                "address": "2 street",
            }
        },
    )

    assert result.state.quote_details.name == "Lilia"
    assert result.state.quote_details.company == "Del company"
    assert result.state.quote_details.address == "2 street"
    assert [(line.catalog_ref, line.quantity) for line in result.state.lines] == [
        ("CH-616", 4)
    ]


def test_order_runtime_accepts_point_as_trailing_unit_count() -> None:
    result = run_order_runtime(
        text="CH 615 new 6 point",
        metadata={},
    )

    assert result.decision.route == "product_selection"
    assert result.decision.handled is True
    assert [
        (line.catalog_ref, line.quantity, line.source_text, line.status, line.sku)
        for line in result.state.lines
    ] == [("CH-615", 6, "CH 615 new", "unresolved", "CH-615")]


def test_order_runtime_routes_missing_quantity_to_clarification() -> None:
    result = run_order_runtime(
        text="I need SKYLAND NOVO 2400 Meeting Table",
        metadata={},
    )

    assert result.decision.route == "quantity_clarification"
    assert result.decision.handled is True
    assert result.decision.reason_codes == ["missing_quantities"]
    assert [
        (line.catalog_ref, line.quantity, line.status) for line in result.state.lines
    ] == [("SKYLAND NOVO 2400", None, "needs_quantity")]


def test_order_runtime_creates_typed_quantity_frame_for_missing_sku_quantity() -> None:
    result = run_order_runtime(
        text="SK 45 White",
        metadata={},
    )

    assert result.decision.route == "quantity_clarification"
    state = result.state.model_dump(mode="json")
    quantity_frame = state["pending_question_frame"]
    assert quantity_frame["question_kind"] == "quantity"
    assert quantity_frame["status"] == "active"
    assert quantity_frame["max_customer_turns"] == 2
    assert quantity_frame["source_refs"] == [
        {
            "kind": "order_line",
            "catalog_ref": "SK-45",
            "source_text": "SK 45 White",
            "sku": "SK-45",
            "ordinal": 1,
        }
    ]


def test_order_runtime_bare_quantity_consumes_typed_frame_without_assistant_prose() -> (
    None
):
    result = run_order_runtime(
        text="2",
        metadata={
            "order_runtime": {
                "pending_question_frame": {
                    "version": 1,
                    "frame_id": "quantity:sk45",
                    "question_kind": "quantity",
                    "status": "active",
                    "prompt_key": "ask_quantity_for_sku",
                    "max_customer_turns": 2,
                    "turns_seen": 0,
                    "source_refs": [
                        {
                            "kind": "order_line",
                            "catalog_ref": "SK-45",
                            "source_text": "SK 45 White",
                            "ordinal": 1,
                        }
                    ],
                }
            }
        },
    )

    assert result.decision.route == "product_selection"
    assert result.decision.handled is True
    assert result.decision.reason_codes == ["quantity_frame_answered"]
    assert [
        (line.catalog_ref, line.quantity, line.source_text, line.status, line.sku)
        for line in result.state.lines
    ] == [("SK-45", 2, "SK 45 White", "resolved", "SK-45")]
    assert (
        result.state.model_dump(mode="json")["pending_question_frame"]["status"]
        == "answered"
    )


def test_order_runtime_quantity_frame_preserves_resolved_lines_after_roundtrip() -> (
    None
):
    first_result = run_order_runtime(
        text="I need 2 CH 616 chairs and SKYLAND NOVO 2400 Meeting Table",
        metadata={},
    )

    assert first_result.decision.route == "quantity_clarification"
    assert [
        (line.catalog_ref, line.quantity, line.status)
        for line in first_result.state.lines
    ] == [
        ("CH-616", 2, "unresolved"),
        ("SKYLAND NOVO 2400", None, "needs_quantity"),
    ]
    assert first_result.state.pending_question_frame is not None

    second_result = run_order_runtime(
        text="1",
        metadata=pending_question_frame_to_metadata(
            {},
            first_result.state.pending_question_frame,
        ),
    )

    assert second_result.decision.route == "product_selection"
    assert second_result.decision.reason_codes == ["quantity_frame_answered"]
    assert [
        (line.catalog_ref, line.quantity, line.source_text, line.status, line.sku)
        for line in second_result.state.lines
    ] == [
        ("CH-616", 2, "CH 616 chairs", "unresolved", "CH-616"),
        (
            "SKYLAND NOVO 2400",
            1,
            "SKYLAND NOVO 2400 Meeting Table",
            "resolved",
            "SKYLAND NOVO 2400",
        ),
    ]


def test_order_runtime_exhausted_quantity_frame_does_not_capture_bare_number() -> None:
    result = run_order_runtime(
        text="2",
        metadata={
            "order_runtime": {
                "pending_question_frame": {
                    "version": 1,
                    "frame_id": "quantity:sk45",
                    "question_kind": "quantity",
                    "status": "active",
                    "prompt_key": "ask_quantity_for_sku",
                    "max_customer_turns": 2,
                    "turns_seen": 2,
                    "source_refs": [
                        {
                            "kind": "order_line",
                            "catalog_ref": "SK-45",
                            "source_text": "SK 45 White",
                            "ordinal": 1,
                        }
                    ],
                }
            }
        },
    )

    assert result.decision.route == "legacy_fallback"
    assert result.decision.handled is False
    assert result.state.lines == []


def test_order_runtime_ages_quantity_frame_on_non_answer_turns() -> None:
    frame_metadata = {
        "order_runtime": {
            "pending_question_frame": {
                "version": 1,
                "frame_id": "quantity:sk45",
                "question_kind": "quantity",
                "status": "active",
                "prompt_key": "ask_quantity_for_sku",
                "max_customer_turns": 2,
                "turns_seen": 0,
                "source_refs": [
                    {
                        "kind": "order_line",
                        "catalog_ref": "SK-45",
                        "source_text": "SK 45 White",
                        "ordinal": 1,
                    }
                ],
            }
        }
    }

    first_result = run_order_runtime(
        text="Do you deliver tomorrow?",
        metadata=frame_metadata,
    )

    aged_frame = first_result.state.pending_question_frame
    assert aged_frame is not None
    assert aged_frame.status == "active"
    assert aged_frame.turns_seen == 1

    second_result = run_order_runtime(
        text="What about assembly?",
        metadata=pending_question_frame_to_metadata({}, aged_frame),
    )

    expired_frame = second_result.state.pending_question_frame
    assert expired_frame is not None
    assert expired_frame.status == "expired"
    assert expired_frame.turns_seen == 2
    assert second_result.decision.route == "legacy_fallback"

    stale_answer_result = run_order_runtime(
        text="2",
        metadata=pending_question_frame_to_metadata({}, expired_frame),
    )
    assert stale_answer_result.decision.route == "legacy_fallback"
    assert stale_answer_result.state.lines == []


def test_order_runtime_routes_mixed_complete_and_missing_lines_to_clarification() -> (
    None
):
    result = run_order_runtime(
        text="I need 2 CH 616 chairs and SKYLAND NOVO 2400 Meeting Table",
        metadata={},
    )

    assert result.decision.route == "quantity_clarification"
    assert result.decision.handled is True
    assert "missing_quantities" in result.decision.reason_codes


def test_order_runtime_does_not_select_stock_or_price_inquiry() -> None:
    result = run_order_runtime(
        text="How much is 2 CH 616 chairs?",
        metadata={},
    )

    assert result.decision.route == "legacy_fallback"
    assert result.decision.handled is False


def test_order_runtime_keeps_valid_order_with_incidental_blocker_words() -> None:
    result = run_order_runtime(
        text="Price is okay, I want 2 CH 616 chairs for Stockholm office",
        metadata={},
    )

    assert result.decision.route == "product_selection"
    assert [(line.catalog_ref, line.quantity) for line in result.state.lines] == [
        ("CH-616", 2)
    ]


def test_order_runtime_blocks_localized_price_inquiries() -> None:
    for text in (
        "ما هو سعر 2 CH 616؟",
        "هل يتوفر 2 CH 616 في المخزون؟",
        "Сколько стоит 2 CH 616?",
    ):
        result = run_order_runtime(text=text, metadata={})

        assert result.decision.route == "legacy_fallback"
        assert result.decision.handled is False
