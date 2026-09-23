"""Catalog product families: the one vocabulary for "what kind of item".

A leaf module so both catalog planning and the product-match reading in
`verified_answers` classify a text into the same families without importing
each other.
"""

from __future__ import annotations

import re
from typing import Literal

CatalogFamily = Literal["seating", "workspace", "storage", "privacy"]

CATALOG_PRODUCT_FAMILIES: tuple[tuple[CatalogFamily, tuple[str, ...]], ...] = (
    ("seating", ("chair", "stool", "seat", "كرسي", "كراسي")),
    (
        "workspace",
        (
            "desk",
            "table",
            "workstation",
            "bench",
            "مكتب",
            "مكاتب",
            "طاولة",
            "طاولات",
            "محطة عمل",
            "محطات عمل",
        ),
    ),
    (
        "storage",
        (
            "pedestal",
            "cabinet",
            "locker",
            "storage",
            "shelf",
            "shelves",
            "accessory",
            "accessories",
            "خزانة",
            "خزائن",
            "تخزين",
        ),
    ),
    ("privacy", ("pod", "booth", "كبسولة", "مقصورة")),
)


def normalize_catalog_text(text: str) -> str:
    return " ".join(str(text or "").casefold().split())


def contains_catalog_term(normalized: str, term: str) -> bool:
    """Whether an already-normalized text names this family term."""
    arabic = re.search(r"[\u0600-\u06ff]", term) is not None
    prefix = "(?:و)?(?:ال)?" if arabic else ""
    suffix = "" if arabic else "(?:s|es)?"
    return (
        re.search(
            rf"(?<!\w){prefix}{re.escape(term.casefold())}{suffix}(?!\w)",
            normalized,
            flags=re.UNICODE,
        )
        is not None
    )


def catalog_text_families(text: str) -> tuple[CatalogFamily, ...]:
    """The product families a text names, in table order."""
    normalized = normalize_catalog_text(text)
    return tuple(
        family
        for family, terms in CATALOG_PRODUCT_FAMILIES
        if any(contains_catalog_term(normalized, term) for term in terms)
    )
