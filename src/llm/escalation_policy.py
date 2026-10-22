"""High-precision policy for customer conversations that truly need a human."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.llm.money import BUDGET_AR_CURRENCY_PATTERN
from src.schemas.common import EscalationType


@dataclass(frozen=True, slots=True)
class CriticalEscalationDecision:
    """Whether the current customer turn may pause the bot for a manager."""

    allowed: bool
    escalation_type: EscalationType | None = None
    reason: str = ""
    trigger: str = ""


_HUMAN_ACTION_RE = re.compile(
    r"\b(?:speak|talk|connect|transfer|put\s+me\s+through|reach)\b"
    r".{0,45}\b(?:manager|human|person|agent|representative|team\s+member|salesperson)\b"
    r"|\b(?:manager|human|agent|representative)\s*(?:,\s*)?(?:please|now)\b",
    re.IGNORECASE | re.DOTALL,
)
_DIRECT_HUMAN_REQUEST_RE = re.compile(
    r"\b(?:i|we)\s+(?:want|need|request)\s+(?:a\s+|an\s+)?"
    r"(?:manager|human|person|agent|representative|team\s+member)\b"
    r"|\bcan\s+i\s+(?:get|have)\s+(?:a\s+|an\s+)?"
    r"(?:manager|human|person|agent|representative)\b",
    re.IGNORECASE,
)
_NEGATED_HUMAN_REQUEST_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|no\s+longer)\s+(?:want|need|request|wish)"
    r".{0,35}\b(?:manager|human|person|agent|representative|callback)\b"
    r"|\bno\s+(?:manager|human|agent|representative|callback)\s+please\b",
    re.IGNORECASE | re.DOTALL,
)
_CALLBACK_RE = re.compile(
    r"^(?:please\s+)?(?:call|phone|contact)\s+(?:me|us)\b"
    r"|\b(?:can|could|would)\s+(?:you|someone|a\s+manager|your\s+team)"
    r"\s+(?:please\s+)?(?:call|phone|contact)\s+(?:me|us)\b"
    r"|\b(?:have|ask)\s+(?:someone|a\s+manager|your\s+team|a\s+team\s+member)"
    r"\s+(?:call|phone|contact)\s+(?:me|us)\b",
    re.IGNORECASE,
)
_ARABIC_HUMAN_RE = re.compile(
    r"(?:أريد|اريد|أحتاج|احتاج|حولني|حوّلني|توصيلي|التحدث|أتحدث|اتحدث|تكلم)"
    r".{0,35}(?:مدير|موظف|شخص|إنسان|انسان|ممثل)"
    r"|(?:اتصلوا|تواصلوا)\s+بي",
    re.DOTALL,
)
_ARABIC_PRODUCT_MANAGER_RE = re.compile(
    r"(?:كرسي|مكتب|طاولة|محطة\s+عمل)\s+(?:ال)?مدير",
)
_PRODUCT_MANAGER_RE = re.compile(
    r"\bmanager(?:'s)?\s+(?:desk|table|chair|office|workstation)\b",
    re.IGNORECASE,
)

_ORDER_CONTEXT_RE = re.compile(
    r"\b(?:my|our|the)\s+(?:order|delivery|shipment|invoice|payment|purchase)\b"
    r"|\b(?:arrived|delivered|received|charged)\b",
    re.IGNORECASE,
)
_ORDER_INCIDENT_RE = re.compile(
    r"\b(?:damaged|broken|wrong|missing|lost|late|delayed|not\s+arrived|"
    r"not\s+delivered|overcharged|charged\s+twice|duplicate\s+charge|"
    r"unauthori[sz]ed|cancel(?:led|ation)?)\b",
    re.IGNORECASE,
)
_NEGATED_ORDER_INCIDENT_RE = re.compile(
    r"\bnot\s+(?:damaged|broken|wrong|missing|lost|late|delayed|overcharged)\b",
    re.IGNORECASE,
)
_DIRECT_REFUND_RE = re.compile(
    r"\b(?:i|we)\s+(?:want|need|request)\s+(?:a\s+)?"
    r"(?:refund|return|exchange)\b(?!\s+(?:policy|terms|rules|procedure|information)\b)"
    r"|\b(?:refund|return|exchange)\s+(?:my|our|this|the)\b"
    r"|\bmoney\s+back\b",
    re.IGNORECASE,
)
_LEGAL_SAFETY_RE = re.compile(
    r"\b(?:legal\s+action|my\s+lawyer|our\s+lawyer|contact(?:ing)?\s+(?:a\s+)?"
    r"(?:lawyer|solicitor|police)|take\s+you\s+to\s+court|this\s+is\s+fraud|"
    r"report(?:ing)?\s+fraud|fraudulent\s+charge|stolen\s+card|"
    r"unauthori[sz]ed\s+charge|electric\s+shock|fire\s+hazard|"
    r"(?:i|we|someone)\s+(?:was|were|got)?\s*injur(?:ed|y)|"
    r"(?:this|the|your|my|our)\s+\w+(?:\s+\w+){0,4}\s+is\s+unsafe)\b",
    re.IGNORECASE,
)
_PAYMENT_INCIDENT_RE = re.compile(
    r"\b(?:my|our|the)\s+payment\s+(?:failed|declined|pending|stuck)\b"
    r"|\bpayment\s+(?:did\s+not|didn't|has\s+not|hasn't)\s+go\s+through\b",
    re.IGNORECASE,
)
_ARABIC_INCIDENT_RE = re.compile(
    r"(?:شكوى|استرداد|إرجاع|ارجاع|تالف|مكسور|طلب\s+خاطئ|لم\s+يصل|متأخر|"
    r"محامي|إجراء\s+قانوني|اجراء\s+قانوني|شرطة|احتيال|خطر|إصابة|اصابة)",
)
_ARABIC_POLICY_INFORMATION_RE = re.compile(
    r"(?:سياسة|شروط|قواعد|طريقة|كيفية)\s+(?:ال)?(?:استرداد|إرجاع|ارجاع)"
    r"|(?:ال)?(?:استرداد|إرجاع|ارجاع)\s+(?:سياسة|شروط|قواعد)",
)

_EXPLICIT_QUOTE_ACCEPTANCE_RE = re.compile(
    r"\b(?:i|we)\s+(?:accept|approve|confirm)\s+(?:(?:the|your|this)\s+)?"
    r"(?:quote|quotation|proposal|order|purchase)\b"
    r"|\b(?:proceed|go\s+ahead|place|finali[sz]e)\s+"
    r"(?:(?:with|on)\s+)?(?:(?:the|my|our|this)\s+)?"
    r"(?:quote|quotation|proposal|order|purchase)\b",
    re.IGNORECASE | re.DOTALL,
)
_NEGATED_QUOTE_ACCEPTANCE_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|cannot|can't|cant|never)\b.{0,20}"
    r"\b(?:accept|approve|confirm|proceed|go\s+ahead|place|finali[sz]e|want)\b"
    r"|\b(?:reject|decline|cancel)\b.{0,20}"
    r"\b(?:quote|quotation|proposal|order|purchase)\b",
    re.IGNORECASE | re.DOTALL,
)
_APPROVED_QUOTE_STATUSES = frozenset({"approved", "accepted", "confirmed"})


def customer_text_for_escalation(
    customer_text: str | None,
    recent_history: Sequence[str] = (),
) -> str:
    """Never treat a historical customer request as a new critical turn."""

    return str(customer_text or "").strip()


def critical_escalation_decision(
    *,
    customer_text: str | None,
    conversation_metadata: Mapping[str, Any] | None = None,
    recent_history: Sequence[str] = (),
    quote_acceptance_recorded_this_turn: bool = False,
) -> CriticalEscalationDecision:
    """Allow a handoff only for a narrow, customer-evidenced critical case."""

    text = customer_text_for_escalation(customer_text, recent_history)
    normalized = " ".join(text.casefold().split()).strip(" .!?،؟")
    without_product_manager = _PRODUCT_MANAGER_RE.sub("", normalized)
    without_arabic_product_manager = _ARABIC_PRODUCT_MANAGER_RE.sub("", text)

    if not _NEGATED_HUMAN_REQUEST_RE.search(without_product_manager) and (
        _HUMAN_ACTION_RE.search(without_product_manager)
        or _DIRECT_HUMAN_REQUEST_RE.search(without_product_manager)
        or _CALLBACK_RE.search(without_product_manager)
        or _ARABIC_HUMAN_RE.search(without_arabic_product_manager)
    ):
        return CriticalEscalationDecision(
            allowed=True,
            escalation_type=EscalationType.HUMAN_REQUESTED,
            reason="Critical escalation: the customer explicitly requested a human response.",
            trigger="explicit_human_request",
        )

    metadata = conversation_metadata or {}
    quote_acceptance_is_negated = bool(_NEGATED_QUOTE_ACCEPTANCE_RE.search(normalized))
    accepted_prepared_quote = (
        not quote_acceptance_is_negated
        and _quotation_is_approved(metadata)
        and (
            quote_acceptance_recorded_this_turn
            or _EXPLICIT_QUOTE_ACCEPTANCE_RE.search(normalized)
        )
    )
    if accepted_prepared_quote:
        return CriticalEscalationDecision(
            allowed=True,
            escalation_type=EscalationType.ORDER_CONFIRMATION,
            reason="Critical escalation: the customer accepted a prepared quotation and human order processing is required.",
            trigger="accepted_quotation",
        )

    incident_text = _NEGATED_ORDER_INCIDENT_RE.sub("", normalized)
    arabic_incident_text = _ARABIC_POLICY_INFORMATION_RE.sub("", text)
    if (
        _LEGAL_SAFETY_RE.search(normalized)
        or _PAYMENT_INCIDENT_RE.search(normalized)
        or _ARABIC_INCIDENT_RE.search(arabic_incident_text)
        or _DIRECT_REFUND_RE.search(normalized)
        or (
            _ORDER_CONTEXT_RE.search(normalized)
            and _ORDER_INCIDENT_RE.search(incident_text)
        )
    ):
        return CriticalEscalationDecision(
            allowed=True,
            escalation_type=EscalationType.GENERAL,
            reason="Critical escalation: the customer reported an existing-order, payment, legal, or safety incident.",
            trigger="critical_customer_incident",
        )

    b2b_decision = b2b_handoff_decision(text)
    if b2b_decision.allowed:
        return b2b_decision

    return CriticalEscalationDecision(
        allowed=False,
        reason="No critical customer-evidenced escalation trigger is present.",
        trigger="noncritical",
    )


# `tj-asty.2`. Victor's handoff rule for the Treejar line (2026-10-22): "the
# client goes to a manager for a wholesale order, for goods made to order, and
# when the bot is unsure". These three routes are narrow on purpose: an
# ordinary office-furniture question, a no-match search or "no quotation yet"
# never reaches them, because a handoff pauses the bot.
WHOLESALE_QUANTITY_THRESHOLD = 20
B2B_HANDOFF_TRIGGERS = frozenset(
    {
        "wholesale_or_bulk_project",
        "custom_made_to_order",
        "specialist_out_of_catalog_scope",
    }
)
NON_PAUSING_HANDOFF_TRIGGERS = frozenset({"specialist_out_of_catalog_scope"})
"""Routes that notify a manager without taking the conversation off the bot.

