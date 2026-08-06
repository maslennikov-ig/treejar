"""Regressions for the volunteered-attribute contract (tj-feet.3)."""

from __future__ import annotations

import pytest

from src.dialogue.claim_contract import (
    AttributeClaim,
    AttributeStatus,
    RetrievedRow,
    apply_contract,
    attribute_status,
    check_claim,
    normalize_field_path,
    partial_answer,
)

# One row shaped like the live catalog: an English description, a short
# specifications map with the namespace exactly as the audit found it.
_ROWS = {
    "AX-E1": RetrievedRow(
        sku="AX-E1",
        fields={
            "attributes.specifications.Mechanism": "synchronised tilt",
            "attributes.specifications.Recommended load": "120 kg",
            "attributes.specifications.Warranty": "5 years",
            "price": "800",
        },
        absent_fields=frozenset({"attributes.specifications.Upholstery"}),
        not_applicable_fields=frozenset({"attributes.specifications.Gaslift"}),
    )
}


def _claim(**overrides: object) -> AttributeClaim:
    values: dict[str, object] = {"claim_type": "catalog_fact", "sku": "AX-E1"}
    values.update(overrides)
    return AttributeClaim(**values)  # type: ignore[arg-type]


# --- the volunteered unsupported attribute ----------------------------------


def test_a_volunteered_attribute_absent_from_the_row_is_unverified_not_blocked() -> (
    None
):
    """The mesh back nobody asked about and the catalog never stated.

    This reverses the original `tj-feet.3` criterion, under the owner decision
    of 2026-08-06. The strict rule blocked whatever it could not prove, and the
    measurement said what that bought: 0.000 fabrications caught across a
    counter-set built to bait them, against 30 of 37 replies rewritten. A
    spoiled reply is worse than a rare invented attribute — the customer sees it
    at once, and a wrong reply can be corrected while a mangled one has already
    been read.

    So the claim ships, and is recorded as unverified rather than approved.
    """
    check = check_claim(
        _claim(field_path="attributes.specifications.Back material", value="mesh"),
        _ROWS,
    )

    assert check.may_reach_customer is True
    assert check.supported is False
    assert check.status is AttributeStatus.UNKNOWN


