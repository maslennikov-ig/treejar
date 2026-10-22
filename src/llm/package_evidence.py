"""Catalog evidence priced at a defensible quantity, per turn (`tj-asty.1`).

The pure arithmetic lives in `src.llm.package_math`; this module ties it to a
turn: which quantity the customer gave for a row, which rows were priced in the
turn, the package and multi-item totals across them, the budget verdict, and
the claim-contract rows that make those figures restatable.
"""

from __future__ import annotations

import re
from typing import Any

from src.dialogue.claim_contract import row_from_catalog_product
from src.dialogue.count_words import COUNT_PATTERN, count_value
from src.llm.catalog_planning import (
    SalesDeps,
    _catalog_budget_cap,
    _catalog_product_family,
    _requested_seat_count,
)
from src.llm.package_math import (
    PricedLine,
    budget_check_text,
    explicit_item_quantity,
    line_math_text,
    multi_item_total_text,
    seat_based_units,
    turnkey_package_text,
)
from src.models.product_links import product_canonical_url


def _normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


_NAME_SEAT_COUNT_RE = re.compile(
    rf"\b(?P<count>{COUNT_PATTERN})[\s-]+(?:person|people|seats?|seater)\b",
    re.IGNORECASE,
)


def _name_seat_capacity(name: str, family: str | None) -> int | None:
    """Seats per unit as the catalog *name* states it, never the description.

    A chair seats one. A workstation counts only when its own name says how
    many people ("Four person workstation", "6 Person Face to Face Table"):
    capacity parsed from free-text descriptions disagrees with itself too often
    to multiply by (owner decision 2026-08-05).
    """

    if family == "seating":
        return 1
    if family != "workspace":
        return None
    match = _NAME_SEAT_COUNT_RE.search(_normalize_text(name))
    if match is None:
        return None
    return count_value(match.group("count"))


def _priced_line_for_turn(
    deps: SalesDeps,
    *,
    sku: str,
    name: str,
    family: str | None,
    unit_price: float | None,
    currency: str,
    stock: int | None,
    requested_seats: int | None,
) -> PricedLine | None:
    """Price one row at a quantity the customer gave us, and remember it.

    tj-asty.1. Either the quantity the customer wrote next to this product, or
    the team size divided by the seats its name states. Anything else is a
    guess, and a guessed quantity would put a guessed total in the reply.
    """

    if unit_price is None or unit_price <= 0 or not sku.strip():
        return None
    quantity = explicit_item_quantity(
        str(deps.user_query or ""), name=name, sku=sku, family=family
    )
    explicit = quantity is not None
    seats_covered: int | None = None
    if quantity is None:
        capacity = _name_seat_capacity(name, family)
        quantity = seat_based_units(
            requested_seats, family=family, name_capacity=capacity
        )
        if quantity is None or requested_seats is None:
            return None
        seats_covered = requested_seats
    line = PricedLine(
        sku=sku.strip(),
        name=name.strip() or sku.strip(),
        family=family,
        quantity=quantity,
        unit_price=float(unit_price),
        currency=currency,
        explicit=explicit,
        seats_covered=seats_covered,
        stock=stock,
    )
    deps.turn_priced_lines[sku.strip().casefold()] = line
    return line


def _priced_line_claim_fields(
    line: PricedLine | None, *, product_url: str | None = None
) -> dict[str, object]:
    """Claim-row fields that make the line math and product page restatable."""

    fields: dict[str, object] = {"product_url": product_url} if product_url else {}
    if line is not None:
        fields.update(
            {
                "quantity": line.quantity,
                "line_subtotal_excl_vat": f"{line.subtotal_excl_vat:.2f}",
                "line_vat_amount": f"{line.vat_amount:.2f}",
                "line_total_incl_vat": f"{line.total_incl_vat:.2f}",
            }
        )
    return fields


_PACKAGE_CLAIM_SKU = "_PACKAGE_"


def _customer_seat_count(deps: SalesDeps) -> int | None:
    """The team size the customer wrote this turn, for package math only."""

    return _requested_seat_count(str(deps.user_query or ""))


