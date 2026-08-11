"""Deterministic enforcement for bounded customer-output grounding violations."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from src.llm.money import canonical_amount, find_customer_output_amounts


class GroundingViolation(StrEnum):
    """Customer-output semantics that must not pass through from a model."""

    SPECIFIC_PRODUCT_SHOWROOM_TRIAL = "specific_product_showroom_trial"
    UNVERIFIED_STOCK_CONFIRMATION = "unverified_stock_confirmation"
    FUTURE_STOCK_CHECK = "future_stock_check"
    # Added 2026-08-10 for `tj-vz7o.10.1`. On a bare "Good Afternoon" with no
    # catalog row behind it, the model answered "Our ergonomic office chairs
    # start from AED 500 in our catalog" -- a price it invented, attributed to
    # the catalog, in the same reply as our promise to quote only confirmed
    # prices. The three violations above are text-only patterns, so nothing
    # here could see that no row existed. This one is the first that has to be
    # told what was actually verified.
    UNVERIFIED_PRICE = "unverified_price"
    # `tj-rt7w.1`: a specific prompt rule was measured on the stored failure
    # and one of three fresh attempts still offered to help with an unsupported
    # customer-owned-furniture resale path. The prompt has therefore earned a
    # bounded deterministic backstop for this exact service family.
    UNVERIFIED_CUSTOMER_OWNED_FURNITURE_SERVICE = (
        "unverified_customer_owned_furniture_service"
    )


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
_QUOTED_TEXT_RE = re.compile(
    r'"(?:\\.|[^"\\])*"'
    r"|“[^”]*”"
    r"|«[^»]*»"
    r"|(?<![\w])'(?=\S)(?:[^'\n]|(?<=\w)'(?=\w))*?(?<=\S)'(?!\w)"
    r"|‘(?=\S)(?:[^’\n]|(?<=\w)’(?=\w))*?(?<=\S)’(?!\w)",
    re.DOTALL,
)
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

_EN_CUSTOMER_OWNED_ITEM_RE = re.compile(
    r"\b(?:"
    r"your\s+(?:(?:own|existing|used|pre[- ]owned|second[- ]hand)\s+)?"
    r"(?:office\s+)?(?:furniture|desks?|tables?|chairs?|workstations?|"
    r"cabinets?|sofas?|items?)"
    r"|(?:customer[- ]owned|pre[- ]owned|second[- ]hand|used)\s+"
    r"(?:office\s+)?(?:furniture|desks?|tables?|chairs?|workstations?|"
    r"cabinets?|sofas?|items?)"
    r"|(?:furniture|desks?|tables?|chairs?|workstations?|cabinets?|sofas?|items?)"
    r"\s+(?:that\s+)?you\s+(?:already\s+)?(?:own|have)"
    r")\b"
)
_EN_CUSTOMER_OWNED_SERVICE_RE = re.compile(
    r"\b(?:i|we|treejar)\s+"
    r"(?!(?:do\s+not|don't|cannot|can't|cant|are\s+unable)\b)"
    r"(?:(?:can|will|would|do|are\s+able\s+to)\s+)?"
    r"(?:help\s+(?:you\s+)?(?:to\s+)?)?"
    r"(?:buy|purchase|sell|resell|broker|trade(?:\s+in)?|assess|value)\b"
)
_EN_CUSTOMER_OWNED_OPTIONS_RE = re.compile(
    r"\b(?:i|we|treejar)\s+can\s+help\s+(?:you\s+)?"
    r"(?:clarify|explore|with)\s+(?:the\s+)?"
    r"(?:resale|selling|trade[- ]in|options?|next\s+steps?)\b"
)
_EN_CUSTOMER_OWNED_INTAKE_RE = re.compile(
    r"\b(?:please\s+)?(?:share|send|provide)\b.{0,160}"
    r"\b(?:photos?|pictures?|dimensions?|measurements?|condition|location|"
    r"asking\s+price)\b"
)

_EN_STRONG_STOCK_CONTEXT_RE = re.compile(
    r"\b(?:stock|inventory|availability|available|unavailable)\b"
)
_EN_WEAK_STOCK_CONTEXT_RE = re.compile(r"\bwarehouse\b")
_AR_STRONG_STOCK_CONTEXT_RE = re.compile(
    r"(?:المخزون|مخزون|التوفر|التوافر|متوفر|متاحة|متاح|غير\s+متوفر)"
)
_AR_WEAK_STOCK_CONTEXT_RE = re.compile(r"(?:المستودع|المخازن)")
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
_EN_SKU_PATTERN = r"(?=[a-z0-9-]*\d)(?=[a-z0-9-]*-)[a-z0-9-]+"
_EN_PRESENT_STOCK_MODIFIER_PATTERN = (
    r"(?:(?:currently\s+not|not\s+currently|currently|not)\s+)?"
)
_EN_PRESENT_STOCK_STATUS_PATTERN = (
    rf"{_EN_PRESENT_STOCK_MODIFIER_PATTERN}"
    r"(?:available|unavailable|in\s+stock|out\s+of\s+stock)"
)
_EN_PRESENT_STOCK_COPULA_PATTERN = r"(?:is|are|isn't|aren't)"
_EN_SKU_PRESENT_STOCK_SUBJECT_PATTERN = (
    rf"(?:(?:\d+\s+)?{_EN_SKU_PATTERN}(?:\s+units?)?"
    rf"\s+{_EN_PRESENT_STOCK_COPULA_PATTERN}\s+"
    rf"{_EN_PRESENT_STOCK_STATUS_PATTERN}"
    rf"|{_EN_SKU_PATTERN}\s+has\s+\d+\s+units?"
    rf"\s+{_EN_PRESENT_STOCK_STATUS_PATTERN})"
)
_EN_CONFIRMED_PRESENT_STOCK_SUBJECT_PATTERN = (
    rf"(?:{_EN_SKU_PRESENT_STOCK_SUBJECT_PATTERN}"
    rf"|\d+\s+units?\s+{_EN_PRESENT_STOCK_COPULA_PATTERN}\s+"
    rf"{_EN_PRESENT_STOCK_STATUS_PATTERN})"
)
_EN_PREFIXED_PRESENT_STOCK_ASSERTION_RE = re.compile(
    rf"\b(?:i|we)\s+can\s+confirm(?:"
    rf"\s+availability\s*:\s*{_EN_CONFIRMED_PRESENT_STOCK_SUBJECT_PATTERN}"
    rf"|\s+(?:that\s+)?{_EN_CONFIRMED_PRESENT_STOCK_SUBJECT_PATTERN}"
    rf")\b",
    re.IGNORECASE,
)
_EN_DIRECT_SKU_PRESENT_STOCK_ASSERTION_RE = re.compile(
    rf"\b{_EN_SKU_PRESENT_STOCK_SUBJECT_PATTERN}\b",
    re.IGNORECASE,
)
_EN_ASSERTION_CLAUSE_BOUNDARY_RE = re.compile(
    r"(?:^|[.;:,—–]\s*|(?:^|\n)\s*(?:[-*•]\s*)?|\b(?:but|however)\s*)$",
    re.IGNORECASE,
)
_EN_CONDITIONAL_CLAUSE_RE = re.compile(
    r"^\s*(?:if|when)\b"
    r"|\b(?:if|whether|when)(?:[ \t]*:)?"
    r"(?:[ \t]*\n[ \t]*(?:[-*•][ \t]*)?)?[ \t]*$",
    re.IGNORECASE,
)
_EN_UNRELATED_CHECK_OBJECT_RE = re.compile(
    r"\b(?:dimensions?|measurements?|sizes?|colou?rs?|finish|delivery|timeline|"
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
_EN_PRICE_FALLBACK = (
    "I quote only from our own catalog, and I don't have a confirmed price for "
    "that yet. Tell me what you need and I'll pull the exact figure from the "
    "catalog for you."
)
_AR_PRICE_FALLBACK = (
    "أقدّم الأسعار من كتالوجنا فقط، ولا يتوفر لدي سعر مؤكد لذلك بعد. أخبرني بما "
    "تحتاجه وسأستخرج لك الرقم الدقيق من الكتالوج."
)
_EN_CUSTOMER_OWNED_SERVICE_FALLBACK = (
    "Buying, resale, brokerage, valuation, or assessment of customer-owned "
    "furniture is not a confirmed service."
)
_AR_CUSTOMER_OWNED_SERVICE_FALLBACK = (
    "شراء أثاث العميل أو إعادة بيعه أو تقييمه ليست خدمة مؤكدة."
)
_EN_GENERIC_FALLBACK = (
    "I can only share confirmed product and inventory information. Current "
    "availability and a specific showroom trial are not confirmed."
)
_AR_GENERIC_FALLBACK = (
    "يمكنني مشاركة معلومات المنتج والمخزون المؤكدة فقط. التوفر الحالي وتجربة "
    "منتج محدد في المعرض غير مؤكدين."
)


def asserted_amounts(text: str) -> tuple[str, ...]:
    """Every sum of money the customer would read as a Treejar figure."""

    return find_customer_output_amounts(visible_grounding_text(str(text or "")))


def _has_unverified_price(sentence: str, *, grounded: frozenset[str] | None) -> bool:
    if grounded is None:
        return False
    return any(amount not in grounded for amount in asserted_amounts(sentence))


def _normalized(text: str) -> str:
    return " ".join(text.casefold().replace("’", "'").split())


def _with_normalized_apostrophes(text: str) -> str:
    return text.replace("’", "'")


def visible_grounding_text(text: str) -> str:
    """Mask bounded quoted spans while preserving offsets and visible wording."""

    original = str(text or "")
    return _QUOTED_TEXT_RE.sub(lambda match: " " * len(match.group()), original)


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
    visible = visible_grounding_text(sentence)
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


def _has_unverified_customer_owned_furniture_service(
    sentence: str,
    *,
    full_text: str,
) -> bool:
    full_visible = _normalized(visible_grounding_text(full_text))
    if not _EN_CUSTOMER_OWNED_ITEM_RE.search(full_visible):
        return False

    visible = _normalized(visible_grounding_text(sentence))
    return any(
        _is_asserted_match(
            visible,
            match,
            negation_pattern=_EN_NEGATION_RE,
        )
        for pattern in (
            _EN_CUSTOMER_OWNED_SERVICE_RE,
            _EN_CUSTOMER_OWNED_OPTIONS_RE,
            _EN_CUSTOMER_OWNED_INTAKE_RE,
        )
        for match in pattern.finditer(visible)
    )


def _has_meaningful_check_object(
    value: str,
    *,
    strong_stock_context: re.Pattern[str],
    weak_stock_context: re.Pattern[str],
    unrelated_context: re.Pattern[str],
    full_text_has_strong_stock_context: bool,
    full_text_has_weak_stock_context: bool,
) -> bool:
    if strong_stock_context.search(value):
        return True
    if unrelated_context.search(value):
        return False
    if weak_stock_context.search(value):
        return True
    residue = re.sub(
        r"\b(?:and|then|with|for|to|you|your|our|the|a|an|also|later|shortly)\b",
        " ",
        value,
    )
    residue = re.sub(r"[\s,;:،؛-]+", "", residue)
    return (
        full_text_has_strong_stock_context or full_text_has_weak_stock_context
    ) and not residue


def _present_stock_confirmation_spans(text: str) -> list[tuple[int, int]]:
    spans = [
        (match.start(), match.end())
        for match in _EN_PREFIXED_PRESENT_STOCK_ASSERTION_RE.finditer(text)
    ]
    for match in _EN_DIRECT_SKU_PRESENT_STOCK_ASSERTION_RE.finditer(text):
        prefix = text[: match.start()]
        if _EN_ASSERTION_CLAUSE_BOUNDARY_RE.search(
            prefix
        ) and not _EN_CONDITIONAL_CLAUSE_RE.search(prefix):
            spans.append((match.start(), match.end()))
    return sorted(set(spans))


def _has_present_stock_confirmation(sentence: str) -> bool:
    visible = _with_normalized_apostrophes(visible_grounding_text(sentence))
    return bool(_present_stock_confirmation_spans(visible))


def _has_future_stock_check(
    sentence: str,
    *,
    full_text: str,
) -> bool:
    visible = visible_grounding_text(sentence)
    full_visible = visible_grounding_text(full_text)
    normalized = _normalized(visible)
    normalized_full = _normalized(full_visible)
    full_has_strong_stock = (
        _EN_STRONG_STOCK_CONTEXT_RE.search(normalized_full) is not None
    )
    full_has_weak_stock = _EN_WEAK_STOCK_CONTEXT_RE.search(normalized_full) is not None

    present_confirmation_spans = _present_stock_confirmation_spans(normalized)
    future_text = list(normalized)
    for start, end in present_confirmation_spans:
        future_text[start:end] = " " * (end - start)
    normalized_future = "".join(future_text)
    for pattern in (
        _EN_DIRECT_FUTURE_CHECK_RE,
        _EN_DELEGATED_FUTURE_CHECK_RE,
        _EN_TEAM_FUTURE_CHECK_RE,
    ):
        for match in pattern.finditer(normalized_future):
            if not _is_asserted_match(
                normalized_future,
                match,
                negation_pattern=_EN_NEGATION_RE,
            ):
                continue
            if _has_meaningful_check_object(
                match.group("object"),
                strong_stock_context=_EN_STRONG_STOCK_CONTEXT_RE,
                weak_stock_context=_EN_WEAK_STOCK_CONTEXT_RE,
                unrelated_context=_EN_UNRELATED_CHECK_OBJECT_RE,
                full_text_has_strong_stock_context=full_has_strong_stock,
                full_text_has_weak_stock_context=full_has_weak_stock,
            ):
                return True

    full_has_ar_strong_stock = (
        _AR_STRONG_STOCK_CONTEXT_RE.search(full_visible) is not None
    )
    full_has_ar_weak_stock = _AR_WEAK_STOCK_CONTEXT_RE.search(full_visible) is not None
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
                strong_stock_context=_AR_STRONG_STOCK_CONTEXT_RE,
                weak_stock_context=_AR_WEAK_STOCK_CONTEXT_RE,
                unrelated_context=_AR_UNRELATED_CHECK_OBJECT_RE,
                full_text_has_strong_stock_context=full_has_ar_strong_stock,
                full_text_has_weak_stock_context=full_has_ar_weak_stock,
            ):
                return True
    return False


def _confirmed_present_clause(
    sentence: str,
    *,
    inventory_confirmed: bool,
) -> str | None:
    if not inventory_confirmed:
        return None
    visible = _with_normalized_apostrophes(visible_grounding_text(sentence))
    spans = _present_stock_confirmation_spans(visible)
    if not spans:
        return None
    _, end = spans[0]
    candidate = sentence[:end].rstrip(" ,;،؛")
    return candidate or None


def _classify_sentence(
    sentence: str,
    *,
    full_text: str,
    inventory_confirmed: bool,
    grounded_amounts: frozenset[str] | None,
) -> tuple[GroundingViolation, ...]:
    violations: list[GroundingViolation] = []
    if _has_specific_product_showroom_trial(sentence):
        violations.append(GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL)
    if _has_present_stock_confirmation(sentence) and not inventory_confirmed:
        violations.append(GroundingViolation.UNVERIFIED_STOCK_CONFIRMATION)
    if _has_future_stock_check(
        sentence,
        full_text=full_text,
    ):
        violations.append(GroundingViolation.FUTURE_STOCK_CHECK)
    if _has_unverified_price(sentence, grounded=grounded_amounts):
        violations.append(GroundingViolation.UNVERIFIED_PRICE)
    if _has_unverified_customer_owned_furniture_service(
        sentence,
        full_text=full_text,
    ):
        violations.append(
            GroundingViolation.UNVERIFIED_CUSTOMER_OWNED_FURNITURE_SERVICE
        )
    return tuple(violations)


def _classify(
    text: str,
    *,
    inventory_confirmed: bool,
    grounded_amounts: frozenset[str] | None = None,
) -> tuple[GroundingViolation, ...]:
    violations: list[GroundingViolation] = []
    for sentence in _sentence_parts(text):
        for violation in _classify_sentence(
            sentence,
            full_text=text,
            inventory_confirmed=inventory_confirmed,
            grounded_amounts=grounded_amounts,
        ):
            if violation not in violations:
                violations.append(violation)
    return tuple(violations)


def classify_grounding_output(
    text: str,
    *,
    inventory_confirmed: bool = False,
    grounded_amounts: Iterable[object] | None = None,
) -> tuple[GroundingViolation, ...]:
    """Classify bounded unsupported product, inventory, price and service semantics."""

    return _classify(
        str(text or ""),
        inventory_confirmed=inventory_confirmed,
        grounded_amounts=_grounded_set(grounded_amounts),
    )


def _grounded_set(values: Iterable[object] | None) -> frozenset[str] | None:
    """`None` means nobody offered evidence, so the price check stays off.

    An empty collection is the opposite and means it: the caller looked and
    found no verified figure, so every sum in the reply is invented.
    """

    if values is None:
        return None
    return frozenset(
        canonical
        for value in values
        if (canonical := canonical_amount(value)) is not None
    )


def contains_specific_product_showroom_trial(text: str) -> bool:
    return (
        GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL
        in classify_grounding_output(text)
    )


def contains_future_stock_check(text: str) -> bool:
    return GroundingViolation.FUTURE_STOCK_CHECK in classify_grounding_output(text)


def contains_unverified_stock_confirmation(text: str) -> bool:
    return (
        GroundingViolation.UNVERIFIED_STOCK_CONFIRMATION
        in classify_grounding_output(text)
    )


def _is_arabic_language(language: str) -> bool:
    return str(language or "").strip().casefold() in {"ar", "arabic", "العربية"}


def _fallback(
    violations: tuple[GroundingViolation, ...],
    *,
    language: str,
) -> str:
    arabic = _is_arabic_language(language)
    if (
        GroundingViolation.FUTURE_STOCK_CHECK in violations
        or GroundingViolation.UNVERIFIED_STOCK_CONFIRMATION in violations
    ):
        return _AR_STOCK_FALLBACK if arabic else _EN_STOCK_FALLBACK
    if GroundingViolation.UNVERIFIED_PRICE in violations:
        return _AR_PRICE_FALLBACK if arabic else _EN_PRICE_FALLBACK
    if GroundingViolation.SPECIFIC_PRODUCT_SHOWROOM_TRIAL in violations:
        return _AR_SHOWROOM_FALLBACK if arabic else _EN_SHOWROOM_FALLBACK
    if GroundingViolation.UNVERIFIED_CUSTOMER_OWNED_FURNITURE_SERVICE in violations:
        return (
            _AR_CUSTOMER_OWNED_SERVICE_FALLBACK
            if arabic
            else _EN_CUSTOMER_OWNED_SERVICE_FALLBACK
        )
    return _AR_GENERIC_FALLBACK if arabic else _EN_GENERIC_FALLBACK


def _tidy(text: str) -> str:
    """Close the hole a removed sentence leaves without closing the paragraphs.

    Dropping one sentence used to re-join the whole reply with single spaces,
    which flattened a three-paragraph WhatsApp opening into a wall. That was
    invisible while the repair path almost never fired on an opening; the price
    violation fires there by design, so the seam has to be tidy.
    """

    kept: list[str] = []
    for line in text.splitlines():
        # A removed sentence leaves its own padding behind on both sides, so the
        # seam is squeezed rather than trusted. WhatsApp replies are flat text
        # and bullets sit at column zero, so no indentation is lost here.
        tidy = re.sub(r"[ \t]{2,}", " ", line.strip())
        if not tidy and (not kept or not kept[-1]):
            continue
        kept.append(tidy)
    return "\n".join(kept).strip()


def _repair(
    original: str,
    *,
    inventory_confirmed: bool,
    grounded_amounts: frozenset[str] | None,
) -> str:
    pieces: list[str] = []
    for match in _SENTENCE_RE.finditer(original):
        raw = match.group()
        sentence = raw.strip()
        if not sentence:
            pieces.append(raw)
            continue
        if not _classify_sentence(
            sentence,
            full_text=original,
            inventory_confirmed=inventory_confirmed,
            grounded_amounts=grounded_amounts,
        ):
            pieces.append(raw)
            continue
        leading = raw[: len(raw) - len(raw.lstrip())]
        confirmed_clause = _confirmed_present_clause(
            sentence,
            inventory_confirmed=inventory_confirmed,
        )
        if confirmed_clause and not _classify(
            confirmed_clause,
            inventory_confirmed=inventory_confirmed,
            grounded_amounts=grounded_amounts,
        ):
            pieces.append(f"{leading}{confirmed_clause}")
        else:
            pieces.append(leading)
    return _tidy("".join(pieces))


def repair_grounding_output(
    text: str,
    *,
    language: str,
    violations: Iterable[GroundingViolation] | None = None,
    inventory_confirmed: bool = False,
    grounded_amounts: Iterable[object] | None = None,
) -> GroundingOutputResult:
    """Apply the named deterministic repair to an explicit classification.

    `grounded_amounts` carries every sum of money verified for this turn --
    catalog rows read this turn plus figures the customer themselves wrote.
    Leave it `None` and the price check does not run at all, which is what the
    non-selling call sites want. Pass an empty collection and it runs against
    nothing, which is exactly right when no row was retrieved.
    """

    original = str(text or "")
    try:
        grounded_values = (
            tuple(grounded_amounts) if grounded_amounts is not None else None
        )
        grounded = _grounded_set(grounded_values)
        classified = (
            tuple(violations)
            if violations is not None
            else classify_grounding_output(
                original,
                inventory_confirmed=inventory_confirmed,
                grounded_amounts=grounded_values,
            )
        )
        if not classified:
            return GroundingOutputResult(
                text=original,
                violations=(),
                action=GroundingOutputAction.UNCHANGED,
            )

        repaired = _repair(
            original,
            inventory_confirmed=inventory_confirmed,
            grounded_amounts=grounded,
        )
        if repaired and not classify_grounding_output(
            repaired,
            inventory_confirmed=inventory_confirmed,
            grounded_amounts=grounded_values,
        ):
            return GroundingOutputResult(
                text=repaired,
                violations=classified,
                action=GroundingOutputAction.REPAIRED,
            )
        return GroundingOutputResult(
            text=_fallback(classified, language=language),
            violations=classified,
            action=GroundingOutputAction.REPLACED,
        )
    except Exception:
        return GroundingOutputResult(
            text=_fallback((), language=language),
            violations=(),
            action=GroundingOutputAction.REPLACED,
        )


# Compatibility name for existing callers. There is one repair function object;
# production and the acceptance harness use its explicit repair name.
enforce_grounding_output = repair_grounding_output
