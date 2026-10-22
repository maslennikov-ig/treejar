"""Deterministic line, package and 5% UAE VAT arithmetic for catalog evidence.

`tj-asty.1`. The client's previous bot wrote out `Qty × Unit = Subtotal`, a
workstation-plus-chairs package total and the VAT-inclusive figure, and then
got the budget comparison wrong (5,931.45 AED called "above" a 6,000 AED
budget). Noor's answer is to never let the model do that arithmetic: the tool
evidence carries the computed figures and the budget verdict, so the reply
only restates them.

Everything here is pure. Quantities come from two sources only: a quantity the
customer wrote next to a product reference, or the team size they asked to
seat, divided by the seat count the product's own catalog *name* states.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from src.dialogue.count_words import EN_COUNT_WORD_PATTERN, count_value
from src.llm.money import amount_with_uae_vat, format_money, line_subtotal, round_money

_HOMOGLYPHS = str.maketrans(
    {
        "А": "a",
        "В": "b",
        "Е": "e",
        "К": "k",
        "М": "m",
        "Н": "h",
        "О": "o",
        "Р": "p",
        "С": "c",
        "Т": "t",
        "Х": "x",
        "а": "a",
        "в": "b",
        "е": "e",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "х": "x",
    }
)
_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_CODE_TOKEN_RE = re.compile(r"[a-z]*\d[a-z0-9]*(?:[-./][a-z0-9]+)*")
_WORD_RE = re.compile(r"[a-z0-9]+(?:[-./][a-z0-9]+)*|[^\sa-z0-9]")
_QTY_RE = re.compile(
    rf"^(?:\d{{1,4}}|{EN_COUNT_WORD_PATTERN})$",
    re.IGNORECASE,
)
_CLAUSE_BOUNDARY_RE = re.compile(r"[.;!?\n،؛]|,\s|\s(?:and|plus|also|but|or)\s")
_STOP_WORDS = frozenset(
    {
        "and",
        "or",
        "plus",
        "for",
        "in",
        "is",
        "are",
        "of",
        "the",
        "a",
        "an",
        "with",
        "to",
        "at",
        "on",
        "we",
        "i",
        "our",
        "your",
        "please",
        "each",
        "per",
        "that",
        "this",
        "it",
        "do",
        "does",
        "can",
        "would",
        "will",
        "also",
        "but",
        "if",
        "from",
        "by",
    }
)
_GENERIC_ITEM_WORDS = frozenset(
    {
        "chair",
        "chairs",
        "workstation",
        "workstations",
        "desk",
        "desks",
        "table",
        "tables",
        "unit",
        "units",
        "pcs",
        "pc",
        "piece",
        "pieces",
        "item",
        "items",
        "x",
        "×",
        "set",
        "sets",
        "model",
        "models",
        "sku",
    }
)
_NOT_ITEM_AFTER_QTY = frozenset(
    {
        "aed",
        "dhs",
        "dh",
        "dirham",
        "dirhams",
        "people",
        "persons",
        "person",
        "staff",
        "employees",
        "employee",
        "seats",
        "seat",
        "users",
        "members",
        "days",
        "weeks",
        "months",
        "years",
        "m",
        "mm",
        "cm",
        "meter",
        "meters",
        "metre",
        "metres",
        "%",
    }
)
_GENERIC_NOUN_FAMILY = {
    "chair": "seating",
    "chairs": "seating",
    "workstation": "workspace",
    "workstations": "workspace",
    "desk": "workspace",
    "desks": "workspace",
    "table": "workspace",
    "tables": "workspace",
    "unit": None,
    "units": None,
    "pcs": None,
    "pieces": None,
}
_MAX_WORDS_BETWEEN_QTY_AND_REF = 4


def _fold(text: str) -> str:
    return (
        str(text or "")
        .translate(_HOMOGLYPHS)
        .translate(_ARABIC_INDIC_DIGITS)
        .casefold()
    )


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(_fold(text))


def product_reference_keys(name: str, sku: str = "") -> tuple[str, ...]:
    """The phrases a customer would type to name this exact catalog row.

    A model code with the word before it (``luma 9719-4``, ``ch 616``) and a
    hyphenated or four-digit code on its own (``9719-4``). Plain words never
    count: ``walnut`` names a finish, not a product.
    """

    keys: list[str] = []
    for source in (name, sku):
        tokens = _words(source)
        for index, token in enumerate(tokens):
            if not _CODE_TOKEN_RE.fullmatch(token) or token.isalpha():
                continue
            if token.isdigit() and len(token) < 3:
                continue
            previous = tokens[index - 1] if index else ""
            if previous.isalpha() and len(previous) >= 2:
                keys.append(f"{previous} {token}")
            if "-" in token or (token.isdigit() and len(token) >= 4):
                keys.append(token)
    return tuple(dict.fromkeys(keys))


@dataclass(frozen=True, slots=True)
class _Occurrence:
    start: int
    end: int
    key: str


def _find_occurrences(
    folded_words: Sequence[str], keys: Iterable[str]
) -> list[_Occurrence]:
    found: list[_Occurrence] = []
    for key in keys:
        key_words = key.split()
        width = len(key_words)
        for index in range(len(folded_words) - width + 1):
            if list(folded_words[index : index + width]) == key_words:
                found.append(_Occurrence(index, index + width, key))
    found.sort(key=lambda item: (item.start, -(item.end - item.start)))
    merged: list[_Occurrence] = []
    for occurrence in found:
        if merged and occurrence.start < merged[-1].end:
            continue
        merged.append(occurrence)
    return merged


def _row_words(name: str, sku: str) -> set[str]:
    words = set(_words(f"{name} {sku}"))
    for word in list(words):
        words.update(part for part in re.split(r"[-./]", word) if part)
    return words


def _qualifiers_fit(words: Sequence[str], start: int, row_words: set[str]) -> bool:
    """Do the words right after the reference describe this row?

    ``CH 616 NEW black`` must not count toward ``CH 616 black``: every
    describing word after the code has to be in the row's own name.
    """

    for word in words[start : start + 3]:
        if word in _STOP_WORDS or _QTY_RE.match(word) or not word.isalnum():
            break
        if word in _GENERIC_ITEM_WORDS:
            continue
        if word not in row_words:
            return False
    return True


def _quantity_value(word: str) -> int | None:
    if not _QTY_RE.match(word):
        return None
    value = count_value(word)
    if value is None or not 0 < value <= 1000:
        return None
    return value


def _quantity_before(words: Sequence[str], start: int) -> int | None:
    lower = max(0, start - _MAX_WORDS_BETWEEN_QTY_AND_REF - 1)
    for index in range(start - 1, lower - 1, -1):
        word = words[index]
        if not word.isalnum() and word not in {"×"}:
            return None
        if word in {"and", "plus", "or", "but", "also"}:
            return None
        value = _quantity_value(word)
        if value is not None:
            following = words[index + 1] if index + 1 < len(words) else ""
            if following in _NOT_ITEM_AFTER_QTY:
                return None
            return value
    return None


def _quantity_after(words: Sequence[str], end: int) -> int | None:
    window = words[end : end + 5]
    for index, word in enumerate(window):
        if not word.isalnum() and word != "×":
            return None
        if word in {"x", "×"} and index + 1 < len(window):
            return _quantity_value(window[index + 1])
        value = _quantity_value(word)
        if value is not None:
            following = window[index + 1] if index + 1 < len(window) else ""
            if following in {"units", "unit", "pcs", "pieces"}:
                return value
            return None
    return None


def _generic_item_quantities(words: Sequence[str]) -> list[tuple[int, str | None]]:
    found: list[tuple[int, str | None]] = []
    for index, word in enumerate(words):
        value = _quantity_value(word)
        if value is None:
            continue
        for follower in words[index + 1 : index + 3]:
            if follower in _GENERIC_NOUN_FAMILY:
                found.append((value, _GENERIC_NOUN_FAMILY[follower]))
                break
            if not follower.isalpha() or follower in _NOT_ITEM_AFTER_QTY:
                break
    return found


def names_product(text: str, *, name: str, sku: str = "") -> bool:
    """Does the text name this exact row by its model code?

    ``LUMA 9719-4 workstation walnut, three for twelve people`` names the LUMA
    9719-4 row even though the surrounding words make a text match look partial.
    """

    words = _words(text)
    keys = product_reference_keys(name, sku)
    if not words or not keys:
        return False
    row_words = _row_words(name, sku)
    return any(
        _qualifiers_fit(words, occurrence.end, row_words)
        for occurrence in _find_occurrences(words, keys)
    )


def named_product_keys(text: str, products: Iterable[object]) -> set[str]:
    """Keys (id, else SKU) of the rows the text names by model code."""

    return {
        str(getattr(product, "id", None) or getattr(product, "sku", ""))
        for product in products
        if names_product(
            text,
            name=str(getattr(product, "name_en", "") or ""),
            sku=str(getattr(product, "sku", "") or ""),
        )
    }


def explicit_item_quantity(
    customer_text: str,
    *,
    name: str,
    sku: str = "",
    family: str | None = None,
) -> int | None:
    """The quantity the customer wrote for this exact row, or ``None``.

    ``3 workstations of SKYLAND LUMA 9719-4``, ``the 3 LUMA 9719-4
    workstations``, ``1 chair CH 616 NEW black and 3 chairs CH 460 black``. A
    message that names exactly one product and one item count elsewhere
    (``... CH 616 NEW black. I need 4 chairs.``) gives that count to it.
    """

    words = _words(customer_text)
    if not words:
        return None
    keys = product_reference_keys(name, sku)
    if not keys:
        return None
    row_words = _row_words(name, sku)
    occurrences = [
        occurrence
        for occurrence in _find_occurrences(words, keys)
        if _qualifiers_fit(words, occurrence.end, row_words)
    ]
    if not occurrences:
        return None
    for occurrence in occurrences:
        quantity = _quantity_before(words, occurrence.start)
        if quantity is None:
            quantity = _quantity_after(words, occurrence.end)
        if quantity is not None:
            return quantity
    # One product named, one item count stated elsewhere in the message.
    if len(_distinct_codes(words)) != 1:
        return None
    generic = _generic_item_quantities(words)
    if len(generic) == 1:
        value, noun_family = generic[0]
        if noun_family is None or family is None or noun_family == family:
            return value
    return None


def _distinct_codes(words: Sequence[str]) -> set[str]:
    codes: set[str] = set()
    for index, token in enumerate(words):
        if not any(char.isdigit() for char in token):
            continue
        has_code_shape = any(char.isalpha() for char in token) or "-" in token
        if not has_code_shape and not (token.isdigit() and len(token) >= 3):
            continue
        previous = words[index - 1] if index else ""
        following = words[index + 1] if index + 1 < len(words) else ""
        if previous in {",", "."} or following in _NOT_ITEM_AFTER_QTY:
            continue
        codes.add(token)
    return codes


def seat_based_units(
    requested_seats: int | None,
    *,
    family: str | None,
    name_capacity: int | None,
) -> int | None:
    """Units needed to seat the team, from the seat count the name states."""

    if requested_seats is None or requested_seats <= 0:
        return None
    if family not in {"seating", "workspace"} or not name_capacity:
        return None
    if name_capacity <= 0:
        return None
    return max(1, math.ceil(requested_seats / name_capacity))


@dataclass(frozen=True, slots=True)
class PricedLine:
    """One catalog row priced at a quantity this turn can defend."""

    sku: str
    name: str
    family: str | None
    quantity: int
    unit_price: float
    currency: str
    explicit: bool
    seats_covered: int | None = None
    stock: int | None = None

    @property
    def subtotal_excl_vat(self) -> float:
        return line_subtotal(self.quantity, self.unit_price)

    @property
    def vat_amount(self) -> float:
        return amount_with_uae_vat(self.subtotal_excl_vat)[1]

    @property
    def total_incl_vat(self) -> float:
        return amount_with_uae_vat(self.subtotal_excl_vat)[2]


def unit_price_vat_text(unit_price: float, currency: str) -> str:
    """``excl. 5% VAT; 1,977.15 AED incl. 5% VAT`` for one catalog price."""

    incl = amount_with_uae_vat(unit_price)[2]
    return f"excl. 5% VAT; {format_money(incl)} {currency} incl. 5% VAT"


def line_math_text(line: PricedLine) -> str:
    basis = (
        f"{line.quantity} unit(s) for {line.seats_covered} seat(s)"
        if line.seats_covered is not None
        else f"{line.quantity} unit(s) as requested by the customer"
    )
    text = (
        f"Verified line math ({basis}): {line.quantity} × "
        f"{format_money(line.unit_price)} {line.currency} = "
        f"{format_money(line.subtotal_excl_vat)} {line.currency} excl. 5% VAT "
        f"({format_money(line.total_incl_vat)} {line.currency} incl. 5% VAT; "
        f"5% VAT = {format_money(line.vat_amount)} {line.currency})."
    )
    if line.explicit:
        text += " The customer gave this quantity: state this subtotal in the reply."
    if line.stock is not None:
        if line.stock >= line.quantity:
            text += f" Stock check: {line.stock} in stock covers {line.quantity}."
        else:
            text += (
                f" Stock check: only {line.stock} in stock, short of {line.quantity}."
            )
    return text


def budget_check_text(
    subtotal_excl_vat: float,
    budget_cap: float | None,
    currency: str = "AED",
) -> str | None:
    """The budget verdict, computed -- never left to the model."""

    if budget_cap is None or budget_cap <= 0:
        return None
    excl, _vat, incl = amount_with_uae_vat(subtotal_excl_vat)
    cap = round_money(budget_cap)
    cap_text = f"{format_money(cap)} {currency}"
    if incl <= cap:
        return (
            f"Budget check (cap {cap_text}): FITS within budget both excl. VAT "
            f"({format_money(excl)} {currency}) and incl. 5% VAT "
            f"({format_money(incl)} {currency}); "
            f"{format_money(round_money(cap - incl))} {currency} remaining after VAT."
        )
    if excl <= cap:
        return (
            f"Budget check (cap {cap_text}): FITS excl. 5% VAT "
            f"({format_money(excl)} {currency}) but is "
            f"{format_money(round_money(incl - cap))} {currency} above the cap "
            f"once 5% VAT is added ({format_money(incl)} {currency})."
        )
    return (
        f"Budget check (cap {cap_text}): ABOVE budget by "
        f"{format_money(round_money(excl - cap))} {currency} excl. VAT "
        f"({format_money(excl)} {currency} excl. 5% VAT; "
        f"{format_money(incl)} {currency} incl. 5% VAT)."
    )


def _sum_lines(lines: Sequence[PricedLine]) -> float:
    return round_money(sum(line.subtotal_excl_vat for line in lines))


def multi_item_total_text(
    lines: Sequence[PricedLine],
    budget_cap: float | None,
) -> tuple[str, float] | None:
    """``1 × A (295.00) + 3 × B (2,403.00) = 2,698.00 excl. VAT (...)``."""

    explicit = [line for line in lines if line.explicit]
    if len({line.sku.casefold() for line in explicit}) < 2:
        return None
    currencies = {line.currency for line in explicit}
    if len(currencies) != 1:
        return None
    currency = currencies.pop()
    total = _sum_lines(explicit)
    _excl, vat, incl = amount_with_uae_vat(total)
    parts = " + ".join(
        f"{line.quantity} × {line.name} ({format_money(line.subtotal_excl_vat)} {currency})"
        for line in explicit
    )
    text = (
        "Verified multi-item total: "
        f"{parts} = {format_money(total)} {currency} excl. 5% VAT "
        f"({format_money(incl)} {currency} incl. 5% VAT; 5% VAT = "
        f"{format_money(vat)} {currency})."
    )
    check = budget_check_text(total, budget_cap, currency)
    if check:
        text += f"\n{check}"
    return text, total


def _cheapest_by_family(lines: Iterable[PricedLine], family: str) -> PricedLine | None:
    candidates = [
        line
        for line in lines
        if line.family == family
        and not line.explicit
        and line.seats_covered is not None
        and (line.stock is None or line.stock >= line.quantity)
    ]
    # A team's package seats its people at desks: visitor chairs are not the
    # chairs a workstation package is priced with.
    if family == "seating":
        candidates = [
            line for line in candidates if "visitor" not in line.name.casefold()
        ]
    if not candidates:
        return None
    return min(candidates, key=lambda line: (line.subtotal_excl_vat, line.name))


def turnkey_package_text(
    lines: Sequence[PricedLine],
    requested_seats: int | None,
    budget_cap: float | None,
) -> tuple[str, float] | None:
    """A workstation-plus-chairs package for the team, from verified rows."""

    if requested_seats is None or requested_seats <= 0:
        return None
    workspace = _cheapest_by_family(lines, "workspace")
    seating = _cheapest_by_family(lines, "seating")
    if workspace is None or seating is None or workspace.currency != seating.currency:
        return None
    currency = workspace.currency
    total = _sum_lines((workspace, seating))
    _excl, vat, incl = amount_with_uae_vat(total)
    text = (
        f"Verified turnkey package math ({requested_seats} seats): "
        f"{workspace.quantity} × {workspace.name} ({workspace.quantity} × "
        f"{format_money(workspace.unit_price)} = "
        f"{format_money(workspace.subtotal_excl_vat)} {currency}) + "
        f"{seating.quantity} × {seating.name} ({seating.quantity} × "
        f"{format_money(seating.unit_price)} = "
        f"{format_money(seating.subtotal_excl_vat)} {currency}) = "
        f"{format_money(total)} {currency} excl. 5% VAT "
        f"({format_money(incl)} {currency} incl. 5% VAT; 5% VAT = "
        f"{format_money(vat)} {currency}). This is the lowest-priced in-stock "
        "combination among the rows returned this turn."
    )
    check = budget_check_text(total, budget_cap, currency)
    if check:
        text += f"\n{check}"
    return text, total


__all__ = [
    "PricedLine",
    "budget_check_text",
    "explicit_item_quantity",
    "line_math_text",
    "multi_item_total_text",
    "named_product_keys",
    "names_product",
    "product_reference_keys",
    "seat_based_units",
    "turnkey_package_text",
    "unit_price_vat_text",
]
