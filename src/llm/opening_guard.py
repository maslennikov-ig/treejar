"""Deterministic first-turn dialogue opening guard."""

from __future__ import annotations

import re

_EN_IDENTITY = "Hello, I'm Noor from Treejar."
_EN_NAME_QUESTION = "May I know your name so I can address you properly?"
_AR_IDENTITY = "مرحبًا، أنا Noor من Treejar."
_AR_NAME_QUESTION = "هل يمكنني معرفة اسمك لأخاطبك بشكل مناسب؟"

# What the first reply is for, added 2026-08-09. Two independent research
# reports named the bare name request as the single worst opening available on
# this channel, and our own data agrees: 34% of real customers open with a
# greeting and nothing else, 36% never send a second message, and the median
# conversation is two customer messages. A reply that only asks for a name
# spends the only turn a third of customers will ever read.
_EN_CAPABILITY = "I can check live prices, stock and UAE delivery with installation."
_AR_CAPABILITY = "يمكنني التحقق من الأسعار والتوفر والتوصيل والتركيب في الإمارات."
_EN_CATEGORY_QUESTION = (
    "And are you looking at chairs, desks and workstations, or a full office?"
)
_AR_CATEGORY_QUESTION = "وهل تبحث عن كراسي أو مكاتب ومحطات عمل أم تجهيز مكتب كامل؟"

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


def build_name_gate_reply(*, language: str, anchor_line: str | None = None) -> str:
    """The first reply, carrying something before it asks for anything.

    Order matters and is the whole point: who we are, what we can do for the
    customer right now, what things cost, and only then the question. The name
    request keeps its exact wording and is folded together with a category
    question, so the customer answers both in three words or neither.

    `anchor_line` comes from the catalog, never from the model. Without it the
    reply still stands; with it the customer has a real number before they have
    told us anything.
    """

    is_arabic = _is_arabic_language(language)
    identity = _AR_IDENTITY if is_arabic else _EN_IDENTITY
    capability = _AR_CAPABILITY if is_arabic else _EN_CAPABILITY
    name_question = _AR_NAME_QUESTION if is_arabic else _EN_NAME_QUESTION
    category_question = _AR_CATEGORY_QUESTION if is_arabic else _EN_CATEGORY_QUESTION

    parts = [f"{identity} {capability}"]
    if anchor_line:
        parts.append(anchor_line)
    parts.append(f"{name_question} {category_question}")
    return "\n\n".join(parts)


def apply_opening_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    customer_name: str | None,
    anchor_line: str | None = None,
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
        return build_name_gate_reply(language=language, anchor_line=anchor_line)

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
