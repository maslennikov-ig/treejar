"""High-precision policy for customer conversations that truly need a human."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.core.text_utils import ARABIC_INDIC_DIGITS as _ARABIC_INDIC_DIGITS
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
    # tj-r62i: a bulk quantity given in an earlier turn still routes, unless
    # this conversation's wholesale handoff already happened.
    if not metadata.get(WHOLESALE_HANDOFF_METADATA_KEY):
        wholesale = wholesale_handoff_from_history(None, recent_history)
        if wholesale.allowed:
            return wholesale

    external_order = external_order_support_decision(text, metadata)
    if external_order.allowed:
        return external_order

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
WHOLESALE_HANDOFF_METADATA_KEY = "wholesale_handoff_notified_at"
"""Set once a conversation's bulk order reached a manager (tj-r62i)."""
B2B_HANDOFF_TRIGGERS = frozenset(
    {
        "wholesale_or_bulk_project",
        "custom_made_to_order",
        "specialist_out_of_catalog_scope",
    }
)
NON_PAUSING_HANDOFF_TRIGGERS = frozenset(
    {"specialist_out_of_catalog_scope", "external_order_support"}
)
"""Routes that notify a manager without taking the conversation off the bot.

A sourcing request for equipment Treejar does not carry is a lead worth a
manager's look, but the customer usually asks it beside an ordinary question --
fume hoods and three workstations in one message -- and pausing the bot would
leave the workstation half unanswered.
"""

