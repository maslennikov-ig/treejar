"""The catalogue is written with Cyrillic lookalikes, so folding them is load-bearing.

This is not about a customer typing on a Russian keyboard. No real customer ever
has: of 69 real-customer conversations in production, zero contain Cyrillic
(tj-4e5j.2). The Cyrillic is on *our* side. Measured in production 2026-08-08
over 920 products:

    7 SKUs begin with Cyrillic "СН"  -- Skyland chairs, e.g. "СН 135 black"
    132 name_en values use Cyrillic "х" as the dimension separator, "1000х500х754"
    distinct Cyrillic characters present: Н А М х С Т

A customer typing Latin "CH 135" only reaches SKU "СН 135" because these maps
exist. tj-4e5j removed them on the reasoning that no customer writes Russian --
true, and beside the point. These tests exist so the next removal fails loudly.
"""

from __future__ import annotations

import pytest

from src.dialogue.catalog_refs import normalize_catalog_ref

# Left column is spelled with Cyrillic С/Н/А/В/Т/Х, as the Zoho catalogue spells
# them; right column is what a customer types on an English keyboard.
CATALOGUE_SPELLINGS = [
    ("СН 135", "CH-135"),
    ("СН-145", "CH-145"),
    ("СН 460", "CH-460"),
    ("СН 620", "CH-620"),
    ("АВ-100", "AB-100"),
    ("ТХ 50", "TX-50"),
]


@pytest.mark.parametrize(("catalogue_spelling", "expected"), CATALOGUE_SPELLINGS)
def test_cyrillic_catalogue_skus_normalise_onto_their_latin_form(
    catalogue_spelling: str, expected: str
) -> None:
    assert normalize_catalog_ref(catalogue_spelling) == expected


@pytest.mark.parametrize(("catalogue_spelling", "expected"), CATALOGUE_SPELLINGS)
def test_a_customer_typing_latin_reaches_the_cyrillic_catalogue_row(
    catalogue_spelling: str, expected: str
) -> None:
    """Both spellings must land on one key, or the lookup misses the product."""
    latin_typed = expected.replace("-", " ")

    assert normalize_catalog_ref(latin_typed) == normalize_catalog_ref(
        catalogue_spelling
    )


def test_the_engine_and_the_catalog_module_agree_on_the_folding() -> None:
    """Two modules carry the map. They must not drift apart."""
    from src.llm.engine import _normalize_sku_homoglyphs

    for catalogue_spelling, expected in CATALOGUE_SPELLINGS:
        folded = _normalize_sku_homoglyphs(catalogue_spelling).upper().replace(" ", "-")
        assert folded == expected, catalogue_spelling
