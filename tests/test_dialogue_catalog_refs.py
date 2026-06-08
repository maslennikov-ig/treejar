from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.dialogue.catalog_refs import (
    CatalogReferenceIndex,
    CatalogResolvedRef,
    extract_catalog_references,
    lookup_variants,
    normalize_catalog_ref,
    parse_catalog_reference,
    resolve_catalog_references,
)


def test_normalize_catalog_ref_handles_sku_spacing_and_cyrillic_homoglyphs() -> None:
    assert normalize_catalog_ref("CH-616") == "CH-616"
    assert normalize_catalog_ref("CH 616") == "CH-616"
    assert normalize_catalog_ref("CH616") == "CH-616"
    assert normalize_catalog_ref("СН 616") == "CH-616"
    assert normalize_catalog_ref("CP-2.1S") == "CP-2.1S"
    assert normalize_catalog_ref("00-07024023") == "00-07024023"
    assert normalize_catalog_ref("skyland novo 2400") == "SKYLAND NOVO 2400"


def test_lookup_variants_include_compact_spaced_and_hyphenated_forms() -> None:
    variants = lookup_variants("СН 616")

    assert variants[:3] == ["CH-616", "CH616", "CH 616"]
    assert len(variants) == len(set(variants))


def test_parse_catalog_reference_identifies_model_number_as_ref_not_quantity() -> None:
    parsed = parse_catalog_reference("Need SKYLAND NOVO 2400 desks")

    assert parsed.normalized == "SKYLAND NOVO 2400"
    assert parsed.raw == "SKYLAND NOVO 2400"
    assert parsed.quantity is None


def test_extract_catalog_references_captures_quantity_before_sku() -> None:
    refs = extract_catalog_references("I need 6 CH 616 and two CP-2.1S")

    assert [(ref.normalized, ref.quantity) for ref in refs] == [
        ("CH-616", 6),
        ("CP-2.1S", 2),
    ]


def test_extract_catalog_references_preserves_multi_item_quantities() -> None:
    refs = extract_catalog_references(
        "I need 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs"
    )

    assert [(ref.normalized, ref.quantity) for ref in refs] == [
        ("SKYLAND NOVO 2400", 2),
        ("CH-616", 4),
    ]


def test_extract_catalog_references_rejects_connector_or_as_sku() -> None:
    refs = extract_catalog_references("I need 2 CH 616 or 4 CH 620")

    assert [(ref.normalized, ref.quantity) for ref in refs] == [
        ("CH-616", 2),
        ("CH-620", 4),
    ]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("4 position CH 616 chairs", [("CH-616", 4)]),
        ("Only SKYLAND NOVO 2400 2 position", [("SKYLAND NOVO 2400", 2)]),
    ],
)
def test_extract_catalog_references_accepts_position_quantity_phrases(
    text: str,
    expected: list[tuple[str, int]],
) -> None:
    refs = extract_catalog_references(text)

    assert [(ref.normalized, ref.quantity) for ref in refs] == expected


def test_extract_catalog_references_finds_supported_sku_and_model_refs() -> None:
    refs = extract_catalog_references(
        "Quote CH616, CP-2.1S, 00-07024023 and SKYLAND NOVO 2400 please"
    )

    assert [ref.normalized for ref in refs] == [
        "CH-616",
        "CP-2.1S",
        "00-07024023",
        "SKYLAND NOVO 2400",
    ]


def test_resolve_catalog_references_prefers_sku_over_model_name() -> None:
    products = [
        SimpleNamespace(sku="CH-616", name_en="Chair 616", is_active=True),
        SimpleNamespace(sku="NOVO-2400", name_en="SKYLAND NOVO 2400", is_active=True),
        SimpleNamespace(sku="OLD-616", name_en="CH 616 legacy name", is_active=True),
    ]
    index = CatalogReferenceIndex.from_products(products)

    resolved = resolve_catalog_references(["СН 616", "skyland novo 2400"], index)

    assert resolved == [
        CatalogResolvedRef(
            raw="СН 616",
            normalized="CH-616",
            sku="CH-616",
            product=products[0],
            matched_by="sku",
        ),
        CatalogResolvedRef(
            raw="skyland novo 2400",
            normalized="SKYLAND NOVO 2400",
            sku="NOVO-2400",
            product=products[1],
            matched_by="name",
        ),
    ]


def test_resolve_catalog_references_matches_unique_suffix_sku() -> None:
    products = [
        SimpleNamespace(
            sku="CH 616 NEW black",
            name_en="Skyland Operative Chair CH 616 NEW black",
            is_active=True,
        ),
        SimpleNamespace(
            sku="CH 620 black",
            name_en="Skyland Operative Chair CH 620 black",
            is_active=True,
        ),
    ]
    index = CatalogReferenceIndex.from_products(products)

    resolved = resolve_catalog_references(
        ["CH 616", "CH-616", "CH616", "СН 616"], index
    )

    assert [item.sku for item in resolved] == ["CH 616 NEW black"] * 4
    assert all(item.matched_by == "sku" for item in resolved)


def test_resolve_catalog_references_returns_unresolved_without_crashing() -> None:
    index = CatalogReferenceIndex.from_products([])

    resolved = resolve_catalog_references(["UNKNOWN 123"], index)

    assert resolved == [
        CatalogResolvedRef(
            raw="UNKNOWN 123",
            normalized="UNKNOWN 123",
            sku=None,
            product=None,
            matched_by=None,
        )
    ]


@pytest.mark.asyncio
async def test_optional_async_db_resolver_uses_product_rows_when_available() -> None:
    from src.dialogue.catalog_refs import resolve_catalog_references_from_db

    products = [
        SimpleNamespace(sku="00-07024023", name_en="Rectangular operative table")
    ]
    session = SimpleNamespace(execute=lambda _: _ScalarResult(products))

    resolved = await resolve_catalog_references_from_db(["00-07024023"], session)

    assert resolved[0].sku == "00-07024023"


class _ScalarResult:
    def __init__(self, products: list[SimpleNamespace]) -> None:
        self._products = products

    def scalars(self) -> _ScalarResult:
        return self

    def all(self) -> list[SimpleNamespace]:
        return self._products