_BULK_ITEM_EN = (
    r"(?:pcs|pieces|units|nos|sets?|seats?|desks?|chairs?|work\s?stations?|"
    r"tables?|cabinets?|lockers?|pods?|sofas?|pedestals?|partitions?)"
)
# `tj-r62i` live pilot 2026-11-05: "Qty.350Nos" (350 workstations) never
# reached a manager. A quantity the customer labels as such is a quantity
# whatever follows it, so a "qty"/"quantity" prefix counts on its own.
_QUANTITY_PREFIX_RE = re.compile(
    r"\b(?:qty|qnty|quantity|quantities)\b\s*[.:=\-#]?\s*"
    r"(?:of\s+|about\s+|around\s+|approx\.?\s+|approximately\s+)?"
    r"(?P<count>\d{1,3}(?:,\d{3})+|\d+)(?!\d)(?![.,]\d)"
    r"(?!\s*(?:mm|cm|m|meters?|metres?|%)\b)"
    r"|(?:الكمية|كمية|العدد)\s*[:\-]?\s*(?P<ar_count>\d+)",
    re.IGNORECASE,
)
_COMPOUND_SET_QUANTITY_RE = re.compile(
    r"\b(?P<sets>\d+)\s*(?:sets?|tables?|desks?|work\s?stations?)\s*"
    r"(?:with|of|each\s+with|each\s+having|having|\*|x)\s*"
    r"(?P<items>\d+)\s*"
    r"(?:pcs|pieces|units|chairs?|desks?|seats?|tables?)\b"
    r"|\b(?P<items_alt>\d+)\s*(?:chairs?|seats?|pcs|pieces|units|desks?)\s*"
    r"(?:per|for\s+each|in\s+each)\s*(?:set|table|desk|work\s?station)\b.*?\b(?P<sets_alt>\d+)\s*(?:sets?|tables?|desks?)\b",
    re.IGNORECASE,
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
    total_items = 0
    for match in _WHOLESALE_QUANTITY_RE.finditer(text):
        if _follows_a_model_name(text, match.start()):
            continue
        try:
            value = int(match.group("count").replace(",", ""))
        except ValueError:
            continue
        largest = max(largest, value)
        total_items += value
    for match in _QUANTITY_PREFIX_RE.finditer(text):
        raw = match.group("count") or match.group("ar_count") or ""
        try:
            value = int(raw.replace(",", ""))
        except ValueError:
            continue
        largest = max(largest, value)
    for match in _COMPOUND_SET_QUANTITY_RE.finditer(text):
        sets_str = match.group("sets") or match.group("sets_alt")
        items_str = match.group("items") or match.group("items_alt")
        if sets_str and items_str:
            try:
                compound = int(sets_str) * int(items_str)
                largest = max(largest, compound)
            except ValueError:
                continue
    return max(largest, total_items)


def wholesale_quantity(customer_text: str | None) -> int:
    """The largest bulk quantity named in one customer message, or 0."""

    text = str(customer_text or "").translate(_ARABIC_INDIC_DIGITS)
    normalized = " ".join(text.split())
    if _NEGATED_B2B_RE.search(normalized):
        normalized = _NEGATED_B2B_RE.sub(" ", normalized)
    return _largest_bulk_quantity(normalized)


def wholesale_handoff_from_history(
    customer_text: str | None,
    recent_history: Sequence[str] = (),
) -> CriticalEscalationDecision:
    """A wholesale handoff earned by this turn or an earlier customer turn.

    `tj-r62i`. Customers split a bulk request across messages ("Qty.350Nos",
    then "Work station with cabinet"), so the current message alone misses
    it. Only customer lines (``user: ``) of the recent history are read, and
    only the wholesale route is carried across turns: a human request or an
    incident stays current-turn only.
    """

    texts = [str(customer_text or "")]
    for line in recent_history:
        line_text = str(line or "")
        if line_text.startswith("user:"):
            texts.append(line_text[len("user:") :])
    for text in texts:
        if "wholesale_or_bulk_project" in b2b_handoff_buckets(text):
            quantity = wholesale_quantity(text)
            detail = f" ({quantity} units)" if quantity else ""
            return CriticalEscalationDecision(
                allowed=True,
                escalation_type=EscalationType.GENERAL,
                reason=(
                    "B2B handoff: the customer asked for "
                    + _B2B_REASONS["wholesale_or_bulk_project"]
                    + detail
                    + "."
                ),
                trigger="wholesale_or_bulk_project",
            )
    return CriticalEscalationDecision(
        allowed=False,
        reason="No wholesale handoff route is present.",
        trigger="noncritical",
    )


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


_EXTERNAL_ORDER_REFERENCE_RE = re.compile(
    r"\b(?:b2c|b2b|web|ord|so|inv)-\d{4,}(?:-\d+)*\b"
    r"|\b(?:order|invoice)\s*(?:number|no\.?|id|ref(?:erence)?|#)\s*[:#\-]?\s*"
    r"(?=[a-z0-9\-]*\d)[a-z0-9][a-z0-9\-]{3,}\b"
    r"|(?:رقم\s+(?:ال)?(?:طلب|فاتورة))\s*[:#\-]?\s*"
    r"(?=[A-Za-z0-9\u0660-\u0669\-]*[\d\u0660-\u0669])[A-Za-z0-9\u0660-\u0669\-]{3,}",
    re.IGNORECASE,
)
_PAID_WEBSITE_ORDER_CONTEXT_RE = re.compile(
    r"\b(?:paid|ordered|purchased|bought)\s+(?:online|on\s+(?:the\s+|your\s+)?website)\b"
    r"|\bstatus\s*:\s*(?:completed|paid|processing)\b"
    r"|(?:دفعت|طلبت|اشتريت)\s+(?:عبر\s+|من\s+)?(?:الموقع|الإنترنت|الانترنت)",
    re.IGNORECASE,
)
_PAID_WEBSITE_ORDER_FOLLOWUP_RE = re.compile(
    r"\b(?:collect(?:ion)?|pick\s*up|ready|status|when\s+can\s+i|any\s+update)\b"
    r"|(?:استلام|جاهز|حالة\s+الطلب|متى)",
    re.IGNORECASE,
)


def external_order_support_decision(
    customer_text: str | None,
    conversation_metadata: Mapping[str, Any] | None = None,
) -> CriticalEscalationDecision:
    """Alert a manager (without pausing Noor) on unlinked website/order inquiries.

    2026-11-09 live pilot (*6040): a customer shared website order
    ``B2C-20261109-5702`` (`Status: Completed`) and asked if it was ready for
    showroom collection. ``check_order_status`` could not see website orders not
    linked to the WhatsApp conversation, and no manager was alerted.
    """

    metadata = conversation_metadata or {}
    if str(metadata.get("zoho_sale_order_id") or "").strip():
        return CriticalEscalationDecision(
            allowed=False,
            reason="Conversation already has a linked sale order.",
            trigger="noncritical",
        )
    text = str(customer_text or "").translate(_ARABIC_INDIC_DIGITS).strip()
    if not text:
        return CriticalEscalationDecision(
            allowed=False,
            reason="No external order reference is present.",
            trigger="noncritical",
        )
    has_order_ref = bool(_EXTERNAL_ORDER_REFERENCE_RE.search(text))
    has_paid_website_followup = bool(
        _PAID_WEBSITE_ORDER_CONTEXT_RE.search(text)
        and _PAID_WEBSITE_ORDER_FOLLOWUP_RE.search(text)
    )
    if has_order_ref or has_paid_website_followup:
        return CriticalEscalationDecision(
            allowed=True,
            escalation_type=EscalationType.GENERAL,
            reason=(
                "External order support: the customer referenced an existing "
                "or website order not linked to this WhatsApp conversation and "
                "needs human status or pickup confirmation."
            ),
            trigger="external_order_support",
        )
    return CriticalEscalationDecision(
        allowed=False,
        reason="No external order reference is present.",
        trigger="noncritical",
    )


def _quotation_status(metadata: Mapping[str, Any]) -> str:
    decision = metadata.get("quotation_decision")
    if isinstance(decision, Mapping):
        status = str(decision.get("status") or "").casefold()
        if status:
            return status
    return str(metadata.get("quotation_decision_status") or "").casefold()
