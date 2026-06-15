from __future__ import annotations

import re

_ORDER_STATUS_RE = re.compile(
    r"\b(?:order\s+status|track(?:ing)?\s+order|tracking)\b",
    re.IGNORECASE,
)
_COMPARISON_RE = re.compile(
    r"\b(?:compare|comparison|which|between|alternative|alternatives)\b",
    re.IGNORECASE,
)
_DISCOVERY_RE = re.compile(
    r"\b(?:show\s+me|recommend(?:ation)?s?|ideas?|options?|similar|catalog)\b",
    re.IGNORECASE,
)
_COMMERCIAL_POLICY_RE = re.compile(
    r"\b(?:"
    r"net\s*30|net\s*60|deferred\s+payment|payment\s+terms?|"
    r"credit\s+terms?|on\s+credit|postpaid|delayed\s+payment|"
    r"discounts?|percent\s+discount|percent\s+off|%\s*off|special\s+price"
    r")\b",
    re.IGNORECASE,
)
_EN_INQUIRY_RE = re.compile(
    r"\b(?:how\s+much|check\s+(?:the\s+)?(?:price|stock|availability)|"
    r"what(?:'s|\s+is)?\s+(?:the\s+)?(?:price|stock|availability)|"
    r"do\s+you\s+have|is\s+.+\bavailable|are\s+.+\bavailable)\b",
    re.IGNORECASE,
)
_EN_PRICE_STOCK_QUESTION_RE = re.compile(
    r"\b(?:price|stock|availability|available)\b.*\?",
    re.IGNORECASE,
)
_RU_INQUIRY_RE = re.compile(
    r"(?:сколько\s+стоит|какая\s+цена|цена|есть\s+ли|в\s+наличии|наличие|доступн)",
    re.IGNORECASE,
)
_AR_INQUIRY_RE = re.compile(
    r"(?:ما\s+هو\s+سعر|كم\s+السعر|سعر|هل\s+يتوفر|يتوفر|متوفر|المخزون|التوفر)"
)
_EXPLICIT_SELECTION_RE = re.compile(
    r"\b(?:buy|purchase|order|proceed|take|confirm|need|want|would\s+like|like)\b"
    r"|(?:нужно|нужны|хочу|заказать|возьму)"
    r"|(?:أحتاج|احتاج|أريد|اريد|اطلب|أطلب)",
    re.IGNORECASE,
)


def is_order_selection_blocked(text: str) -> bool:
    normalized = " ".join(text.split())
    if not normalized:
        return False
    explicit_selection = _EXPLICIT_SELECTION_RE.search(normalized) is not None
    if _ORDER_STATUS_RE.search(normalized):
        return True
    if _COMMERCIAL_POLICY_RE.search(normalized):
        return True
    if _COMPARISON_RE.search(normalized):
        return True
    if (
        _EN_INQUIRY_RE.search(normalized)
        or _EN_PRICE_STOCK_QUESTION_RE.search(normalized)
        or _RU_INQUIRY_RE.search(normalized)
        or _AR_INQUIRY_RE.search(normalized)
    ):
        return True
    return bool(_DISCOVERY_RE.search(normalized) and not explicit_selection)
