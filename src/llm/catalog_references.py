"""Direct catalog lookup for SKU references a customer names.

SKU spelling normalization, exact and stem lookups, and the named-reference
resolution search_products uses so an item named by code is found whatever its
vector-search visibility (tj-uz6j.4).
"""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.dialogue.catalog_refs import extract_catalog_references
from src.llm.catalog_planning import _SKU_HOMOGLYPH_TRANSLATION
from src.models.product import Product
from src.schemas.product import ProductRead, ProductSearchResult

logger = logging.getLogger(__name__)

CatalogSkuLookup = Callable[[AsyncSession, str], Awaitable[Any | None]]


def _normalize_sku_homoglyphs(text: str) -> str:
    return text.translate(_SKU_HOMOGLYPH_TRANSLATION)


def _canonicalize_sku_signal(value: str) -> str:
    normalized = " ".join(_normalize_sku_homoglyphs(value).split()).strip().upper()
    compact_match = re.fullmatch(r"([A-Z]{1,4})[-\s]?(\d{2,8})", normalized)
    if compact_match:
        return f"{compact_match.group(1)}-{compact_match.group(2)}"
    return re.sub(r"\s+", "-", normalized)


def _sku_lookup_variants(value: str) -> tuple[str, ...]:
    normalized = " ".join(_normalize_sku_homoglyphs(value).split()).strip().upper()
    if not normalized:
        return ()

    variants: list[str] = []

    def add(candidate: str) -> None:
        candidate = candidate.strip().upper()
        if candidate and candidate not in variants:
            variants.append(candidate)

    add(normalized)
    add(_canonicalize_sku_signal(normalized))

    tokens = re.findall(r"[A-Z0-9]+", normalized)
    if len(tokens) >= 2 and any(
        any(char.isdigit() for char in token) for token in tokens
    ):
        add("-".join(tokens))
        add(" ".join(tokens))
        add("".join(tokens))

    add(normalized.replace("-", " "))
    add(normalized.replace(" ", "-"))
    add(re.sub(r"[^A-Z0-9]+", "", normalized))

    # A customer types "ch616"; the catalog stores "CH 616". Splitting a run of
    # letters from the digits that follow it recovers the spaced and hyphenated
    # forms, which the token pass above cannot because there is nothing to
    # tokenise. Found 2026-08-09 on the realistic set: "hi do u have ch616 in
    # black" reached "I don't have live stock information for CH616".
    for chunk in re.finditer(r"\b([A-Z]{1,4})(\d{2,5})\b", normalized):
        letters, digits = chunk.group(1), chunk.group(2)
        add(f"{letters} {digits}")
        add(f"{letters}-{digits}")
    return tuple(variants)


_LATIN_TO_CYRILLIC_SKU_PREFIX = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "C": "С",
        "E": "Е",
        "H": "Н",
        "K": "К",
        "M": "М",
        "O": "О",
        "P": "Р",
        "T": "Т",
        "X": "Х",
    }
)


def _cyrillic_sku_prefix_variant(variant: str) -> str | None:
    """Spell a Latin SKU prefix the way Cyrillic catalogue rows store it."""
    match = re.match(r"^([A-Z]{2,4})(?=[-\s]?\d)", variant)
    if match is None:
        return None
    prefix = match.group(1)
    if any(char not in "ABCEHKMOPTX" for char in prefix):
        return None
    return prefix.translate(_LATIN_TO_CYRILLIC_SKU_PREFIX) + variant[len(prefix) :]


