"""High-precision policy for customer conversations that truly need a human."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

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
    r"\b(?:i|we)\s+(?:want|need|request)\s+(?:a\s+)?(?:refund|return|exchange)\b"
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

_ORDER_FINALIZATION_RE = re.compile(
    r"\b(?:accept|approve|confirm|proceed|go\s+ahead|place|finali[sz]e)\b"
    r".{0,35}\b(?:quote|quotation|proposal|order|purchase)?\b",
    re.IGNORECASE | re.DOTALL,
)
_EXPLICIT_QUOTE_ACCEPTANCE_RE = re.compile(
    r"\b(?:accept|approve|confirm|proceed|go\s+ahead|place|finali[sz]e)\b"
    r".{0,35}\b(?:quote|quotation|proposal|order|purchase)\b"
    r"|\b(?:quote|quotation|proposal|order|purchase)\b"
    r".{0,35}\b(?:accept|approve|confirm|proceed|go\s+ahead|place|finali[sz]e)\b",
    re.IGNORECASE | re.DOTALL,
)
_NEGATED_QUOTE_ACCEPTANCE_RE = re.compile(
    r"\b(?:do\s+not|don't|dont|cannot|can't|cant|never)\b.{0,20}"
    r"\b(?:accept|approve|confirm|proceed|go\s+ahead|place|finali[sz]e|want)\b"
    r"|\b(?:reject|decline|cancel)\b.{0,20}"
    r"\b(?:quote|quotation|proposal|order|purchase)\b",
    re.IGNORECASE | re.DOTALL,
)
_AFFIRMATIVE_REPLIES = frozenset(
    {
        "yes",
        "yes please",
        "approved",
        "accepted",
        "i accept",
        "we accept",
        "go ahead",
        "proceed",
        "نعم",
        "موافق",
    }
)
_GENERIC_AFFIRMATIVE_REPLIES = frozenset(
    {"yes", "yes please", "go ahead", "proceed", "نعم", "موافق"}
)
_QUOTE_APPROVAL_PROMPT_CUES = (
    "quotation works",
    "quotation work",
    "proposal works",
    "proposal work",
    "offer works",
    "offer work",
    "approve the quotation",
    "accept the quotation",
    "proceed with the quotation",
    "هل يناسبك العرض",
)
_APPROVED_QUOTE_STATUSES = frozenset({"approved", "accepted", "confirmed"})


def customer_text_for_escalation(
    customer_text: str | None,
    recent_history: Sequence[str] = (),
) -> str:
    """Return the current customer turn without trusting assistant history."""

    direct = str(customer_text or "").strip()
    if direct:
        return direct
    for entry in reversed(recent_history):
        role, separator, content = str(entry).partition(":")
        if separator and role.strip().casefold() == "user" and content.strip():
            return content.strip()
    return ""


def critical_escalation_decision(
    *,
    customer_text: str | None,
    conversation_metadata: Mapping[str, Any] | None = None,
    recent_history: Sequence[str] = (),
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
            normalized in _AFFIRMATIVE_REPLIES
            or _ORDER_FINALIZATION_RE.search(normalized)
        )
    )
    explicit_pending_quote_acceptance = (
        _quotation_is_awaiting_acceptance(metadata)
        and not quote_acceptance_is_negated
        and (
            _EXPLICIT_QUOTE_ACCEPTANCE_RE.search(normalized)
            or (
                normalized in _GENERIC_AFFIRMATIVE_REPLIES
                and _last_assistant_asked_quote_approval(recent_history)
            )
        )
    )
    if accepted_prepared_quote or explicit_pending_quote_acceptance:
        return CriticalEscalationDecision(
            allowed=True,
            escalation_type=EscalationType.ORDER_CONFIRMATION,
            reason="Critical escalation: the customer accepted a prepared quotation and human order processing is required.",
            trigger="accepted_quotation",
        )

    incident_text = _NEGATED_ORDER_INCIDENT_RE.sub("", normalized)
    if (
        _LEGAL_SAFETY_RE.search(normalized)
        or _PAYMENT_INCIDENT_RE.search(normalized)
        or _ARABIC_INCIDENT_RE.search(text)
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

    return CriticalEscalationDecision(
        allowed=False,
        reason="No critical customer-evidenced escalation trigger is present.",
        trigger="noncritical",
    )


def _quotation_is_approved(metadata: Mapping[str, Any]) -> bool:
    return _quotation_status(metadata) in _APPROVED_QUOTE_STATUSES


def _quotation_is_awaiting_acceptance(metadata: Mapping[str, Any]) -> bool:
    if _quotation_status(metadata) != "pending":
        return False
    proposal = metadata.get("proposal_followup")
    decision = metadata.get("quotation_decision")
    return bool(
        (isinstance(proposal, Mapping) and proposal.get("sent_at"))
        or (isinstance(decision, Mapping) and decision.get("sent_at"))
    )


def _quotation_status(metadata: Mapping[str, Any]) -> str:
    decision = metadata.get("quotation_decision")
    if isinstance(decision, Mapping):
        status = str(decision.get("status") or "").casefold()
        if status:
            return status
    return str(metadata.get("quotation_decision_status") or "").casefold()


def _last_assistant_asked_quote_approval(recent_history: Sequence[str]) -> bool:
    for entry in reversed(recent_history):
        role, separator, content = str(entry).partition(":")
        if separator and role.strip().casefold() == "assistant":
            normalized = " ".join(content.casefold().split())
            return any(cue in normalized for cue in _QUOTE_APPROVAL_PROMPT_CUES)
    return False
