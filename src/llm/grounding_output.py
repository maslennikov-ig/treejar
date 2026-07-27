"""Deterministic enforcement for bounded customer-output grounding violations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class GroundingViolation(StrEnum):
    """Customer-output semantics that must not pass through from a model."""

    SPECIFIC_PRODUCT_SHOWROOM_TRIAL = "specific_product_showroom_trial"
    FUTURE_STOCK_CHECK = "future_stock_check"


class GroundingOutputAction(StrEnum):
    """How enforcement handled the model-generated customer text."""

    UNCHANGED = "unchanged"
    REPAIRED = "repaired"
    REPLACED = "replaced"


@dataclass(frozen=True, slots=True)
class GroundingOutputResult:
    text: str
    violations: tuple[GroundingViolation, ...]
    action: GroundingOutputAction


_SENTENCE_RE = re.compile(r".+?(?:[.!?؟]+(?=\s|$)|\Z)", re.DOTALL)
_QUOTED_TEXT_RE = re.compile(r'"(?:\\.|[^"\\])*"|“[^”]*”|«[^»]*»', re.DOTALL)
_EN_SHOWROOM_RE = re.compile(r"\bshowroom\b")
_EN_SPECIFIC_PRODUCT_TRIAL_RE = re.compile(
    r"\b(?:try|test|experience)\s+(?:out\s+)?"
    r"(?:(?:a specific|the specific|this|that|the)\s+"
    r"(?:[a-z0-9-]+\s+){0,3}"
    r"|our\s+(?:[a-z0-9-]+\s+){1,3}"
    r"|(?:[a-z0-9-]+\s+){1,3})"
    r"(?:chair|product|item|model)\b"
    r"(?!\s+(?:quality|range|selection|catalog)\b)"
)
_EN_SKU_TRIAL_RE = re.compile(
    r"\b(?:try|test|experience)\s+(?:out\s+)?(?:the\s+)?"
    r"(?=[a-z0-9-]*\d)(?=[a-z0-9-]*-)[a-z0-9-]{3,}\b"
)
_EN_NEGATION_RE = re.compile(
    r"\b(?:not|never|cannot|can't|cant|unable to|unconfirmed|"
    r"without confirmation|don't|do not|no)\b"
)
_AR_SHOWROOM_RE = re.compile(r"(?:معرض|صالة\s+العرض)")
_AR_SPECIFIC_PRODUCT_TRIAL_RE = re.compile(
    r"(?:تجربة|تجرب|جرّب|جرب|اختبار|اختبر)\s+"
    r"(?:(?:هذا|ذلك)\s+)?"
    r"(?:كرسي|الكرسي|منتج|المنتج|موديل|طراز)"
    r"(?:\s+[\w-]+){0,3}"
)
_AR_NEGATION_RE = re.compile(
    r"(?:لا\s+(?:أستطيع|استطيع|يمكنني)|لا\s+يمكن|لن|ليس|ليست|غير\s+مؤكد)"
)

_STOCK_CONTEXT_RE = re.compile(
    r"\b(?:stock|inventory|availability|warehouse)\b"
    r"|(?:المخزون|مخزون|التوفر|التوافر|المستودع|المخازن)"
)
_EN_DIRECT_FUTURE_CHECK_RE = re.compile(
    r"\b(?:let me|i can|i will|i'll|we can|we will|we'll)\s+"
    r"(?:also\s+)?(?:check|confirm|look up|verify)\b"
    r"(?P<object>.{0,100})"
)
_EN_DELEGATED_FUTURE_CHECK_RE = re.compile(
    r"\b(?:(?:i|we)\s+(?:can|will)|i'll|we'll)\s+(?:also\s+)?"
    r"(?:arrange(?:\s+for)?|ask|have)\s+"
    r"(?:(?:our|the)\s+)?(?:team|staff|colleagues?|warehouse team|inventory team)"
    r"\s+to\s+(?:check|confirm|look up|verify)\b"
    r"(?P<object>.{0,100}?)"
    r"(?:\band\s+|\bthen\s+)?"
    r"(?:get back|contact|reply|respond|update)\b"
)
_EN_TEAM_FUTURE_CHECK_RE = re.compile(
    r"\b(?:(?:our|the)\s+)?"
    r"(?:inventory team|warehouse team|team|staff|colleagues?)\s+"
    r"(?:will|'ll)\s+(?:check|confirm|look up|verify)\b"
    r"(?P<object>.{0,100}?)"
    r"(?:\band\s+|\bthen\s+)?"
    r"(?:get back|contact|reply|respond|update)\b"
)
_EN_PRESENT_STOCK_CONFIRMATION_RE = re.compile(
    r"\b(?:i|we)\s+can\s+confirm\s+availability\s*:\s*"
    r"(?:\d+\s+units?\s+are\s+)?(?:currently\s+)?"
    r"(?:in stock|available)\b"
)
_EN_UNRELATED_CHECK_OBJECT_RE = re.compile(
    r"\b(?:dimension|measurement|size|colour|color|finish|delivery|timeline|"
    r"appointment|project|quotation|quote|order status)\b"
)
_AR_DIRECT_FUTURE_CHECK_RE = re.compile(
    r"(?:دعني|يمكنني(?:\s+أن)?|سأقوم\s+ب|سوف\s+أقوم\s+ب|سنقوم\s+ب)"
    r"\s*(?:التحقق|التأكد)"
    r"(?P<object>.{0,100})"
)
_AR_DELEGATED_FUTURE_CHECK_RE = re.compile(
    r"(?:يمكنني(?:\s+أن)?|سأقوم(?:\s+ب)?|سوف\s+أقوم(?:\s+ب)?|سنقوم(?:\s+ب)?)"
    r"\s*(?:أطلب|اطلب|نطلب|أرتب|ارتب|ترتيب)\s+من\s+"
    r"(?:فريقنا|الفريق|الموظفين|زملائنا)\s+"
    r"(?:أن\s+)?(?:التحقق|التأكد)"
    r"(?P<object>.{0,100}?)"
    r"(?:والرد|ثم\s+الرد|والتواصل|ثم\s+التواصل|والعودة)"
)
_AR_UNRELATED_CHECK_OBJECT_RE = re.compile(
    r"(?:الأبعاد|الابعاد|المقاسات|القياسات|اللون|التشطيب|التوصيل|"
    r"الموعد|المشروع|عرض\s+السعر|حالة\s+الطلب)"
)

_EN_SHOWROOM_FALLBACK = (
    "You're welcome to visit our UAE showroom to experience our product quality, "
    "but I can't confirm that a specific product will be available to try."
)
_AR_SHOWROOM_FALLBACK = (
    "يمكنك زيارة معرضنا في الإمارات للتعرف على جودة منتجاتنا، لكن لا أستطيع "
    "تأكيد توفر منتج محدد للتجربة."
)
_EN_STOCK_FALLBACK = (
    "Current stock is unconfirmed because no inventory result is available. "
    "I can only confirm availability from a current inventory result."
)
_AR_STOCK_FALLBACK = (
    "لا تتوفر لدي نتيجة حالية من نظام المخزون، لذلك يبقى المخزون غير مؤكد. "
    "لا يمكنني تأكيد التوفر إلا بناءً على نتيجة مخزون حالية."
)
_EN_GENERIC_FALLBACK = (
    "I can only share confirmed product and inventory information. Current "
    "availability and a specific showroom trial are not confirmed."
)
_AR_GENERIC_FALLBACK = (
    "يمكنني مشاركة معلومات المنتج والمخزون المؤكدة فقط. التوفر الحالي وتجربة "
    "منتج محدد في المعرض غير مؤكدين."
)


def _normalized(text: str) -> str:
    return " ".join(text.casefold().replace("’", "'").split())


def _without_quoted_text(text: str) -> str:
    return _QUOTED_TEXT_RE.sub(" ", text)


def _sentence_parts(text: str) -> list[str]:
    return [
        match.group().strip()
        for match in _SENTENCE_RE.finditer(text)
        if match.group().strip()
    ]


def _is_asserted_match(
    sentence: str,
    match: re.Match[str],
    *,
    negation_pattern: re.Pattern[str],
) -> bool:
    boundaries = [
        sentence.rfind(marker, 0, match.start())
        for marker in (".", "!", "?", "؟", ";", "؛", "\n", " but ", " however ")
    ]
    clause_start = max((index + 1 for index in boundaries if index >= 0), default=0)
    return negation_pattern.search(sentence[clause_start : match.start()]) is None


def _has_specific_product_showroom_trial(sentence: str) -> bool:
    visible = _without_quoted_text(sentence)
    normalized = _normalized(visible)
    if _EN_SHOWROOM_RE.search(normalized):
        for pattern in (_EN_SPECIFIC_PRODUCT_TRIAL_RE, _EN_SKU_TRIAL_RE):
            for match in pattern.finditer(normalized):
                if _is_asserted_match(
                    normalized,
                    match,
                    negation_pattern=_EN_NEGATION_RE,
                ):
                    return True

    if _AR_SHOWROOM_RE.search(visible):
        for match in _AR_SPECIFIC_PRODUCT_TRIAL_RE.finditer(visible):
            if _is_asserted_match(
                visible,
                match,
                negation_pattern=_AR_NEGATION_RE,
            ):
                return True
    return False


def _has_meaningful_check_object(
    value: str,
    *,
    stock_context: re.Pattern[str],
    unrelated_context: re.Pattern[str],
    full_text_has_stock_context: bool,
) -> bool:
    if unrelated_context.search(value):
        return False
    if stock_context.search(value):
        return True
    residue = re.sub(
        r"\b(?:and|then|with|for|to|you|your|our|the|a|an|also|later|shortly)\b",
        " ",
        value,
    )
    residue = re.sub(r"[\s,;:،؛-]+", "", residue)
    return full_text_has_stock_context and not residue


def _has_future_stock_check(
    sentence: str,
    *,
    full_text: str,
    inventory_confirmed: bool,
) -> bool:
    visible = _without_quoted_text(sentence)
    full_visible = _without_quoted_text(full_text)
    normalized = _normalized(visible)
    normalized_full = _normalized(full_visible)
    full_has_stock = _STOCK_CONTEXT_RE.search(normalized_full) is not None

    present_confirmation_spans = (
        [
            (match.start(), match.end())
            for match in _EN_PRESENT_STOCK_CONFIRMATION_RE.finditer(normalized)
        ]
        if inventory_confirmed
        else []
    )
    for pattern in (
        _EN_DIRECT_FUTURE_CHECK_RE,
        _EN_DELEGATED_FUTURE_CHECK_RE,
        _EN_TEAM_FUTURE_CHECK_RE,
    ):
        for match in pattern.finditer(normalized):
            if any(
                start <= match.start() < end
                for start, end in present_confirmation_spans
            ):
                continue
            if not _is_asserted_match(
                normalized,
                match,
                negation_pattern=_EN_NEGATION_RE,
            ):
                continue
            if _has_meaningful_check_object(
                match.group("object"),
                stock_context=_STOCK_CONTEXT_RE,
                unrelated_context=_EN_UNRELATED_CHECK_OBJECT_RE,
                full_text_has_stock_context=full_has_stock,
            ):
                return True

    for pattern in (_AR_DIRECT_FUTURE_CHECK_RE, _AR_DELEGATED_FUTURE_CHECK_RE):
        for match in pattern.finditer(visible):
            if not _is_asserted_match(
                visible,
                match,
                negation_pattern=_AR_NEGATION_RE,
            ):
                continue
            if _has_meaningful_check_object(
                match.group("object"),
                stock_context=_STOCK_CONTEXT_RE,
                unrelated_context=_AR_UNRELATED_CHECK_OBJECT_RE,
                full_text_has_stock_context=full_has_stock,
            ):
                return True
    return False


def _classify_sentence(
    sentence: str,
    *,
    full_text: str,
    inventory_confirmed: bool,
) -> tuple[GroundingViolation, ...]:
    violations: list[GroundingViolation] = []
    if _has_specific_product_showroom_trial(sentence):
        violations.append(GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL)
    if _has_future_stock_check(
        sentence,
        full_text=full_text,
        inventory_confirmed=inventory_confirmed,
    ):
        violations.append(GroundingViolation.FUTURE_STOCK_CHECK)
    return tuple(violations)


def _classify(
    text: str,
    *,
    inventory_confirmed: bool,
) -> tuple[GroundingViolation, ...]:
    violations: list[GroundingViolation] = []
    for sentence in _sentence_parts(text):
        for violation in _classify_sentence(
            sentence,
            full_text=text,
            inventory_confirmed=inventory_confirmed,
        ):
            if violation not in violations:
                violations.append(violation)
    return tuple(violations)


def classify_grounding_output(
    text: str,
    *,
    inventory_confirmed: bool = False,
) -> tuple[GroundingViolation, ...]:
    """Classify the two bounded unsupported semantics in customer text."""

    return _classify(
        str(text or ""),
        inventory_confirmed=inventory_confirmed,
    )


def contains_specific_product_showroom_trial(text: str) -> bool:
    return (
        GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL
        in classify_grounding_output(text)
    )


def contains_future_stock_check(text: str) -> bool:
    return GroundingViolation.FUTURE_STOCK_CHECK in classify_grounding_output(text)


def _is_arabic_language(language: str) -> bool:
    return str(language or "").strip().casefold() in {"ar", "arabic", "العربية"}


def _fallback(
    violations: tuple[GroundingViolation, ...],
    *,
    language: str,
) -> str:
    arabic = _is_arabic_language(language)
    if GroundingViolation.FUTURE_STOCK_CHECK in violations:
        return _AR_STOCK_FALLBACK if arabic else _EN_STOCK_FALLBACK
    if GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL in violations:
        return _AR_SHOWROOM_FALLBACK if arabic else _EN_SHOWROOM_FALLBACK
    return _AR_GENERIC_FALLBACK if arabic else _EN_GENERIC_FALLBACK


def enforce_grounding_output(
    text: str,
    *,
    language: str,
    inventory_confirmed: bool = False,
) -> GroundingOutputResult:
    """Remove bounded violating sentences or fail closed with localized text."""

    original = str(text or "")
    try:
        violations = _classify(
            original,
            inventory_confirmed=inventory_confirmed,
        )
        if not violations:
            return GroundingOutputResult(
                text=original,
                violations=(),
                action=GroundingOutputAction.UNCHANGED,
            )

        retained = [
            sentence
            for sentence in _sentence_parts(original)
            if not _classify_sentence(
                sentence,
                full_text=original,
                inventory_confirmed=inventory_confirmed,
            )
        ]
        repaired = " ".join(retained).strip()
        if repaired and not _classify(
            repaired,
            inventory_confirmed=inventory_confirmed,
        ):
            return GroundingOutputResult(
                text=repaired,
                violations=violations,
                action=GroundingOutputAction.REPAIRED,
            )
        return GroundingOutputResult(
            text=_fallback(violations, language=language),
            violations=violations,
            action=GroundingOutputAction.REPLACED,
        )
    except Exception:
        return GroundingOutputResult(
            text=_fallback((), language=language),
            violations=(),
            action=GroundingOutputAction.REPLACED,
        )