A sourcing request for equipment Treejar does not carry is a lead worth a
manager's look, but the customer usually asks it beside an ordinary question --
fume hoods and three workstations in one message -- and pausing the bot would
leave the workstation half unanswered.
"""

_ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
_BULK_ITEM_EN = (
    r"(?:pcs|pieces|units|seats?|desks?|chairs?|work\s?stations?|tables?|"
    r"cabinets?|lockers?|pods?|sofas?|pedestals?|partitions?)"
)
_BULK_ITEM_AR = (
    r"(?:محطات\s+عمل|محطة\s+عمل|محطات|مكاتب|مكتب|كراسي|كرسي|مقاعد|مقعد|"
    r"طاولات|طاولة|وحدات|وحدة|قطع|قطعة|خزائن|خزانة)"
)
_WHOLESALE_QUANTITY_RE = re.compile(
    r"(?<![\d.,\-])(?P<count>\d{1,3}(?:,\d{3})+|\d+)(?![\d\-]|\.\d)"
    # A dimension or a price is not a quantity: "2400 mm", "1600x800".
    rf"(?!\s*(?:mm|cm|m|meters?|metres?|%|متر|سم|{BUDGET_AR_CURRENCY_PATTERN})(?:\b|\s|$))"
    r"(?!\s*[x×*]\s*\d)\s*"
    r"(?:x\s*|×\s*)?"
    rf"(?:(?:[a-z][a-z\-]*\s+){{0,2}}{_BULK_ITEM_EN}\b|{_BULK_ITEM_AR})",
    re.IGNORECASE,
)
_WHOLESALE_PRICING_RE = re.compile(
    r"\b(?:wholesale|bulk|volume|trade|project|tender)\s+"
    r"(?:discount|price|prices|pricing|rate|rates|deal|offer|terms)\b"
    r"|\b(?:special|better|best)\s+(?:wholesale|bulk|volume|project)\s+"
    r"(?:price|prices|pricing|rate|rates|discount|deal|offer)\b"
    r"|\bdiscount\s+for\s+(?:a\s+)?(?:bulk|wholesale|large|big)\s+(?:order|quantity|quantities)\b"
    r"|\b(?:wholesale|bulk)\s+order\b"
    r"|\btender\b|\bboq\b|\bbill\s+of\s+quantities\b"
    r"|خصم\s+(?:ال)?(?:جملة|كميات|كمية)|(?:سعر|أسعار|اسعار)\s+(?:ال)?جملة"
    r"|بالجملة|طلب\s+جملة|عرض\s+سعر\s+خاص\s+(?:لل)?(?:كميات|كمية)|مناقصة",
    re.IGNORECASE,
)
_CUSTOM_MADE_TO_ORDER_RE = re.compile(
    r"\bcustom(?:ised|ized)?[\s-]+(?:made|built|size[ds]?|sizing|dimensions?|"
    r"design(?:ed)?|manufactur\w*|fabricat\w*|furniture|table|desk|"
    r"workstation|cabinet|joinery|carpentry|\d)"
    r"|\bmade[\s-]to[\s-](?:order|measure)\b|\bbespoke\b|\btailor[\s-]?made\b"
    r"|\bbuilt[\s-]?in\s+(?:power|electrical|electric|sockets?|outlets?)\b"
    r"|\bnon[\s-]?standard\s+(?:size|sizes|dimensions?)\b"
    r"|\bspecial\s+(?:size|sizes|dimensions?)\b"
    r"|تفصيل\s+(?:\S+\s+)?(?:طاولة|طاولات|مكتب|مكاتب|أثاث|اثاث|خزائن|خزانة)"
    r"|حسب\s+الطلب|مقاس(?:ات)?\s+خاص(?:ة)?|تصنيع\s+خاص"
    r"|(?:وحدات|مقابس)\s+كهرباء\s+مدمجة",
    re.IGNORECASE,
)
_SPECIALIST_OUT_OF_CATALOG_RE = re.compile(
    r"\bfume\s+(?:hoods?|cupboards?|cabinets?)\b|\bchemical\s+hoods?\b"
    r"|\bbiosafety\s+cabinets?\b|\blaminar\s+flow\b|\bautoclaves?\b"
    r"|\bdental\s+chairs?\b|\bhospital\s+beds?\b|\bexamination\s+(?:beds?|couch(?:es)?)\b"
    r"|\b(?:lab|laboratory)\s+equipment\b|\bmedical\s+(?:equipment|devices?)\b"
    r"|خزان(?:ة|ات)\s+(?:ال)?أبخرة|شفاط(?:ات)?\s+(?:ال)?مختبر|معدات\s+(?:ال)?مختبر"
    r"|أجهزة\s+(?:ال)?تعقيم|سرير\s+مستشفى|كرسي\s+(?:ال)?أسنان",
    re.IGNORECASE,
)
_NEGATED_B2B_RE = re.compile(
    r"\b(?:not|no|don't|dont|do\s+not)\s+(?:a\s+)?(?:wholesale|bulk|custom)\b",
    re.IGNORECASE,
)


_MODEL_SERIES_WORDS = frozenset(
    {"luma", "novo", "skyland", "ch", "model", "series", "sku", "code", "ref"}
)


def _follows_a_model_name(text: str, start: int) -> bool:
    """``NOVO 2400 tables`` names a model, not 2,400 tables."""

    preceding = text[:start].rstrip().rsplit(maxsplit=1)
    if not preceding:
        return False
    word = preceding[-1].strip(".,:;()[]")
    if word.casefold() in _MODEL_SERIES_WORDS:
        return True
    return len(word) >= 2 and word.isascii() and word.isalpha() and word.isupper()


def _largest_bulk_quantity(text: str) -> int:
    largest = 0
    for match in _WHOLESALE_QUANTITY_RE.finditer(text):
        if _follows_a_model_name(text, match.start()):
            continue
        try:
            value = int(match.group("count").replace(",", ""))
        except ValueError:
            continue
        largest = max(largest, value)
    return largest


def b2b_handoff_buckets(customer_text: str | None) -> tuple[str, ...]:
    """Every B2B handoff route this customer message earns, in priority order."""

    text = str(customer_text or "").translate(_ARABIC_INDIC_DIGITS)
    if not text.strip():
        return ()
    # Case is kept: every pattern here ignores case, and the model-name check
    # needs to see that "NOVO" was written in capitals.
    normalized = " ".join(text.split())
    if _NEGATED_B2B_RE.search(normalized):
        normalized = _NEGATED_B2B_RE.sub(" ", normalized)
    buckets: list[str] = []
    if _largest_bulk_quantity(
        normalized
    ) >= WHOLESALE_QUANTITY_THRESHOLD or _WHOLESALE_PRICING_RE.search(normalized):
        buckets.append("wholesale_or_bulk_project")
    if _CUSTOM_MADE_TO_ORDER_RE.search(normalized):
        buckets.append("custom_made_to_order")
    if _SPECIALIST_OUT_OF_CATALOG_RE.search(normalized):
        buckets.append("specialist_out_of_catalog_scope")
    return tuple(buckets)


_B2B_REASONS = {
    "wholesale_or_bulk_project": "a wholesale or bulk project order (20+ units or bulk pricing)",
    "custom_made_to_order": "furniture made to order (custom dimensions, materials or built-in power)",
    "specialist_out_of_catalog_scope": "specialist equipment outside the office furniture catalog",
}


def b2b_handoff_decision(customer_text: str | None) -> CriticalEscalationDecision:
    """Treejar's B2B handoff routes for the current customer message."""

    buckets = b2b_handoff_buckets(customer_text)
    if not buckets:
        return CriticalEscalationDecision(
            allowed=False,
            reason="No B2B handoff route is present.",
            trigger="noncritical",
        )
    primary = buckets[0]
    return CriticalEscalationDecision(
        allowed=True,
        escalation_type=EscalationType.GENERAL,
        reason=(
            "B2B handoff: the customer asked for "
            + "; ".join(_B2B_REASONS[bucket] for bucket in buckets)
            + "."
        ),
        trigger=primary,
    )


def _quotation_is_approved(metadata: Mapping[str, Any]) -> bool:
    return _quotation_status(metadata) in _APPROVED_QUOTE_STATUSES


def _quotation_status(metadata: Mapping[str, Any]) -> str:
    decision = metadata.get("quotation_decision")
    if isinstance(decision, Mapping):
        status = str(decision.get("status") or "").casefold()
        if status:
            return status
    return str(metadata.get("quotation_decision_status") or "").casefold()
