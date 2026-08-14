"""Deterministic single-language enforcement for customer-facing replies."""

from __future__ import annotations

import re

from src.llm.money import contains_customer_output_currency
from src.services.customer_language import normalize_customer_language

_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064a\u066e-\u06d3\u06fa-\u06fc]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
_SENTENCE_RE = re.compile(r".+?(?:[.!?؟]+(?=\s|$)|$)", re.DOTALL)
_SKU_REFERENCE_RE = re.compile(r"\b[A-Z]{2,}[ -]?\d[A-Z0-9 -]*\b", re.IGNORECASE)
_SAFE_FALLBACK = {
    "en": "I want to answer accurately in English. What would you like help with?",
    "ar": "أريد أن أجيبك بدقة بالعربية. بماذا يمكنني مساعدتك؟",
}


def _letter_counts(text: str) -> tuple[int, int]:
    return len(_ARABIC_LETTER_RE.findall(text)), len(_LATIN_LETTER_RE.findall(text))


def _is_foreign_narrative(text: str, *, language: str) -> bool:
    arabic, latin = _letter_counts(text)
    carries_catalog_reference = bool(
        contains_customer_output_currency(text) or _SKU_REFERENCE_RE.search(text)
    )
    if language == "ar":
        return latin >= 8 and latin > arabic * 2 and not carries_catalog_reference
    return arabic >= 4 and arabic > latin and not carries_catalog_reference


def _matches_target_language(text: str, *, language: str) -> bool:
    letters = sum(character.isalpha() for character in text)
    if letters == 0:
        return False
    arabic, _latin = _letter_counts(text)
    arabic_ratio = arabic / letters
    return arabic_ratio >= 0.35 if language == "ar" else arabic_ratio < 0.10


def enforce_customer_reply_language(text: str, *, language: str) -> str:
    """Remove foreign narrative, preserving byte-for-byte text when already safe."""

    normalized_language = normalize_customer_language(language)
    original = str(text or "")
    kept: list[str] = []
    removed_foreign_narrative = False
    for match in _SENTENCE_RE.finditer(original):
        sentence = match.group(0)
        if _is_foreign_narrative(sentence, language=normalized_language):
            removed_foreign_narrative = True
            continue
        kept.append(sentence)

    if (
        not removed_foreign_narrative
        and original
        and _matches_target_language(original, language=normalized_language)
    ):
        return original

    candidate = "".join(kept).strip()
    candidate = re.sub(r"[ \t]+\n", "\n", candidate)
    candidate = re.sub(r"\n{3,}", "\n\n", candidate)
    if candidate and _matches_target_language(candidate, language=normalized_language):
        return candidate
    return _SAFE_FALLBACK[normalized_language]
