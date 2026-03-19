from src.core.discounts import apply_discount, get_discount_percentage


def test_get_discount_percentage() -> None:
    assert get_discount_percentage("Wholesale") == 15
    assert get_discount_percentage("Developer") == 5
    assert get_discount_percentage("Unknown") == 0


def test_apply_discount() -> None:
    assert apply_discount(100.0, "Wholesale") == 85.0
    assert apply_discount(100.0, "Unknown") == 100.0


# ---------------------------------------------------------------------------
# Edge cases: Zoho CRM returns Segment as list, not str (bug that hit prod)
# ---------------------------------------------------------------------------


class TestSegmentNormalization:
    """Cover real-world Segment values from Zoho CRM multi-select field."""

    def test_segment_as_list(self) -> None:
        """Zoho CRM returns Segment as ['Wholesale'] — must still apply 15%."""
        assert get_discount_percentage(["Wholesale"]) == 15
        assert apply_discount(100.0, ["Wholesale"]) == 85.0

    def test_segment_empty_list(self) -> None:
        """Empty list → Unknown → 0% discount."""
        assert get_discount_percentage([]) == 0
        assert apply_discount(100.0, []) == 100.0

    def test_segment_none(self) -> None:
        """None → Unknown → 0% discount."""
        assert get_discount_percentage(None) == 0
        assert apply_discount(100.0, None) == 100.0

    def test_segment_multiselect(self) -> None:
        """Multi-select list: first value used for discount lookup."""
        # First value "Unknown" → 0%
        assert get_discount_percentage(["Unknown", "Retail chain B2B"]) == 0
        assert apply_discount(100.0, ["Unknown", "Retail chain B2B"]) == 100.0

    def test_segment_multiselect_known_first(self) -> None:
        """Multi-select with recognized first value."""
        assert get_discount_percentage(["Horeca", "Wholesale"]) == 10
        assert apply_discount(200.0, ["Horeca", "Wholesale"]) == 180.0

    def test_segment_list_design_agency(self) -> None:
        """Design Agency as list element → 10%."""
        assert get_discount_percentage(["Design Agency"]) == 10
        assert apply_discount(1000.0, ["Design Agency"]) == 900.0
