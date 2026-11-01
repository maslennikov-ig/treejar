from __future__ import annotations

import pytest

from src.core.text_utils import (
    ARABIC_INDIC_DIGITS,
    SKU_HOMOGLYPH_TRANSLATION,
    normalize_sku_homoglyphs,
    normalize_text,
    phone_digits,
    translate_arabic_indic_digits,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  Hello   WORLD \n\t Treejar  ", "hello world treejar"),
        ("СН  135\tBLACK", "сн 135 black"),
        ("Straße", "strasse"),
        ("   ", ""),
        ("", ""),
    ],
)
def test_normalize_text_casefolds_and_collapses_whitespace(
    raw: str, expected: str
) -> None:
    assert normalize_text(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+971 (50) 123-4567", "971501234567"),
        ("050 987 6543", "0509876543"),
        ("٠٥٠١٢٣٤٥٦٧", "٠٥٠١٢٣٤٥٦٧"),
        ("no-digits", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_phone_digits_extracts_digits_and_handles_none(
    raw: str | None, expected: str
) -> None:
    assert phone_digits(raw) == expected


def test_arabic_indic_digit_translation_preserves_separators() -> None:
    raw = "Budget ١٢,٥٠٠.٧٥ AED for ٢٤ chairs"
    expected = "Budget 12,500.75 AED for 24 chairs"
    assert translate_arabic_indic_digits(raw) == expected
    assert raw.translate(ARABIC_INDIC_DIGITS) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("СН 135 black", "CH 135 black"),
        ("1000х500х754", "1000x500x754"),
        ("АВЕКМНОРСТХУ-авекмнорстху", "ABEKMHOPCTXY-abekmhopctxy"),
    ],
)
def test_normalize_sku_homoglyphs_preserves_case(raw: str, expected: str) -> None:
    assert normalize_sku_homoglyphs(raw) == expected
    assert raw.translate(SKU_HOMOGLYPH_TRANSLATION) == expected
