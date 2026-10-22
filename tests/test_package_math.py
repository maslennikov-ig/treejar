"""tj-asty.1: deterministic line, package and 5% UAE VAT arithmetic."""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    AttributeClaim,
    ClaimInput,
    check_claim,
    row_from_catalog_product,
)
from src.llm.money import amount_with_uae_vat, format_money, line_subtotal
from src.llm.package_math import (
    PricedLine,
    budget_check_text,
    explicit_item_quantity,
    line_math_text,
    multi_item_total_text,
    product_reference_keys,
    seat_based_units,
    turnkey_package_text,
    unit_price_vat_text,
)

LUMA = (
    "Four person workstation SKYLAND LUMA 9719-4",
    "OF-HAI-Luma-Workstation-RJ 9719-4-Walnut",
)
CH616_NEW = ("Operative Office Chair CH 616 NEW black", "CH 616 NEW black")
CH616 = ("Operative Office Chair CH 616 black", "CH 616 black")
CH460 = ("Executive Office Chair CH 460 black", "CH 460 black")
CH460_WHITE = ("Executive Office Chair CH 460 white", "CH 460 white")


def test_vat_is_exact_to_the_cent() -> None:
    assert amount_with_uae_vat(5649) == (5649.0, 282.45, 5931.45)
    assert amount_with_uae_vat(2698) == (2698.0, 134.9, 2832.9)
    # Half-up, as an invoice rounds: 0.05 × 14.75 = 0.7375 -> 0.74.
    assert amount_with_uae_vat(14.75) == (14.75, 0.74, 15.49)
    assert line_subtotal(3, 1883) == 5649.0
    assert format_money(5931.45) == "5,931.45"
    assert unit_price_vat_text(1883, "AED") == (
        "excl. 5% VAT; 1,977.15 AED incl. 5% VAT"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Hi, I'm Rami. Do you sell laboratory fume hoods? Also, if we order 3 "
            "workstations of SKYLAND LUMA 9719-4 for our office in Dubai?",
            {LUMA: 3},
        ),
        (
            "Wait, our total budget for the 3 LUMA 9719-4 workstations is 6,000 AED.",
            {LUMA: 3},
        ),
        (
            "I want 1 chair CH 616 NEW black and 3 chairs CH 460 black",
            {CH616_NEW: 1, CH616: None, CH460: 3, CH460_WHITE: None},
        ),
        (
            "Please check the price for CH 616 NEW black. I need 4 chairs.",
            {CH616_NEW: 4, CH616: None},
        ),
        ("We also need three LUMA 9719-4 workstations in walnut", {LUMA: 3}),
        ("2 x CH 460 black please", {CH460: 2, CH460_WHITE: None}),
        ("CH 460 black x 5", {CH460: 5}),
        # A comparison names no quantity, and a budget is not a quantity.
        ("Please compare LUMA 9719-4 and a NOVO 2400 setup", {LUMA: None}),
        ("LUMA 9719-4 under 6,000 AED?", {LUMA: None}),
        # Two products and one count: the count belongs to neither.
        ("Compare CH 616 NEW black and CH 460 black, I need 4 chairs", {CH460: None}),
    ],
)
def test_explicit_item_quantity_reads_only_what_the_customer_wrote(
    text: str, expected: dict[tuple[str, str], int | None]
) -> None:
    for (name, sku), quantity in expected.items():
        assert explicit_item_quantity(text, name=name, sku=sku) == quantity, name


def test_reference_keys_name_the_model_code() -> None:
    assert "luma 9719-4" in product_reference_keys(*LUMA)
    assert product_reference_keys(*CH616_NEW) == ("ch 616",)


def test_seat_based_units_use_the_seats_the_name_states() -> None:
    assert seat_based_units(6, family="workspace", name_capacity=6) == 1
    assert seat_based_units(6, family="workspace", name_capacity=4) == 2
    assert seat_based_units(6, family="seating", name_capacity=1) == 6
    assert seat_based_units(6, family="storage", name_capacity=1) is None
    assert seat_based_units(6, family="workspace", name_capacity=None) is None
    assert seat_based_units(None, family="seating", name_capacity=1) is None


def test_budget_check_never_calls_a_fitting_total_above_budget() -> None:
    """The client's previous bot called 5,931.45 AED 'above' 6,000 AED."""

    fits = budget_check_text(5649, 6000)
    assert fits is not None
    assert "FITS within budget both excl. VAT (5,649.00 AED)" in fits
    assert "incl. 5% VAT (5,931.45 AED); 68.55 AED remaining after VAT" in fits

    vat_tips_over = budget_check_text(5900, 6000)
    assert vat_tips_over is not None
    assert "FITS excl. 5% VAT (5,900.00 AED)" in vat_tips_over
    assert "195.00 AED above the cap" in vat_tips_over

    above = budget_check_text(6500, 6000)
    assert above is not None and "ABOVE budget by 500.00 AED" in above
    assert budget_check_text(6500, None) is None


