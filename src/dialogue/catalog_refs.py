from __future__ import annotations

import inspect
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from src.models.product import Product

_HOMOGLYPHS = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "а": "A",
        "в": "B",
        "е": "E",
        "к": "K",
        "м": "M",
        "н": "H",
        "о": "O",
        "р": "P",
        "с": "C",
        "т": "T",
        "х": "X",
    }
)

_NUMERIC_SKU_RE = re.compile(r"\b\d{2}-\d{6,}\b")
_ALPHA_SKU_RE = re.compile(
    r"\b(?P<prefix>[A-ZА-Я]{2,3})[-\s]?(?P<number>\d+(?:\.\d+)?[A-ZА-Я]?)\b",
    re.IGNORECASE,
)
_MODEL_RE = re.compile(r"\bSKYLAND\s+NOVO\s+\d+\b", re.IGNORECASE)
_NORMALIZED_ALPHA_RE = re.compile(
    r"^(?P<prefix>[A-Z]{2,3})[-\s]?(?P<number>\d+(?:\.\d+)?[A-Z]?)$"
)
_ALPHA_SKU_PREFIX_STOPWORDS = frozenset(
    {
        "AND",
        "ARE",
        "BUT",
        "BUY",
        "FOR",
        "GET",
        "HAS",
        "NEED",
        "NEW",
        "ONLY",
        "OR",
        "THE",
        "WANT",
    }
)
_QUANTITY_WORDS = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
    "SIX": 6,
    "SEVEN": 7,
    "EIGHT": 8,
    "NINE": 9,
    "TEN": 10,
}


@dataclass(frozen=True)
class CatalogParsedRef:
    raw: str
    normalized: str
    quantity: int | None = None
    start: int | None = None
    end: int | None = None


@dataclass(frozen=True)
class CatalogResolvedRef:
    raw: str
    normalized: str
    sku: str | None
    product: Any | None
    matched_by: str | None


@dataclass(frozen=True)
class CatalogReferenceIndex:
    by_sku: dict[str, Any]
    by_name: dict[str, Any]

    @classmethod
    def from_products(cls, products: Iterable[Any]) -> CatalogReferenceIndex:
        by_sku: dict[str, Any] = {}
        by_name: dict[str, Any] = {}
        for product in products:
            if not getattr(product, "is_active", True):
                continue
            sku = _text_attr(product, "sku")
            if sku:
                for variant in lookup_variants(sku):
                    by_sku.setdefault(variant, product)
            name = _text_attr(product, "name_en")
            if name:
                by_name.setdefault(normalize_catalog_ref(name), product)
        return cls(by_sku=by_sku, by_name=by_name)


def normalize_catalog_ref(raw: str) -> str:
    value = _normalize_text(raw)
    if _NUMERIC_SKU_RE.fullmatch(value):
        return value

    alpha_match = _NORMALIZED_ALPHA_RE.fullmatch(value)
    if alpha_match:
        return f"{alpha_match.group('prefix')}-{alpha_match.group('number')}"

    return value


def lookup_variants(raw: str) -> list[str]:
    normalized = normalize_catalog_ref(raw)
    variants = [normalized]

    alpha_match = _NORMALIZED_ALPHA_RE.fullmatch(normalized)
    if alpha_match:
        prefix = alpha_match.group("prefix")
        number = alpha_match.group("number")
        variants.extend([f"{prefix}{number}", f"{prefix} {number}"])
    elif _NUMERIC_SKU_RE.fullmatch(normalized):
        variants.append(normalized.replace("-", ""))

    return _unique(variants)


def parse_catalog_reference(text: str) -> CatalogParsedRef:
    refs = extract_catalog_references(text)
    if refs:
        return refs[0]
    return CatalogParsedRef(raw=text.strip(), normalized=normalize_catalog_ref(text))


def extract_catalog_references(text: str) -> list[CatalogParsedRef]:
    normalized_text = text.translate(_HOMOGLYPHS)
    matches: list[tuple[int, int, str, re.Match[str] | None]] = []
    for pattern in (_MODEL_RE, _NUMERIC_SKU_RE, _ALPHA_SKU_RE):
        for match in pattern.finditer(normalized_text):
            if pattern is _ALPHA_SKU_RE:
                prefix = match.group("prefix").translate(_HOMOGLYPHS).upper()
                if prefix in _ALPHA_SKU_PREFIX_STOPWORDS:
                    continue
            matches.append(
                (
                    match.start(),
                    match.end(),
                    text[match.start() : match.end()],
                    match,
                )
            )

    refs: list[CatalogParsedRef] = []
    occupied: list[tuple[int, int]] = []
    for start, end, raw, _ in sorted(
        matches, key=lambda item: (item[0], -(item[1] - item[0]))
    ):
        if any(
            start < taken_end and end > taken_start
            for taken_start, taken_end in occupied
        ):
            continue
        occupied.append((start, end))
        refs.append(
            CatalogParsedRef(
                raw=raw,
                normalized=normalize_catalog_ref(raw),
                quantity=_quantity_before_ref(normalized_text, start)
                or _quantity_after_ref(normalized_text, end),
                start=start,
                end=end,
            )
        )
    return refs


