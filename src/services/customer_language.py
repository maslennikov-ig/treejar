from __future__ import annotations

import re
from typing import Literal

CustomerLanguage = Literal["en", "ar"]

_ARABIC_LANGUAGE_MARKERS = {"ar", "arabic", "العربية", "عربي"}
_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064a\u066e-\u06d3\u06fa-\u06fc]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
# Attachment notes from src/services/inbound_media.py (one line each).
_MEDIA_NOTE_RE = re.compile(r"\[The customer sent an? [^\n]*\]")


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


def is_strongly_arabic_customer_text(value: object) -> bool:
    """Return true when Arabic script clearly dominates a customer message."""
    # An attachment note is written by Noor in English, not by the customer.
    text = _MEDIA_NOTE_RE.sub(" ", str(value or ""))
    arabic_letters = len(_ARABIC_LETTER_RE.findall(text))
    latin_letters = len(_LATIN_LETTER_RE.findall(text))
    return arabic_letters >= 6 and arabic_letters >= latin_letters * 2