def _customer_budget_cap(deps: SalesDeps) -> float | None:
    """The total budget for the budget check: the tool's, else the customer's.

    Search constraints stay the model's tool arguments. The budget *check* is
    different: it only compares a computed total with a figure the customer
    wrote ("our budget ... is 6,000 AED"), so it reads the current message and
    then the recent customer turns, newest first.
    """

    if deps.catalog_planning.budget_cap is not None:
        return float(deps.catalog_planning.budget_cap)
    texts = [str(deps.user_query or "")]
    texts.extend(
        entry.split(":", 1)[1]
        for entry in reversed(deps.recent_history or ())
        if entry.startswith("user:")
    )
    for text in texts:
        cap = _catalog_budget_cap(text)
        if cap is not None:
            return cap
    return None


def _turn_package_math_blocks(deps: SalesDeps) -> list[str]:
    """Totals across every row priced this turn, with the budget verdict."""

    lines = list(deps.turn_priced_lines.values())
    if not lines:
        return []
    budget_cap = _customer_budget_cap(deps)
    blocks: list[str] = []
    package_totals: dict[str, object] = {}
    explicit = [line for line in lines if line.explicit]
    multi = multi_item_total_text(lines, budget_cap)
    if multi is not None:
        text, total = multi
        blocks.append(text)
        package_totals["multi_item_subtotal_excl_vat"] = f"{total:.2f}"
    elif len(explicit) == 1:
        check = budget_check_text(
            explicit[0].subtotal_excl_vat, budget_cap, explicit[0].currency
        )
        if check:
            blocks.append(f"{explicit[0].quantity} × {explicit[0].name}: {check}")
    package = turnkey_package_text(
        lines,
        deps.catalog_planning.requested_seats or _customer_seat_count(deps),
        budget_cap,
    )
    if package is not None:
        text, total = package
        blocks.append(text)
        package_totals["package_subtotal_excl_vat"] = f"{total:.2f}"
    if package_totals:
        deps.claim_rows[_PACKAGE_CLAIM_SKU] = row_from_catalog_product(
            sku=_PACKAGE_CLAIM_SKU,
            attributes=None,
            extras={**package_totals, "price": next(iter(package_totals.values()))},
        )
    return blocks


def enrich_stock_answer(
    deps: SalesDeps,
    *,
    sku: str,
    catalog_product: Any | None,
    zoho_name: str,
    unit_price: float,
    currency: str,
    available: int,
) -> str:
    """Product page, line math and package totals appended to a stock answer."""

    extra: list[str] = []
    stock_name = str(getattr(catalog_product, "name_en", "") or "") or zoho_name or sku
    canonical_url = (
        product_canonical_url(catalog_product) if catalog_product is not None else None
    )
    if canonical_url:
        extra.append(f"Product page: {canonical_url}")
    priced_line = _priced_line_for_turn(
        deps,
        sku=sku,
        name=stock_name,
        family=_catalog_product_family(stock_name),
        unit_price=unit_price,
        currency=currency,
        stock=available,
        requested_seats=None,
    )
    if priced_line is not None:
        extra.append(line_math_text(priced_line))
        existing_row = deps.claim_rows.get(sku)
        merged_fields: dict[str, object] = (
            dict(existing_row.fields) if existing_row is not None else {}
        )
        merged_fields.setdefault("price", unit_price)
        merged_fields.setdefault("currency", currency)
        merged_fields.update(_priced_line_claim_fields(priced_line))
        deps.claim_rows[sku] = row_from_catalog_product(
            sku=sku,
            attributes=getattr(catalog_product, "attributes", None),
            extras=merged_fields,
        )
    extra.extend(_turn_package_math_blocks(deps))
    return "".join(f"\n{line}" for line in extra)


__all__ = [
    "enrich_stock_answer",
    "_customer_seat_count",
    "_priced_line_claim_fields",
    "_priced_line_for_turn",
    "_turn_package_math_blocks",
]
