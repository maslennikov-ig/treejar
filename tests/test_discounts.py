"""Tests for src.core.discounts — normalize segment from CRM (list/str/None)."""
from __future__ import annotations

import pytest

from src.core.discounts import (
    _normalize_segment,
    apply_discount,
    get_discount_percentage,
)


class TestNormalizeSegment:
    """CRM returns Segment as list, str, or None — all must be handled."""

    def test_list_single_element(self) -> None:
        assert _normalize_segment(["Wholesale"]) == "Wholesale"

    def test_list_multiple_elements(self) -> None:
        assert _normalize_segment(["Wholesale", "Horeca"]) == "Wholesale"

    def test_empty_list(self) -> None:
        assert _normalize_segment([]) == "Unknown"

    def test_string(self) -> None:
        assert _normalize_segment("Wholesale") == "Wholesale"

    def test_none(self) -> None:
        assert _normalize_segment(None) == "Unknown"

    def test_empty_string(self) -> None:
        assert _normalize_segment("") == "Unknown"


class TestGetDiscountPercentage:
    """Discount lookup with all segment formats."""

    @pytest.mark.parametrize(
        "segment,expected",
        [
            ("Wholesale", 15),
            (["Wholesale"], 15),
            ("Horeca", 10),
            (["Horeca"], 10),
            ("Design Agency", 10),
            ("Developer", 5),
            ("Unknown", 0),
            (["NonExistent"], 0),
            (None, 0),
            ([], 0),
        ],
    )
    def test_discount_lookup(self, segment: str | list | None, expected: int) -> None:
        assert get_discount_percentage(segment) == expected


class TestApplyDiscount:
    """Price calculation with discount."""

    def test_wholesale_list(self) -> None:
        """The exact case that crashed on prod: Segment=['Wholesale']."""
        assert apply_discount(1000.0, ["Wholesale"]) == 850.0

    def test_wholesale_string(self) -> None:
        assert apply_discount(1000.0, "Wholesale") == 850.0

    def test_no_discount(self) -> None:
        assert apply_discount(1000.0, None) == 1000.0

    def test_horeca(self) -> None:
        assert apply_discount(1000.0, ["Horeca"]) == 900.0

    def test_zero_price(self) -> None:
        assert apply_discount(0.0, ["Wholesale"]) == 0.0
