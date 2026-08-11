"""Shared parsing primitives for customer-facing money amounts."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

AMOUNT_TOKEN_PATTERN = r"\d[\d,]*(?:\.\d+)?"

# Four spellings of the same currency, and they are deliberately not one.
#
# `tj-rt7w.3` brought the budget and customer-output vocabularies here and left
# two more behind; `tj-rt7w.12` brings those. Merging them would be a behaviour
# change, not a tidy-up: each was widened for its own call site, and a pattern
# that reads a customer's budget too eagerly and one that decides whether a
# reply quotes a price fail in opposite directions. What they must not do is
# live in four files, where the divergence is invisible and nobody can say
# whether it was meant.
BUDGET_AED_CURRENCY_PATTERN = r"AED|DHS|dirhams?"
"""What a customer might type when naming a budget. Read as intent, not fact."""

CUSTOMER_OUTPUT_CURRENCY_PATTERN = r"(?:\bAED\b|درهم)"
"""What we ourselves write. Narrow on purpose: grounding checks every match."""

SKU_FOLLOWING_CURRENCY_PATTERN = r"(?:aed|dhs?|dirhams?|dirham|درهم|د\.إ)"
"""Anything that can follow a SKU. The widest, and the only one with `د.إ`."""

PRICE_SIGNAL_CURRENCY_PATTERN = r"\b(?:aed|dirhams?|dhs?)\b|درهم"
"""Whether a reply carries a price at all. Presence only, never an amount."""

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
