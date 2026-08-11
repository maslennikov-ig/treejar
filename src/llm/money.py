"""Shared parsing primitives for customer-facing money amounts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

AMOUNT_TOKEN_PATTERN = r"\d[\d,]*(?:\.\d+)?"
BUDGET_AED_CURRENCY_PATTERN = r"AED|DHS|dirhams?"
CUSTOMER_OUTPUT_CURRENCY_PATTERN = r"(?:\bAED\b|درهم)"

_CUSTOMER_OUTPUT_AMOUNT_RE = re.compile(
    rf"{CUSTOMER_OUTPUT_CURRENCY_PATTERN}\s*"
    rf"(?P<prefixed>{AMOUNT_TOKEN_PATTERN})"
    rf"|(?P<suffixed>{AMOUNT_TOKEN_PATTERN})\s*"
    rf"{CUSTOMER_OUTPUT_CURRENCY_PATTERN}",
    re.IGNORECASE,
)
_CUSTOMER_OUTPUT_CURRENCY_RE = re.compile(
    CUSTOMER_OUTPUT_CURRENCY_PATTERN,
    re.IGNORECASE,
)


def canonical_amount(value: object) -> str | None:
    text = str(value if value is not None else "").strip().replace(",", "")
    if not text:
        return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if not number.is_finite():
        return None
    rendered = format(number, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def find_customer_output_amounts(text: str) -> tuple[str, ...]:
    found: list[str] = []
    for match in _CUSTOMER_OUTPUT_AMOUNT_RE.finditer(str(text or "")):
        token = match.group("prefixed") or match.group("suffixed")
        canonical = canonical_amount(token)
        if canonical is not None and canonical not in found:
            found.append(canonical)
    return tuple(found)


def contains_customer_output_currency(text: str) -> bool:
    return _CUSTOMER_OUTPUT_CURRENCY_RE.search(str(text or "")) is not None