def test_line_math_states_quantity_unit_subtotal_vat_and_stock() -> None:
    line = PricedLine(
        sku=LUMA[1],
        name=LUMA[0],
        family="workspace",
        quantity=3,
        unit_price=1883.0,
        currency="AED",
        explicit=True,
        stock=30,
    )
    assert line_math_text(line) == (
        "Verified line math (3 unit(s) as requested by the customer): 3 × "
        "1,883.00 AED = 5,649.00 AED excl. 5% VAT (5,931.45 AED incl. 5% VAT; "
        "5% VAT = 282.45 AED). Stock check: 30 in stock covers 3."
    )


def _line(
    name: str, sku: str, family: str, qty: int, price: float, **kw: object
) -> PricedLine:
    return PricedLine(
        sku=sku,
        name=name,
        family=family,
        quantity=qty,
        unit_price=price,
        currency="AED",
        **kw,  # type: ignore[arg-type]
    )


def test_multi_item_total_for_scenario_b_mix() -> None:
    lines = [
        _line(*CH616_NEW, "seating", 1, 295.0, explicit=True, stock=1),
        _line(*CH460, "seating", 3, 801.0, explicit=True, stock=34),
    ]
    result = multi_item_total_text(lines, None)
    assert result is not None
    text, total = result
    assert total == 2698.0
    assert (
        "1 × Operative Office Chair CH 616 NEW black (295.00 AED) + 3 × "
        "Executive Office Chair CH 460 black (2,403.00 AED) = 2,698.00 AED "
        "excl. 5% VAT (2,832.90 AED incl. 5% VAT; 5% VAT = 134.90 AED)"
    ) in text
    assert multi_item_total_text(lines[:1], None) is None


def test_turnkey_package_takes_the_cheapest_in_stock_row_per_family() -> None:
    lines = [
        _line(
            "6 Person Face to Face Table SKYLAND NOVO 3600",
            "WS6",
            "workspace",
            1,
            2598.0,
            explicit=False,
            seats_covered=6,
            stock=8,
        ),
        _line(
            "4 Person Face to Face Table SKYLAND NOVO 2400",
            "WS4",
            "workspace",
            2,
            1813.0,
            explicit=False,
            seats_covered=6,
            stock=29,
        ),
        _line(
            "Operative Office Chair CH 616 NEW black",
            "CH616",
            "seating",
            6,
            295.0,
            explicit=False,
            seats_covered=6,
            stock=1,
        ),
        _line(
            "Executive Office Chair CH 145 grey NEW",
            "CH145",
            "seating",
            6,
            596.0,
            explicit=False,
            seats_covered=6,
            stock=48,
        ),
    ]
    result = turnkey_package_text(lines, 6, 10000)
    assert result is not None
    text, total = result
    # CH 616 has 1 in stock for 6 seats, so it cannot carry the package.
    assert total == 2598.0 + 6 * 596.0
    assert text.startswith(
        "Verified turnkey package math (6 seats): 1 × 6 Person Face to Face "
        "Table SKYLAND NOVO 3600 (1 × 2,598.00 = 2,598.00 AED) + 6 × Executive "
        "Office Chair CH 145 grey NEW (6 × 596.00 = 3,576.00 AED) = 6,174.00 AED "
        "excl. 5% VAT (6,482.70 AED incl. 5% VAT"
    )
    assert "Budget check (cap 10,000.00 AED): FITS" in text
    assert turnkey_package_text(lines[:2], 6, None) is None


def test_claim_contract_restates_vat_and_line_derivations() -> None:
    row = row_from_catalog_product(
        sku=LUMA[1],
        attributes=None,
        extras={"price": 1883, "quantity": 3, "line_subtotal_excl_vat": "5649.00"},
    )
    assert row.fields["price_incl_vat"] == "1977.15"
    assert row.fields["vat_amount"] == "94.15"
    rows = {LUMA[1]: row}

    for figure in ("5,649.00 AED", "5,931.45 AED incl. VAT", "282.45 AED VAT"):
        claim = AttributeClaim(
            claim_type="derived_fact",
            sku=LUMA[1],
            value=figure,
            operation="product",
            inputs=(
                ClaimInput(sku=LUMA[1], field_path="quantity", value="3"),
                ClaimInput(sku=LUMA[1], field_path="price", value="1883"),
            ),
        )
        assert check_claim(claim, rows).may_reach_customer, figure

    invented = AttributeClaim(
        claim_type="derived_fact",
        sku=LUMA[1],
        value="5,990.00 AED",
        operation="product",
        inputs=(
            ClaimInput(sku=LUMA[1], field_path="quantity", value="3"),
            ClaimInput(sku=LUMA[1], field_path="price", value="1883"),
        ),
    )
    assert not check_claim(invented, rows).may_reach_customer
