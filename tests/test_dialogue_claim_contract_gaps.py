"""The three contract gaps the `tj-feet.10` measurement found.

Running the claim contract over every catalog turn on 2026-08-05 would have
rewritten 30 of 37 turns, and almost none of that was a fabrication being
caught. Three structural classes accounted for it, each a gap in the contract
rather than a defect in the model:

* `tj-feet.12` — a derived fact has no field path by definition, so a
  comparison, a total or a calculation could never be supported.
* `tj-feet.13` — an Arabic surface form was compared literally against an
  English stored value, so every translated value was withheld. The module
  documented the intended behaviour; containment did not implement it.
* `tj-feet.14` — saying an attribute is *absent* was itself withheld, which
  withholds the exact sentence the partial answer exists to produce.

Every test here failed before the fix.
"""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    AttributeClaim,
    AttributeStatus,
    ClaimInput,
    RetrievedRow,
    apply_contract,
    check_claim,
)

_ROWS = {
    "CH-A": RetrievedRow(
        sku="CH-A",
        fields={
            "price": "800.00",
            "attributes.specifications.Frame": "steel frame",
            "attributes.specifications.Origin": "Dubai",
            "attributes.specifications.Recommended load": "120 kg",
        },
        absent_fields=frozenset({"attributes.specifications.Upholstery"}),
        not_applicable_fields=frozenset({"attributes.specifications.Gaslift"}),
    ),
    "CH-B": RetrievedRow(
        sku="CH-B",
        fields={"price": "900.00", "attributes.specifications.Frame": "aluminium"},
    ),
    "DK-2": RetrievedRow(sku="DK-2", fields={"price": "2000.00"}),
}


# --- tj-feet.14: an absence statement is not an attribute claim --------------


