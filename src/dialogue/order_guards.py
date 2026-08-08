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
    r"\b(?:how\s+much|check\s+(?:the\s+)?"
    r"(?:(?:exact|current|live)\s+)?(?:price|stock|availability)|"
    r"what(?:'s|\s+is)?\s+(?:the\s+)?(?:price|stock|availability)|"
    r"do\s+you\s+have|is\s+.+\bavailable|are\s+.+\bavailable)\b",
    re.IGNORECASE,
)
_EN_PRICE_STOCK_QUESTION_RE = re.compile(
    r"\b(?:price|stock|availability|available)\b.*\?",
    re.IGNORECASE,
)
_AR_INQUIRY_RE = re.compile(
    r"(?:ما\s+هو\s+سعر|كم\s+السعر|سعر|هل\s+يتوفر|يتوفر|متوفر|المخزون|التوفر)"
)
_EXPLICIT_SELECTION_RE = re.compile(
    r"\b(?:buy|purchase|order|proceed|take|confirm|need|want|would\s+like|like)\b"
    r"|(?:أحتاج|احتاج|أريد|اريد|اطلب|أطلب)",
    re.IGNORECASE,
)


_QUOTATION_DONE_CLAIM_RE = re.compile(
    r"\b(?:quote|quotation)\b[^.!?\n]{0,60}\b"
    r"(?:prepared|created|generated|issued|drafted|ready|sent|attached)\b"
    r"|\b(?:prepared|created|generated|issued|drafted|sent|attached)\b"
    r"[^.!?\n]{0,60}\b(?:quote|quotation)\b"
    r"|(?:عرض\s+(?:ال)?سعر)[^.!?\n]{0,60}(?:جاهز|جاهزة|مرفق|أُرسل|ارسل)"
    r"|(?:تم\s+(?:إعداد|اعداد|إرسال|ارسال)|جهزت|أعددت|اعددت)"
    r"[^.!?\n]{0,60}(?:عرض\s+(?:ال)?سعر)",
    re.IGNORECASE,
)
# A promise is not an assertion. Without this the guard would fire on
# "I will prepare the quotation once you confirm", which is exactly the honest
# sentence the assistant is supposed to say after a decline.
_QUOTATION_NOT_YET_RE = re.compile(
    r"\b(?:will|would|can|could|shall|going\s+to|once|after\s+you|when\s+you"
    r"|as\s+soon\s+as|if\s+you|cannot|can't|won't|not\s+yet|before)\b"
    r"|(?:سوف|سأ|بمجرد|عندما|إذا|لا\s+أستطيع|لم\s+)",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?؟\n]+")


def quotation_claimed_without_call(
    reply_text: str,
    *,
    quotation_created: bool,
) -> bool:
    """Whether the reply tells the customer a quotation exists that never ran.

    This is an action claim, not a catalog fact, so pattern matching is the
    right instrument here: the trace answers definitively whether the call
    succeeded, and the only open question is whether the reply asserts it did.
    """
    if quotation_created:
        return False
    for sentence in _SENTENCE_SPLIT_RE.split(reply_text):
        if not sentence.strip():
            continue
        if _QUOTATION_DONE_CLAIM_RE.search(
            sentence
        ) and not _QUOTATION_NOT_YET_RE.search(sentence):
            return True
    return False


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
        or _AR_INQUIRY_RE.search(normalized)
    ):
        return True
    return bool(_DISCOVERY_RE.search(normalized) and not explicit_selection)
