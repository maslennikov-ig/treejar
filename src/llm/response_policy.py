"""Shared response-policy composition helpers."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Sequence

from src.llm.closed_question_guard import apply_closed_question_guard
from src.llm.opening_guard import apply_opening_guard
from src.llm.sales_turn_guard import (
    carry_the_company_question,
    collapse_question_form,
    refuse_to_chase_the_name,
)
from src.services.customer_language import is_arabic_customer_language

logger = logging.getLogger(__name__)


def apply_first_turn_opening_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    customer_name: str | None,
    anchor_line: str | None,
) -> str:
    """Apply the existing opening guard from explicit turn state."""

    return apply_opening_guard(
        text,
        language=language,
        is_first_turn=is_first_turn,
        customer_name=customer_name,
        anchor_line=anchor_line,
    )


def apply_selling_turn_guard(
    text: str,
    *,
    language: str,
    is_first_turn: bool,
    previous_assistant_turns: Sequence[str],
    customer_name: str | None,
    owes_company_question: bool,
) -> str:
    """Apply the selling-turn guards in their established order."""

    if is_first_turn or not text.strip():
        return text

    guarded = collapse_question_form(text)
    guarded = refuse_to_chase_the_name(
        guarded,
        previous_assistant_turns=previous_assistant_turns,
        customer_name=customer_name,
    )
    if owes_company_question:
        guarded = carry_the_company_question(guarded, language=language)
    return guarded


def repair_closed_questions(
    text: str,
    *,
    language: str,
    customer_name: str | None,
    company: str | None,
    customer_type: str | None,
    delivery_address: str | None,
) -> str:
    """Repair questions for values already present in explicit state."""

    result = apply_closed_question_guard(
        text,
        language=language,
        customer_name=customer_name,
        company=company,
        customer_type=customer_type,
        delivery_address=delivery_address,
    )
    return result.text if result.repaired else text


def _last_assistant_message(recent_history: Sequence[str] | None) -> str:
    for entry in reversed(recent_history or ()):
        if entry.startswith("assistant: "):
            return entry.removeprefix("assistant: ").strip()
    return ""


def last_assistant_asked_quote_customer_details(
    recent_history: Sequence[str] | None,
    *,
    quote_context_active: bool = False,
) -> bool:
    """Whether the latest assistant turn requests quotation customer details."""

    last_assistant = " ".join(
        _last_assistant_message(recent_history).casefold().split()
    )
    if not last_assistant:
        return False
    text_has_quote_context = bool(
        re.search(
            r"\b(?:quote|quotation|commercial\s+(?:offer|proposal))\b",
            last_assistant,
        )
        or re.search(
            r"(?:عرض\s+السعر|عرض\s+أسعار|عرض\s+تجاري)",
            last_assistant,
        )
    )
    if not quote_context_active and not text_has_quote_context:
        return False

    english_field = (
        r"(?:company(?:\s+name)?|(?:specific\s+)?delivery\s+address|address|"
        r"(?:customer|full)\s+name|(?:customer\s+)?email(?:\s+address)?|"
        r"(?:phone|mobile)(?:\s+number)?)"
    )
    english_field_value = (
        rf"(?:(?:your|the)\s+)?{english_field}"
        r"(?=\s*(?:[(),;:/?!.]|\d{1,2}[.)]|$|\band\b|\bor\b|\bfor\b|"
        r"\bto\b|\bbefore\b|\bso\b))"
    )
    english_field_prefix = r"\s*(?:[:,-]\s*)?(?:\d{1,2}[.)]\s*)?"
    english_requests = (
        rf"\b(?:please\s+)?(?:share|provide|send){english_field_prefix}"
        rf"{english_field_value}",
        rf"\b(?:can|could|may)\s+i\s+(?:get|have)\s+{english_field_value}",
        rf"\b(?:can|could|may)\s+you\s+(?:share|provide|send)"
        rf"{english_field_prefix}{english_field_value}",
        rf"\bwhat(?:'s|\s+is)\s+(?:your|the)\s+{english_field_value}",
        rf"\bplease\s+let\s+me\s+know\s+{english_field_value}",
        rf"\b(?:please\s+)?confirm\s+{english_field_value}",
        rf"\b(?:i|we)(?:'ll)?\s+(?:just\s+)?need{english_field_prefix}"
        rf"{english_field_value}",
        r"\b(?:please\s+)?confirm\s+you\s+are\s+buying\s+as\s+an\s+individual\b",
    )
    if any(re.search(pattern, last_assistant) for pattern in english_requests):
        return True

    arabic_field = (
        r"(?:اسم\s+العميل|اسم\s+الشركة|عنوان\s+التوصيل(?:\s+المحدد)?|"
        r"البريد\s+الإلكتروني|رقم\s+الهاتف)"
    )
    arabic_field_value = (
        rf"{arabic_field}"
        r"(?=\s*(?:[،؛,:.?؟!]|$|و|أو|لإعداد|قبل))"
    )
    return bool(
        re.search(
            rf"(?:يرجى\s+(?:مشاركة|تزويد)|"
            rf"هل\s+يمكنك\s+(?:مشاركة|تزويد|إرسال)|"
            rf"(?:من\s+فضلك\s+)?(?:شارك|زودني|أرسل)|(?:أحتاج|نحتاج))"
            rf"\s*[:،-]?\s*{arabic_field_value}",
            last_assistant,
        )
    )


def guard_premature_quote_detail_collection(
    text: str,
    *,
    language: str,
    quote_consent_granted: bool,
) -> str:
    """Replace pre-consent detail collection with the quotation opt-in."""

    if quote_consent_granted:
        return text
    if not last_assistant_asked_quote_customer_details(
        [f"assistant: {text}"],
        quote_context_active=True,
    ):
        return text

    quote_match = re.search(
        r"\b(?:quote|quotation|commercial\s+(?:offer|proposal))\b|"
        r"(?:عرض\s+السعر|عرض\s+أسعار|عرض\s+تجاري)",
        text,
        flags=re.IGNORECASE,
    )
    detail_match = re.search(
        r"\b(?:company(?:\s+name)?|(?:specific\s+)?delivery\s+address|"
        r"(?:customer|full)\s+name|(?:customer\s+)?email(?:\s+address)?|"
        r"(?:phone|mobile)(?:\s+number)?)\b|"
        r"(?:اسم\s+العميل|اسم\s+الشركة|عنوان\s+التوصيل(?:\s+المحدد)?|"
        r"البريد\s+الإلكتروني|رقم\s+الهاتف)",
        text,
        flags=re.IGNORECASE,
    )
    anchors = [
        match.start() for match in (quote_match, detail_match) if match is not None
    ]
    request_start = min(anchors) if anchors else 0
    sentence_starts = [0]
    for separator in ("\n", ". ", "? ", "! "):
        boundary = text.rfind(separator, 0, request_start)
        if boundary >= 0:
            sentence_starts.append(boundary + len(separator))
    prefix = text[: max(sentence_starts)].rstrip()
    offer = (
        "هل ترغب أن أجهز عرض سعر رسمي؟"
        if is_arabic_customer_language(language)
        else "Would you like me to prepare a formal quotation?"
    )
    return f"{prefix}\n\n{offer}" if prefix else offer


def _has_meaningful_reply(text: str) -> bool:
    return any(character.isalnum() for character in text)


def apply_guard_with_reply_bound(
    text: str,
    *,
    guard_name: str,
    guard: Callable[[str], str],
) -> str:
    candidate = guard(text)
    if _has_meaningful_reply(text) and not _has_meaningful_reply(candidate):
        logger.error(
            "Response guard removed the reply: guard=%s before_chars=%d after_chars=%d",
            guard_name,
            len(text),
            len(candidate),
        )
        return text
    return candidate
