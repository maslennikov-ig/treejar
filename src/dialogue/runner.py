from __future__ import annotations

import re

from src.dialogue.order_state import quotation_consent_is_grounded
from src.dialogue.state import QuoteConsent

_QUOTE_DECLINE_RE = re.compile(
    r"\b(?:no|without)\s+(?:a\s+)?(?:quote|quotation)\b|"
    r"\b(?:do\s+not|don't|dont|not\s+want)\b.{0,32}\b(?:quote|quotation)\b|"
    r"(?:لا\s+أريد|بدون)\s+(?:عرض\s+سعر|عرض\s+السعر)",
    re.IGNORECASE,
)
_QUOTE_DEFER_RE = re.compile(
    r"\b(?:quote|quotation)\b.{0,24}\b(?:later|yet|for\s+now|on\s+hold|pause)\b|"
    r"\b(?:later|not\s+yet|hold|pause)\b.{0,24}\b(?:quote|quotation)\b|"
    r"(?:عرض\s+سعر|عرض\s+السعر).{0,24}(?:لاحق|ليس\s+الآن)",
    re.IGNORECASE,
)
_QUOTE_REQUEST_RE = re.compile(
    r"\b(?:prepare|create|send|need|want|get)\b.{0,28}\b(?:quote|quotation)\b|"
    r"\b(?:quote|quotation)\b.{0,20}\b(?:please|now)\b|"
    r"(?:جهز|أرسل|ارسل).{0,28}(?:عرض\s+سعر|عرض\s+السعر)",
    re.IGNORECASE,
)


def quote_consent_signal(
    text: str,
    recent_history: list[str],
) -> QuoteConsent | None:
    if _QUOTE_DEFER_RE.search(text):
        return QuoteConsent.DEFERRED
    if _QUOTE_DECLINE_RE.search(text):
        return QuoteConsent.DECLINED
    if _QUOTE_REQUEST_RE.search(text):
        return QuoteConsent.GRANTED
    normalized = " ".join(text.casefold().split()).strip(" .!?،؟")
    affirmative = normalized in {
        "yes",
        "yes please",
        "ok",
        "okay",
        "نعم",
    }
    last_assistant = next(
        (
            entry.removeprefix("assistant: ")
            for entry in reversed(recent_history)
            if entry.startswith("assistant: ")
        ),
        "",
    )
    if affirmative and quotation_consent_is_grounded("", last_assistant):
        return QuoteConsent.GRANTED
    return None
