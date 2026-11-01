"""Shared pure text, digit, and SKU homoglyph normalization utilities."""

from __future__ import annotations

ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# The Treejar catalogue itself is written with Cyrillic lookalikes, so this map
# is load-bearing rather than defensive. Measured in production 2026-08-08:
# 7 of 920 SKUs literally begin with Cyrillic "СН" -- Skyland chairs such as
# "СН 135 black" -- and 132 product names use Cyrillic "х" as the dimension
# separator, as in "1000х500х754". A customer typing Latin "CH 135" must still
# reach the row whose SKU is Cyrillic, and vice versa.
SKU_HOMOGLYPH_TRANSLATION = str.maketrans(
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
        "У": "Y",
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
        "у": "y",
    }
)


def normalize_text(text: str) -> str:
    """Case-fold text and collapse runs of whitespace to single spaces."""
    return " ".join(text.casefold().split())


def phone_digits(value: str | None) -> str:
    """Extract only digit characters from an optional phone string."""
    if not value:
        return ""
    return "".join(ch for ch in value if ch.isdigit())


def translate_arabic_indic_digits(text: str) -> str:
    """Fold Eastern Arabic-Indic digits (٠-٩) onto ASCII digits (0-9)."""
    return text.translate(ARABIC_INDIC_DIGITS)


def normalize_sku_homoglyphs(text: str) -> str:
    """Fold Cyrillic SKU lookalikes onto case-matching Latin characters."""
    return text.translate(SKU_HOMOGLYPH_TRANSLATION)
