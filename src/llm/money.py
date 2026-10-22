"""Shared parsing primitives for customer-facing money amounts."""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

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

BUDGET_AR_CURRENCY_PATTERN = rf"درهم|{BUDGET_AED_CURRENCY_PATTERN}"
"""The same, after an Arabic budget word (`tj-asty.1`)."""

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


# `tj-asty.1`. Treejar catalog prices exclude UAE VAT (`priceExclVAT`). The
# rate lives here, once, so the tool evidence, the claim contract and the
# budget check all derive the VAT-inclusive figure the same way and to the same
# cent. Decimal with half-up rounding is what an invoice does; binary floats
# would round 5,931.445 either way depending on representation.
UAE_VAT_RATE = Decimal("0.05")
UAE_VAT_MULTIPLIER = Decimal("1.05")
_CENT = Decimal("0.01")


def _to_decimal(amount: float | int | Decimal | str) -> Decimal:
    if isinstance(amount, Decimal):
        return amount
    return Decimal(str(amount))


def round_money(amount: float | int | Decimal | str) -> float:
    """Round a money amount to the cent, half-up, as an invoice does."""

    return float(_to_decimal(amount).quantize(_CENT, rounding=ROUND_HALF_UP))


def amount_with_uae_vat(
    amount: float | int | Decimal | str,
) -> tuple[float, float, float]:
    """Return ``(excl_vat, vat_amount, incl_vat)`` rounded to the cent.

    ``incl_vat`` is always ``excl_vat + vat_amount`` exactly, so the three
    figures a reply restates can never disagree with one another.
    """

    excl = _to_decimal(amount).quantize(_CENT, rounding=ROUND_HALF_UP)
    vat = (excl * UAE_VAT_RATE).quantize(_CENT, rounding=ROUND_HALF_UP)
    return float(excl), float(vat), float(excl + vat)


def line_subtotal(quantity: int, unit_price: float | int | Decimal | str) -> float:
    """``quantity × unit_price`` to the cent, without float drift."""

    return round_money(_to_decimal(unit_price) * Decimal(int(quantity)))


def format_money(amount: float | int | Decimal | str) -> str:
    """Render ``5931.45`` as ``5,931.45`` -- the form the tool evidence uses."""

    return f"{round_money(amount):,.2f}"