def resolve_catalog_references(
    refs: Iterable[str | CatalogParsedRef], index: CatalogReferenceIndex
) -> list[CatalogResolvedRef]:
    resolved: list[CatalogResolvedRef] = []
    for ref in refs:
        parsed = (
            ref if isinstance(ref, CatalogParsedRef) else parse_catalog_reference(ref)
        )
        product = _find_by_variants(parsed.raw, index.by_sku)
        matched_by = "sku"
        if product is None:
            product = _find_unique_by_sku_stem(parsed.raw, index.by_sku)
            matched_by = "sku" if product is not None else ""
        if product is not None:
            resolved.append(
                CatalogResolvedRef(
                    raw=parsed.raw,
                    normalized=parsed.normalized,
                    sku=_text_attr(product, "sku"),
                    product=product,
                    matched_by=matched_by,
                )
            )
            continue

        product = index.by_name.get(parsed.normalized)
        if product is not None:
            resolved.append(
                CatalogResolvedRef(
                    raw=parsed.raw,
                    normalized=parsed.normalized,
                    sku=_text_attr(product, "sku"),
                    product=product,
                    matched_by="name",
                )
            )
            continue

        resolved.append(
            CatalogResolvedRef(
                raw=parsed.raw,
                normalized=parsed.normalized,
                sku=None,
                product=None,
                matched_by=None,
            )
        )
    return resolved


async def resolve_catalog_references_from_db(
    refs: Iterable[str | CatalogParsedRef], session: Any
) -> list[CatalogResolvedRef]:
    result = session.execute(select(Product).where(Product.is_active.is_(True)))
    if inspect.isawaitable(result):
        result = await result
    products = result.scalars().all()
    index = CatalogReferenceIndex.from_products(products)
    return resolve_catalog_references(refs, index)


def _find_by_variants(raw: str, products_by_variant: dict[str, Any]) -> Any | None:
    for variant in lookup_variants(raw):
        product = products_by_variant.get(variant)
        if product is not None:
            return product
    return None


def _sku_stem(raw: str) -> str | None:
    normalized = normalize_catalog_ref(raw)
    match = re.match(
        r"^(?P<prefix>[A-Z]{2,3})[-\s]?(?P<number>\d+(?:\.\d+)?[A-Z]?)", normalized
    )
    if match is None:
        return None
    return f"{match.group('prefix')}{match.group('number')}"


def _find_unique_by_sku_stem(
    raw: str,
    products_by_variant: dict[str, Any],
) -> Any | None:
    stem = _sku_stem(raw)
    if stem is None:
        return None

    matches: dict[str, Any] = {}
    for variant, product in products_by_variant.items():
        if _sku_stem(variant) != stem:
            continue
        sku = _text_attr(product, "sku")
        if not sku:
            continue
        matches.setdefault(sku, product)

    if len(matches) != 1:
        return None
    return next(iter(matches.values()))


def _normalize_text(raw: str) -> str:
    value = raw.translate(_HOMOGLYPHS).strip().upper()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*-\s*", "-", value)
    return value


def _text_attr(item: Any, attr: str) -> str | None:
    value = getattr(item, attr, None)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _quantity_before_ref(normalized_text: str, ref_start: int) -> int | None:
    prefix = normalized_text[max(0, ref_start - 32) : ref_start]
    match = re.search(
        r"(?:^|[^A-Z0-9])(?P<qty>\d{1,3}|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)"
        r"(?:\s+(?:X|PCS?|PIECES?|UNITS?|POSITIONS?|POINTS?))?\s*$",
        prefix,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    raw_quantity = match.group("qty").upper()
    quantity: int | None
    if raw_quantity.isdigit():
        quantity = int(raw_quantity)
    else:
        quantity = _QUANTITY_WORDS.get(raw_quantity)
    if quantity is None or quantity <= 0:
        return None
    return quantity


def _quantity_after_ref(normalized_text: str, ref_end: int) -> int | None:
    suffix = normalized_text[ref_end : ref_end + 32]
    match = re.search(
        r"^(?:\s+(?!(?:AND|OR|PLUS|WITH)\b)[A-Z][A-Z0-9-]{1,20}){0,4}"
        r"\s+(?P<qty>\d{1,3}|ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN)"
        r"\s+(?:X|PCS?|PIECES?|UNITS?|POSITIONS?|POINTS?)\b",
        suffix,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    raw_quantity = match.group("qty").upper()
    quantity = (
        int(raw_quantity)
        if raw_quantity.isdigit()
        else _QUANTITY_WORDS.get(raw_quantity)
    )
    if quantity is None or quantity <= 0:
        return None
    return quantity


def _unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
