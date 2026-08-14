"""Deterministic single-language enforcement for customer-facing replies."""

from __future__ import annotations

import re

from src.llm.money import contains_customer_output_currency
from src.services.customer_language import normalize_customer_language

_ARABIC_LETTER_RE = re.compile(r"[\u0621-\u064a\u066e-\u06d3\u06fa-\u06fc]")
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
# Two short Arabic words. Below that a sentence carries no Arabic of its own.
_AR_SENTENCE_MIN_LETTERS = 4
_LATIN_SENTENCE_MIN_LETTERS = 8
_SENTENCE_RE = re.compile(r".+?(?:[.!?؟]+(?=\s|$)|$)", re.DOTALL)
_SKU_REFERENCE_RE = re.compile(r"\b[A-Z]{2,}[ -]?\d[A-Z0-9 -]*\b", re.IGNORECASE)
_SAFE_FALLBACK = {
    "en": "I want to answer accurately in English. What would you like help with?",
    "ar": "أريد أن أجيبك بدقة بالعربية. بماذا يمكنني مساعدتك؟",
}


def _letter_counts(text: str) -> tuple[int, int]:
    return len(_ARABIC_LETTER_RE.findall(text)), len(_LATIN_LETTER_RE.findall(text))


def _carries_catalog_reference(text: str) -> bool:
    return bool(
        contains_customer_output_currency(text) or _SKU_REFERENCE_RE.search(text)
    )


def _is_foreign_narrative(text: str, *, language: str) -> bool:
    """Whether this one sentence is written in the language we are not speaking.

    The two sides are not symmetric, and `tj-l6pw` is what treating them as
    symmetric cost. Our catalog is named in Latin script, so an Arabic sentence
    that quotes `SkyLand Chair CH 616` is an Arabic sentence, not an English
    one: what decides is whether the sentence carries Arabic of its own. The
    other way round there is nothing to weigh, because no English reply needs
    Arabic script to name anything we sell.
    """

    arabic, latin = _letter_counts(text)
    if language == "ar":
        if arabic >= _AR_SENTENCE_MIN_LETTERS:
            return False
        return latin >= _LATIN_SENTENCE_MIN_LETTERS and not _carries_catalog_reference(
            text
        )
    return arabic >= _AR_SENTENCE_MIN_LETTERS


def _speaks_target_language(text: str, *, language: str) -> bool:
    """Whether this whole reply may go to the customer as it stands.

    A reply that fails here is thrown away and replaced by a fixed sentence, so
    the test has to be about the language and nothing else. Requiring a share of
    Arabic letters is not that test: it also fails a true Arabic reply that
    names three English products, quotes a price or carries a link, and the
    customer then loses the answer instead of receiving it in the wrong
    language.
    """

    letters = sum(character.isalpha() for character in text)
    if letters == 0:
        # Digits, punctuation or an emoji carry no language to judge.
        return True
    arabic, _latin = _letter_counts(text)
    if language == "ar":
        return arabic >= _AR_SENTENCE_MIN_LETTERS or _carries_catalog_reference(text)
    return arabic / letters < 0.10


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
        and _speaks_target_language(original, language=normalized_language)
    ):
        return original

    candidate = "".join(kept).strip()
    candidate = re.sub(r"[ \t]+\n", "\n", candidate)
    candidate = re.sub(r"\n{3,}", "\n\n", candidate)
    if candidate and _speaks_target_language(candidate, language=normalized_language):
        return candidate
    return _SAFE_FALLBACK[normalized_language]