def test_saying_the_catalog_does_not_state_an_attribute_survives() -> None:
    """The sentence the whole partial answer exists to produce."""
    check = check_claim(
        AttributeClaim(
            claim_type="absence",
            sku="CH-A",
            field_path="attributes.specifications.Back material",
            value="not specified in the catalog",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True
    assert check.status is AttributeStatus.UNKNOWN


def test_an_absence_claim_in_arabic_survives_too() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="absence",
            sku="CH-A",
            field_path="attributes.specifications.Back material",
            value="غير متوفر",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


@pytest.mark.parametrize(
    ("path", "expected_status"),
    [
        ("attributes.specifications.Upholstery", AttributeStatus.CONFIRMED_ABSENT),
        ("attributes.specifications.Gaslift", AttributeStatus.NOT_APPLICABLE),
        ("attributes.specifications.Back material", AttributeStatus.UNKNOWN),
    ],
)
def test_every_not_known_status_supports_an_absence_claim(
    path: str, expected_status: AttributeStatus
) -> None:
    check = check_claim(
        AttributeClaim(claim_type="absence", sku="CH-A", field_path=path),
        _ROWS,
    )

    assert check.may_reach_customer is True
    assert check.status is expected_status


def test_denying_an_attribute_the_row_does_state_is_withheld() -> None:
    """The other half of the criterion: absence is checked, not waved through."""
    check = check_claim(
        AttributeClaim(
            claim_type="absence",
            sku="CH-A",
            field_path="attributes.specifications.Frame",
            value="not specified",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert check.status is AttributeStatus.KNOWN_VALUE


def test_absence_does_not_become_a_way_to_state_a_capacity() -> None:
    """Capacity is absent everywhere, so absence must stay a *denial* of it."""
    supported = check_claim(
        AttributeClaim(claim_type="absence", sku="CH-A", field_path="capacity"),
        _ROWS,
    )
    asserted = check_claim(
        AttributeClaim(
            claim_type="catalog_fact", sku="CH-A", field_path="capacity", value="10"
        ),
        _ROWS,
    )

    assert supported.may_reach_customer is True
    assert asserted.may_reach_customer is False


# --- tj-feet.13: the Arabic surface form is a translation, not a source ------


@pytest.mark.parametrize(
    ("arabic", "english", "path"),
    [
        ("هيكل فولاذي", "steel frame", "attributes.specifications.Frame"),
        ("دبي", "Dubai", "attributes.specifications.Origin"),
    ],
)
def test_an_arabic_surface_form_reaches_the_customer_with_its_english_source(
    arabic: str, english: str, path: str
) -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact",
            sku="CH-A",
            field_path=path,
            value=arabic,
            source_value=english,
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True
    assert "translation" in check.reason


def test_an_arabic_claim_whose_english_source_is_not_on_the_row_is_withheld() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact",
            sku="CH-A",
            field_path="attributes.specifications.Frame",
            value="هيكل ألومنيوم",
            source_value="aluminium frame",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False


def test_a_translation_may_not_smuggle_in_a_number_the_row_does_not_carry() -> None:
    """Words are translation; a figure is a fact in any script."""
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact",
            sku="CH-A",
            field_path="attributes.specifications.Recommended load",
            value="١٥٠ كجم",
            source_value="120 kg",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False


def test_a_translated_number_in_arabic_indic_digits_is_the_stored_number() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact",
            sku="CH-A",
            field_path="attributes.specifications.Recommended load",
            value="١٢٠ كجم",
            source_value="120 kg",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


def test_source_value_is_not_an_escape_hatch_for_an_english_surface() -> None:
    """The translation branch opens only for a non-Latin surface form.

    Otherwise a model could name a stored value in `source_value` and write
    anything it liked in `value`, which is the whole thing the contract exists
    to prevent.
    """
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact",
            sku="CH-A",
            field_path="attributes.specifications.Frame",
            value="mesh back",
            source_value="steel frame",
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False


def test_an_arabic_marked_assumption_is_verified_the_same_way() -> None:
    """The assumption branch shares the comparison, so it shares the fix."""
    check = check_claim(
        AttributeClaim(
            claim_type="explicit_assumption",
            sku="CH-A",
            field_path="attributes.specifications.Frame",
            value="هيكل فولاذي",
            source_value="steel frame",
            marker_present=True,
            confirming_question=True,
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


# --- tj-feet.12: verify the inputs of a derivation, not its output -----------


def _input(**overrides: object) -> ClaimInput:
    values: dict[str, object] = {"sku": "CH-A", "field_path": "price"}
    values.update(overrides)
    return ClaimInput(**values)  # type: ignore[arg-type]


def test_a_price_comparison_over_supported_inputs_reaches_the_customer() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="CH-A at AED 800 is cheaper than CH-B at AED 900",
            operation="comparison",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                _input(sku="CH-B", value="900.00"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


def test_a_line_total_over_a_supported_price_and_a_customer_quantity() -> None:
    """`AED 4,000 for two desks`: the price is the catalog's, the two is theirs."""
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="DK-2",
            value="AED 4,000 for two desks",
            operation="product",
            inputs=(
                _input(sku="DK-2", value="2000.00"),
                ClaimInput(field_path="quantity", value="2", customer_stated=True),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


def test_a_sum_over_two_supported_prices_reaches_the_customer() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="AED 1,700 for the pair",
            operation="sum",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                _input(sku="CH-B", value="900.00"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


def test_a_total_computed_from_an_unsupported_input_does_not_ship() -> None:
    """The criterion's negative half."""
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="AED 1,550 for the pair",
            operation="sum",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                _input(sku="CH-B", value="750.00"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "input" in check.reason


def test_a_derivation_whose_arithmetic_does_not_restate_is_blocked() -> None:
    """Supported inputs are not enough; the number in the reply must follow.

    This survives the 2026-08-06 reversal, because it is not an unproven claim.
    Both prices are on the row and `800 + 900` is not `1,500`, so the runtime
    can show the figure is wrong rather than merely unconfirmed.
    """
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="AED 1,500 for the pair",
            operation="sum",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                _input(sku="CH-B", value="900.00"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "does not produce" in check.reason


def test_a_stray_figure_in_a_comparison_is_unverified_not_false() -> None:
    """A comparison restates, it does not calculate, so nothing here is proven.

    The strict rule blocked this. Under the 2026-08-06 decision it ships and is
    recorded, because `250` between a stored 800 and 900 is unconfirmed rather
    than refuted — the operation names no arithmetic to refute it with.
    """
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="CH-A is AED 250 cheaper than CH-B",
            operation="comparison",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                _input(sku="CH-B", value="900.00"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True
    assert check.supported is True


def test_a_difference_that_does_restate_reaches_the_customer() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="CH-A is AED 100 cheaper than CH-B",
            operation="difference",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                _input(sku="CH-B", value="900.00"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


@pytest.mark.parametrize(
    ("label", "claim"),
    [
        (
            "no inputs to check against",
            AttributeClaim(
                claim_type="derived_fact",
                sku="CH-A",
                value="CH-A is the better value",
                operation="comparison",
            ),
        ),
        (
            "no operation to recompute",
            AttributeClaim(
                claim_type="derived_fact",
                sku="CH-A",
                value="CH-A works out cheaper overall",
                inputs=(ClaimInput(sku="CH-A", field_path="price", value="800.00"),),
            ),
        ),
    ],
)
def test_a_derivation_the_runtime_cannot_check_ships_as_unverified(
    label: str, claim: AttributeClaim
) -> None:
    """Unable to check is not the same as caught.

    Both of these were blocked before 2026-08-06. Neither is refuted by
    anything on the row, so under the owner decision both ship and are recorded.
    """
    check = check_claim(claim, _ROWS)

    assert check.may_reach_customer is True, label
    assert check.supported is False, label


def test_a_seating_capacity_cannot_enter_through_arithmetic() -> None:
    """`two desks x ten people = twenty` was the measured shape.

    The owner decision of 2026-08-05 stands whatever route the number takes:
    a per-product capacity is not a catalog fact, and multiplying it does not
    make it one. It belongs in the marked-assumption branch.
    """
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="DK-2",
            value="two desks seat twenty people",
            operation="product",
            inputs=(
                ClaimInput(field_path="quantity", value="2", customer_stated=True),
                _input(sku="DK-2", field_path="capacity", value="10"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "capacity" in check.reason


def test_a_customer_stated_capacity_for_a_product_is_still_refused() -> None:
    """Labelling an invented per-desk figure as the customer's does not help."""
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="DK-2",
            value="two desks seat twenty people",
            operation="product",
            inputs=(
                ClaimInput(field_path="quantity", value="2", customer_stated=True),
                ClaimInput(
                    sku="DK-2",
                    field_path="capacity",
                    value="10",
                    customer_stated=True,
                ),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False


def test_the_customers_own_headcount_is_not_a_product_capacity_claim() -> None:
    """A figure with no SKU is about the customer's team, not about a product.

    `one chair each for 20 people` multiplies the customer's own headcount by a
    catalog price. Nothing here states how many people a product seats, which is
    the only thing the capacity rule exists to stop.
    """
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="AED 16,000",
            operation="product",
            inputs=(
                _input(sku="CH-A", value="800.00"),
                ClaimInput(field_path="people", value="20", customer_stated=True),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


def test_a_customer_stated_input_may_not_contradict_the_retrieved_row() -> None:
    """Otherwise `customer_stated` is a hole straight through the contract."""
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="DK-2",
            value="AED 3,000 for the two desks",
            operation="product",
            inputs=(
                ClaimInput(
                    sku="DK-2", field_path="price", value="1500", customer_stated=True
                ),
                ClaimInput(field_path="quantity", value="2", customer_stated=True),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "contradict" in check.reason


def test_a_derived_input_may_itself_be_an_arabic_surface_form() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="derived_fact",
            sku="CH-A",
            value="١٧٠٠ درهم للاثنين",
            operation="sum",
            inputs=(
                ClaimInput(sku="CH-A", field_path="price", value="٨٠٠ درهم"),
                ClaimInput(sku="CH-B", field_path="price", value="٩٠٠ درهم"),
            ),
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


# --- a fourth class, found by the same replay --------------------------------


def test_naming_the_sku_itself_is_supported_by_the_row_it_names() -> None:
    """The row *is* this SKU; the identifier needs no column to be true.

    Found on 2026-08-05 replaying the stored claims: the model emitted
    `field_path=sku, value=CH-A` and the contract withheld it, because
    `row_from_catalog_product` never flattens the identifier into the fields.
    """
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact", sku="CH-A", field_path="sku", value="CH-A"
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


def test_naming_a_different_sku_than_the_row_is_still_withheld() -> None:
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact", sku="CH-A", field_path="sku", value="CH-B"
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False


def test_a_stored_sku_field_still_wins_over_the_identifier() -> None:
    """`setdefault`, not overwrite: a catalog that does carry the column rules."""
    rows = {"CH-A": RetrievedRow(sku="CH-A", fields={"sku": "CH-A-2024"})}
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact", sku="CH-A", field_path="sku", value="CH-A-2024"
        ),
        rows,
    )

    assert check.may_reach_customer is True


# --- the three together, over one reply --------------------------------------


def test_a_realistic_arabic_comparison_turn_ships_whole() -> None:
    """The shape that produced most of the 30 rewrites, now intact."""
    result = apply_contract(
        (
            AttributeClaim(
                claim_type="catalog_fact",
                sku="CH-A",
                field_path="attributes.specifications.Frame",
                value="هيكل فولاذي",
                source_value="steel frame",
            ),
            AttributeClaim(
                claim_type="absence",
                sku="CH-A",
                field_path="attributes.specifications.Back material",
                value="غير متوفر",
            ),
            AttributeClaim(
                claim_type="derived_fact",
                sku="CH-A",
                value="٨٠٠ مقابل ٩٠٠ درهم",
                operation="comparison",
                inputs=(
                    ClaimInput(sku="CH-A", field_path="price", value="800.00"),
                    ClaimInput(sku="CH-B", field_path="price", value="900.00"),
                ),
            ),
            AttributeClaim(claim_type="recommendation", sku="CH-A"),
        ),
        _ROWS,
    )

    assert result.withheld == ()
    assert len(result.approved) == 4
