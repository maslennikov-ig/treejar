from __future__ import annotations

from typing import Literal

CustomerLanguage = Literal["en", "ar"]

_ARABIC_LANGUAGE_MARKERS = {"ar", "arabic", "العربية", "عربي"}


def _normalized_language_marker(value: object) -> str:
    return str(value or "").strip().casefold().replace("_", "-")


def normalize_customer_language(value: object) -> CustomerLanguage:
    """Return the only customer-facing runtime language codes supported by Noor."""
    normalized = _normalized_language_marker(value)
    if normalized in _ARABIC_LANGUAGE_MARKERS or normalized.startswith("ar-"):
        return "ar"
    return "en"


def customer_language_name(value: object) -> str:
    return "Arabic" if normalize_customer_language(value) == "ar" else "English"


def is_arabic_customer_language(value: object) -> bool:
    return normalize_customer_language(value) == "ar"
