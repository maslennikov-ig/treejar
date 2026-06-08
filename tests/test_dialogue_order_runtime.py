from __future__ import annotations

from src.dialogue.order_runtime import run_order_runtime


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
