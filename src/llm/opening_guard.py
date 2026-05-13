"""Deterministic first-turn dialogue opening guard."""

from __future__ import annotations

import re

_EN_IDENTITY = "Hello, I'm Noor from Treejar."
_EN_NAME_QUESTION = "May I know your name so I can address you properly?"
_AR_IDENTITY = "مرحبًا، أنا Noor من Treejar."
_AR_NAME_QUESTION = "هل يمكنني معرفة اسمك لأخاطبك بشكل مناسب؟"

_EN_NAME_QUESTION_SIGNALS = (
    "your name",
    "address you",
    "call you",
    "how should i address",
    "how should i call",
    "may i know your name",
)
_AR_NAME_QUESTION_SIGNALS = (
    "اسمك",
    "أخاطبك",
    "اخاطبك",
    "أناديك",
    "اناديك",
    "مناداتك",
)


def _is_arabic_language(language: str) -> bool:
    normalized = str(language or "").strip().casefold()
    return normalized in {"ar", "arabic", "العربية"}


def _has_identity(text: str) -> bool:
    normalized = text.casefold()
    return "noor" in normalized and "treejar" in normalized


def _has_name_question(text: str) -> bool:
    normalized = text.casefold()
    return any(signal in normalized for signal in _EN_NAME_QUESTION_SIGNALS) or any(
        signal in text for signal in _AR_NAME_QUESTION_SIGNALS
    )


def _has_customer_name(customer_name: str | None) -> bool:
    return bool(str(customer_name or "").strip())


def _strip_generic_english_opening(text: str) -> str:
    body = text.lstrip()
    body = re.sub(r"\A(?:hello|hi|hey)\b[\s!,.:-]*", "", body, count=1, flags=re.I)
    body = re.sub(
        r"\A(?:welcome\s+to\s+treejar)\b[\s!,.:-]*(?:[^\w\s]+\s*)?",
        "",
        body,
        count=1,
        flags=re.I,
    )
    return body.lstrip() or text.lstrip()


def _strip_legacy_identity(text: str) -> str:
    body = text.lstrip()
    body = re.sub(
        r"\A(?:hello|hi|hey)?[\s!,.:-]*(?:i(?:'| a)m|i am)\s+"
        r"(?:si[y]yad|noor)\s+from\s+treejar[\s!,.:-]*",
        "",
        body,
        count=1,
        flags=re.I,
    )
    body = re.sub(
        r"\Aمرحبًا،\s*أنا\s+(?:Si[y]yad|Noor)\s+من\s+Treejar[\s.،!]*",
        "",
        body,
        count=1,
    )
    return body.lstrip()


def apply_opening_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    customer_name: str | None,
) -> str:
    """Ensure the first customer-facing reply follows Treejar opening rules."""
    if not is_first_turn:
        return text

    body = text.lstrip()
    if not body:
        return text

    is_arabic = _is_arabic_language(language)
    identity = _AR_IDENTITY if is_arabic else _EN_IDENTITY
    name_question = _AR_NAME_QUESTION if is_arabic else _EN_NAME_QUESTION

    if not _has_customer_name(customer_name):
        return f"{identity} {name_question}"

    body = _strip_legacy_identity(body) or body
    needs_identity = not _has_identity(body)
    needs_name_question = False

    if not needs_identity and not needs_name_question:
        return text

    if not needs_identity:
        return f"{body}\n\n{name_question}" if needs_name_question else body

    if not is_arabic:
        body = _strip_generic_english_opening(body)

    opening_parts = [identity]
    if needs_name_question:
        opening_parts.append(name_question)

    return f"{' '.join(opening_parts)}\n\n{body}"