def test_a_supported_attribute_reaches_the_customer() -> None:
    check = check_claim(
        _claim(
            field_path="attributes.specifications.Mechanism", value="synchronised tilt"
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True
    assert check.status is AttributeStatus.KNOWN_VALUE


def test_a_claim_about_another_sku_is_not_confirmed_by_this_row() -> None:
    """No row was retrieved for DK-4, so nothing here can confirm or deny it."""
    check = check_claim(
        _claim(
            sku="DK-4",
            field_path="attributes.specifications.Mechanism",
            value="synchronised tilt",
        ),
        _ROWS,
    )

    assert check.supported is False
    assert check.may_reach_customer is True


def test_a_value_the_row_does_not_carry_is_withheld() -> None:
    check = check_claim(
        _claim(field_path="attributes.specifications.Warranty", value="10 years"),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "not the value stored" in check.reason


def test_the_uncanonical_key_namespace_does_not_produce_false_negatives() -> None:
    """`Recommended load` and `Recommended Load` are both live catalog keys."""
    assert normalize_field_path("attributes.specifications.Recommended Load") == (
        normalize_field_path("Recommended load")
    )

    check = check_claim(
        _claim(field_path="Recommended Load", value="120 kg"),
        _ROWS,
    )

    assert check.may_reach_customer is True


# --- the fabricated seating capacity ----------------------------------------


def test_a_bare_seating_capacity_claim_cannot_reach_the_customer() -> None:
    """No active SKU carries a capacity field; a bare claim is always invented."""
    check = check_claim(
        _claim(sku="DK-4", field_path="capacity", value="10 people"),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "not a catalog field" in check.reason


@pytest.mark.parametrize("path", ["capacity", "seats", "seating_capacity", "pax"])
def test_every_capacity_path_is_refused_as_a_plain_fact(path: str) -> None:
    assert (
        check_claim(
            _claim(sku="DK-4", field_path=path, value="10"), _ROWS
        ).may_reach_customer
        is False
    )


def test_a_marked_capacity_assumption_with_a_question_is_allowed() -> None:
    """Owner decision of 2026-08-05: this is the permitted way to say it."""
    check = check_claim(
        _claim(
            claim_type="explicit_assumption",
            sku="DK-4",
            field_path="capacity",
            value="10",
            marker_present=True,
            confirming_question=True,
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


@pytest.mark.parametrize(
    ("marker", "question"), [(True, False), (False, True), (False, False)]
)
def test_an_assumption_without_marker_or_question_is_withheld(
    marker: bool, question: bool
) -> None:
    check = check_claim(
        _claim(
            claim_type="explicit_assumption",
            sku="DK-4",
            field_path="capacity",
            value="10",
            marker_present=marker,
            confirming_question=question,
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False


def test_an_assumption_cannot_contradict_a_value_the_row_already_carries() -> None:
    check = check_claim(
        _claim(
            claim_type="explicit_assumption",
            field_path="attributes.specifications.Warranty",
            value="10 years",
            marker_present=True,
            confirming_question=True,
        ),
        _ROWS,
    )

    assert check.may_reach_customer is False
    assert "contradicts" in check.reason


# --- typed statuses ----------------------------------------------------------


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("attributes.specifications.Mechanism", AttributeStatus.KNOWN_VALUE),
        ("attributes.specifications.Upholstery", AttributeStatus.CONFIRMED_ABSENT),
        ("attributes.specifications.Gaslift", AttributeStatus.NOT_APPLICABLE),
        ("attributes.specifications.Back material", AttributeStatus.UNKNOWN),
    ],
)
def test_a_missing_attribute_is_a_typed_status_not_an_empty_string(
    path: str, expected: AttributeStatus
) -> None:
    assert attribute_status("AX-E1", path, _ROWS) is expected


def test_a_recommendation_is_never_blocked_as_a_catalog_attribute() -> None:
    check = check_claim(_claim(claim_type="recommendation"), _ROWS)

    assert check.may_reach_customer is True


# --- the unknown branch answers, it does not refuse -------------------------


def test_an_unknown_attribute_yields_a_useful_partial_answer() -> None:
    answer = partial_answer(
        sku="AX-E1",
        unknown_field_paths=("attributes.specifications.Back material",),
        confirmed={"price": "AED 800", "stock": "7 in Dubai"},
    )

    assert "does not state" in answer
    assert "confirm" in answer
    assert "AED 800" in answer and "7 in Dubai" in answer
    for refusal in ("cannot help", "unable to", "I can't"):
        assert refusal not in answer


def test_the_arabic_partial_answer_still_hands_over_what_is_confirmed() -> None:
    answer = partial_answer(
        sku="AX-E1",
        unknown_field_paths=("attributes.specifications.Back material",),
        confirmed={"price": "800 AED"},
        arabic=True,
    )

    assert "AX-E1" in answer
    assert "800 AED" in answer


def test_an_arabic_reply_is_verified_against_the_english_row() -> None:
    """No active SKU carries Arabic text, so there is no Arabic source to want."""
    check = check_claim(
        _claim(
            field_path="attributes.specifications.Mechanism", value="synchronised tilt"
        ),
        _ROWS,
    )

    assert check.may_reach_customer is True


# --- the contract over a whole reply ----------------------------------------


def test_the_contract_separates_proven_false_from_merely_unconfirmed() -> None:
    """Three buckets, not two.

    Only the capacity is blocked, because the owner rule of 2026-08-05 blocks
    it outright. The unstated back material ships but stays visible in its own
    bucket: giving up the block is not a reason to give up the telemetry.
    """
    result = apply_contract(
        (
            _claim(
                field_path="attributes.specifications.Mechanism",
                value="synchronised tilt",
            ),
            _claim(field_path="attributes.specifications.Back material", value="mesh"),
            _claim(sku="DK-4", field_path="capacity", value="10"),
            _claim(claim_type="recommendation"),
        ),
        _ROWS,
    )

    assert len(result.approved) == 3
    assert result.withheld_field_paths == ("capacity",)
    assert result.unverified_field_paths == ("attributes.specifications.Back material",)


def test_a_contradicted_value_is_still_blocked() -> None:
    """The one thing the contract still stops: a statement the row refutes."""
    result = apply_contract(
        (_claim(field_path="attributes.specifications.Warranty", value="10 years"),),
        _ROWS,
    )

    assert result.approved == ()
    assert result.unverified == ()
    assert result.withheld_field_paths == ("attributes.specifications.Warranty",)


# --- formatted values, found by the tj-feet.10 measurement -------------------


@pytest.mark.parametrize(
    ("claimed", "stored"),
    [
        # What the model actually emitted against the live extras, where a
        # price is stored as a bare decimal and quoted with its currency.
        ("AED 800", "800.00"),
        ("800 AED", "800.00"),
        ("2,000", "2000"),
        ("2,000 AED", "2000.00"),
        ("٨٠٠ درهم", "800.00"),
        ("5-year warranty", "5 years"),
        ("5 units", "5"),
    ],
)
def test_a_formatted_number_is_the_stored_number(claimed: str, stored: str) -> None:
    """Currency, separators and word order are presentation, not provenance.

    Measured on 2026-08-05: withholding these was the single largest class of
    false withholding, ahead of every real one. A customer being told the
    catalog does not state a price it does state is the worst outcome the
    contract can produce.
    """
    rows = {
        "AX-E1": RetrievedRow(sku="AX-E1", fields={"price": stored}),
    }
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact", sku="AX-E1", field_path="price", value=claimed
        ),
        rows,
    )

    assert check.may_reach_customer is True


@pytest.mark.parametrize(
    ("claimed", "stored"),
    [
        ("150 kg", "120 kg"),
        ("AED 900", "800.00"),
        ("7 units", "5"),
        ("mesh", "steel frame"),
    ],
)
def test_a_different_number_is_still_withheld(claimed: str, stored: str) -> None:
    """The tolerance is for formatting, not for a different value."""
    rows = {
        "AX-E1": RetrievedRow(sku="AX-E1", fields={"price": stored}),
    }
    check = check_claim(
        AttributeClaim(
            claim_type="catalog_fact", sku="AX-E1", field_path="price", value=claimed
        ),
        rows,
    )

    assert check.may_reach_customer is False
