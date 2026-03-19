DISCOUNTS = {
    "Wholesale": 15,
    "Retail chain B2B": 15,
    "Horeca": 10,
    "Design Agency": 10,
    "Developer": 5,
}


def _normalize_segment(segment: str | list[str] | None) -> str:
    """Normalize segment value from CRM (may be str, list, or None)."""
    if isinstance(segment, list):
        return segment[0] if segment else "Unknown"
    return segment or "Unknown"


def get_discount_percentage(segment: str | list[str] | None) -> int:
    return DISCOUNTS.get(_normalize_segment(segment), 0)


def apply_discount(price: float, segment: str | list[str] | None) -> float:
    discount = get_discount_percentage(segment)
    return price * (1 - (discount / 100.0))
