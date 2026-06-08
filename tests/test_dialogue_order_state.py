from __future__ import annotations

from src.dialogue.order_state import OrderState, extract_order_intent_from_text


def test_extract_order_intent_preserves_multi_item_lines() -> None:
    intent = extract_order_intent_from_text(
        "I need 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs"
    )

    assert [
        (line.catalog_ref, line.quantity, line.source_text, line.sku)
        for line in intent.lines
    ] == [
        ("SKYLAND NOVO 2400", 2, "SKYLAND NOVO 2400", "SKYLAND NOVO 2400"),
        ("CH-616", 4, "CH 616", "CH-616"),
    ]


def test_extract_order_intent_keeps_missing_quantity_lines() -> None:
    intent = extract_order_intent_from_text("I need SKYLAND NOVO 2400 Meeting Table")

    assert [
        (line.catalog_ref, line.quantity, line.status, line.sku)
        for line in intent.lines
    ] == [("SKYLAND NOVO 2400", None, "needs_quantity", "SKYLAND NOVO 2400")]


def test_order_state_loads_legacy_quote_metadata() -> None:
    state = OrderState.from_legacy_metadata(
        {
            "pending_quote_selection": {
                "items": [
                    {
                        "quantity": 4,
                        "item_candidate": "Two-Person Liner Table SKYLAND NOVO 2400",
                        "sku": "SKYLAND NOVO 2400",
                    }
                ],
                "source": "assistant_quote_summary",
            },
            "quote_customer_details": {
                "name": "Lilia",
                "company": "Del company",
                "address": "2 street",
                "email": "lilia@example.com",
            },
        }
    )

    assert [
        (line.catalog_ref, line.quantity, line.source_text, line.sku)
        for line in state.lines
    ] == [
        (
            "SKYLAND NOVO 2400",
            4,
            "Two-Person Liner Table SKYLAND NOVO 2400",
            "SKYLAND NOVO 2400",
        )
    ]
    assert state.quote_details.name == "Lilia"
    assert state.quote_details.company == "Del company"
    assert state.quote_details.address == "2 street"
    assert state.quote_details.email == "lilia@example.com"