def _sku_stem(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(_normalize_sku_homoglyphs(value).split()).strip().upper()
    match = re.match(r"^(?P<prefix>[A-Z]{2,4})[-\s]?(?P<number>\d{2,8})", normalized)
    if match is None:
        return None
    return f"{match.group('prefix')}{match.group('number')}"


async def _find_catalog_products_by_sku_stem(
    db: AsyncSession,
    sku: str,
) -> list[Any]:
    stem = _sku_stem(sku)
    if stem is None:
        return []
    number_match = re.search(r"\d{2,8}", stem)
    if number_match is None:
        return []

    result = await db.execute(
        select(Product).where(
            Product.is_active.is_(True),
            func.lower(Product.sku).contains(number_match.group(0).casefold()),
        )
    )
    products = list(result.scalars().all())
    matches: dict[str, Any] = {}
    for product in products:
        product_sku = getattr(product, "sku", None)
        if not isinstance(product_sku, str) or not product_sku.strip():
            continue
        if _sku_stem(product_sku) != stem:
            continue
        matches.setdefault(product_sku, product)

    return list(matches.values())


_QUERY_REFERENCE_BOUNDARY_RE = re.compile(r"[,;/&+]|\b(?:and|or|plus)\b", re.I)
_QUERY_REFERENCE_MAX_PRODUCTS = 3
_ALPHA_QUERY_REFERENCE_RE = re.compile(r"^[A-Z]{2,4}-\d")
_NUMERIC_QUERY_REFERENCE_RE = re.compile(r"^\d{2}-\d{6,}$")


@dataclass(frozen=True)
class _QueryCatalogResolution:
    products: tuple[Any, ...] = ()
    unresolved_references: tuple[str, ...] = ()


def _sku_detail_tokens(sku: str) -> tuple[str, ...]:
    """Words a SKU carries after its stem: "CH 616 NEW black" -> NEW, BLACK."""
    normalized = " ".join(_normalize_sku_homoglyphs(sku).split()).strip().upper()
    match = re.match(r"^[A-Z]{2,4}[-\s]?\d{2,8}", normalized)
    tail = normalized[match.end() :] if match else normalized
    return tuple(re.findall(r"[A-Z0-9]+", tail))


def _select_most_specific_sku_products(
    products: Sequence[Any],
    detail_text: str,
) -> list[Any]:
    """Pick the rows whose SKU details the customer actually stated.

    "CH 616 NEW black" names both "CH 616 black" and "CH 616 NEW black" by
    stem; only rows whose every SKU word appears in the text qualify, and the
    one matching the most stated words wins, so the NEW row beats its sibling.
    """
    stated = set(
        re.findall(
            r"[A-Z0-9]+",
            _normalize_sku_homoglyphs(detail_text).upper(),
        )
    )
    scored: list[tuple[int, Any]] = []
    for product in products:
        details = _sku_detail_tokens(str(getattr(product, "sku", "") or ""))
        if all(token in stated for token in details):
            scored.append((len(details), product))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    return [product for score, product in scored if score == best]


def _product_reads_for_resolved_references(
    products: Sequence[Any],
) -> list[ProductRead]:
    reads: list[ProductRead] = []
    for product in products:
        try:
            reads.append(ProductRead.model_validate(product))
        except ValidationError:
            logger.warning(
                "Skipping unreadable catalog row for SKU %r",
                getattr(product, "sku", None),
            )
    return reads


def _lead_with_resolved_references(
    results: ProductSearchResult,
    resolved_reference_products: Sequence[ProductRead],
    query: str,
    max_results: int,
) -> ProductSearchResult:
    """Put the directly resolved rows first and fill the rest from vector search."""
    resolved_reference_skus = {
        product.sku.strip().casefold() for product in resolved_reference_products
    }
    vector_fill = [
        product
        for product in results.products
        if str(product.sku).strip().casefold() not in resolved_reference_skus
    ][: max(max_results - len(resolved_reference_products), 0)]
    return ProductSearchResult(
        products=[*resolved_reference_products, *vector_fill],
        query_interpreted=query,
        total_found=len(resolved_reference_products) + len(vector_fill),
    )


async def _resolve_query_catalog_references(
    db: AsyncSession,
    query: str,
    find_product_by_sku: CatalogSkuLookup | None = None,
) -> _QueryCatalogResolution:
    """Resolve SKU references named in a search query by direct catalog lookup.

    Vector search only returns in-stock rows, so an item the customer names by
    code can vanish from search_products the moment its local stock reads zero
    (tj-uz6j.4: "CH 616 NEW black" was found by get_stock and then reported as
    unconfirmed). A named code is looked up directly instead, whatever its stock.
    """
    lookup = find_product_by_sku or find_catalog_product_by_sku
    references = [
        reference
        for reference in extract_catalog_references(query)
        if _ALPHA_QUERY_REFERENCE_RE.match(reference.normalized)
        or _NUMERIC_QUERY_REFERENCE_RE.match(reference.normalized)
    ]
    if not references:
        return _QueryCatalogResolution()

    resolved: dict[str, Any] = {}
    unresolved: list[str] = []
    for index, reference in enumerate(references):
        start = reference.start if reference.start is not None else 0
        end = reference.end if reference.end is not None else len(query)
        next_start = (
            references[index + 1].start
            if index + 1 < len(references) and references[index + 1].start is not None
            else len(query)
        )
        window = query[end:next_start]
        boundary = _QUERY_REFERENCE_BOUNDARY_RE.search(window)
        if boundary is not None:
            window = window[: boundary.start()]
        detail_text = f"{query[start:end]} {window}"

        matches: list[Any]
        try:
            if _NUMERIC_QUERY_REFERENCE_RE.match(reference.normalized):
                product = await lookup(db, reference.raw)
                matches = [product] if product is not None else []
                stem_found = bool(matches)
            else:
                stem_products = await _find_catalog_products_by_sku_stem(
                    db, reference.raw
                )
                stem_found = bool(stem_products)
                matches = _select_most_specific_sku_products(
                    [
                        product
                        for product in stem_products
                        if getattr(product, "is_active", True) is not False
                    ],
                    detail_text,
                )
        except Exception:
            logger.warning(
                "Direct catalog lookup failed for search reference %r",
                reference.raw,
                exc_info=True,
            )
            continue
        if not stem_found:
            unresolved.append(" ".join(detail_text.split()))
        for product in matches[:_QUERY_REFERENCE_MAX_PRODUCTS]:
            sku = getattr(product, "sku", None)
            if isinstance(sku, str) and sku.strip():
                resolved.setdefault(sku.strip().casefold(), product)

    return _QueryCatalogResolution(
        products=tuple(resolved.values()),
        unresolved_references=tuple(dict.fromkeys(unresolved)),
    )


async def find_catalog_product_by_sku(db: AsyncSession, sku: str) -> Any | None:
    """Exact catalog row for a SKU, trying Latin and Cyrillic spellings."""
    variants = _sku_lookup_variants(sku)
    if not variants:
        return None

    variant_priority: dict[str, int] = {}
    for variant in variants:
        variant_priority.setdefault(variant.casefold(), len(variant_priority))
    # The variants are folded onto Latin, but the comparison runs against the
    # stored SKU, and some catalogue rows spell their prefix in Cyrillic
    # ("СН 135 black"). Without the Cyrillic spelling a customer typing "CH 135
    # black" can never reach that row through this exact lookup.
    for variant in variants:
        cyrillic_variant = _cyrillic_sku_prefix_variant(variant)
        if cyrillic_variant is not None:
            variant_priority.setdefault(
                cyrillic_variant.casefold(), len(variant_priority)
            )
    result = await db.execute(
        select(Product)
        .where(func.lower(Product.sku).in_(variant_priority))
        .order_by(
            case(
                variant_priority,
                value=func.lower(Product.sku),
                else_=len(variant_priority),
            )
        )
        .limit(1)
    )
    product = result.scalar_one_or_none()
    if product is None or not isinstance(getattr(product, "sku", None), str):
        return None
    return product
