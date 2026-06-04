"""Guard against asking already answered customer-facing questions."""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.services.customer_language import is_arabic_customer_language


@dataclass(frozen=True)
class ClosedQuestionGuardResult:
    text: str
    repaired: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class _SlotQuestion:
    key: str
    known_label_en: str
    missing_label_en: str
    known_label_ar: str
    missing_label_ar: str


_CUSTOMER_NAME_SLOT = _SlotQuestion(
    key="customer_name",
    known_label_en="your name",
    missing_label_en="your name so I can address you properly",
    known_label_ar="اسمك",
    missing_label_ar="اسمك حتى أخاطبك بشكل صحيح",
)
_COMPANY_STATUS_SLOT = _SlotQuestion(
    key="company_status",
    known_label_en="your company or individual status",
    missing_label_en="your company name or confirm you are buying as an individual",
    known_label_ar="بيانات الشركة أو صفة الشراء الفردية",
    missing_label_ar="اسم الشركة أو تأكيد أنك تشتري كفرد",
)
_DELIVERY_ADDRESS_SLOT = _SlotQuestion(
    key="delivery_address",
    known_label_en="your delivery address",
    missing_label_en="your specific delivery address",
    known_label_ar="عنوان التوصيل",
    missing_label_ar="عنوان التوصيل المحدد",
)

_EN_CUSTOMER_NAME_QUESTION_SIGNALS = (
    "may i know your name",
    "can i have your name",
    "please share your name",
    "what is your name",
    "your name so i can address you",
)
_EN_COMPANY_STATUS_QUESTION_PATTERNS = (
    re.compile(
        r"\b(?:share|provide|send)\b[^.?!\n]{0,140}\b(?:company\s+name|company)\b"
    ),
    re.compile(r"\bwhat\s+is\s+your\s+company\s+name\b"),
    re.compile(r"\bconfirm\b[^.?!\n]{0,100}\b(?:individual|personal\s+use|company)\b"),
    re.compile(
        r"\b(?:share|provide|send)\b[^.?!\n]{0,140}"
        r"\b(?:buying|purchase|purchasing)\s+as\s+(?:an\s+)?individual\b"
    ),
)
_EN_DELIVERY_ADDRESS_QUESTION_PATTERNS = (
    re.compile(
        r"\b(?:share|provide|send)\b[^.?!\n]{0,140}"
        r"\b(?:specific\s+)?delivery\s+address\b"
    ),
    re.compile(
        r"\b(?:share|provide|send)\b[^.?!\n]{0,140}"
        r"\b(?:specific\s+)?address\b"
    ),
    re.compile(r"\bwhat\s+is\s+your\s+(?:specific\s+)?(?:delivery\s+)?address\b"),
    re.compile(
        r"\b(?:need|needs|required|requires?)\b[^.?!\n]{0,140}"
        r"\b(?:specific\s+)?delivery\s+address\b"
    ),
)
_AR_CUSTOMER_NAME_QUESTION_SIGNALS = (
    "اسمك",
    "أخاطبك",
    "اخاطبك",
    "أناديك",
    "اناديك",
    "مناداتك",
)
_AR_COMPANY_STATUS_QUESTION_SIGNALS = (
    "اسم الشركة",
    "شركة",
    "كفرد",
    "فرد",
)
_AR_DELIVERY_ADDRESS_QUESTION_SIGNALS = (
    "عنوان التوصيل",
    "عنوانك",
    "العنوان",
)
_AR_REQUEST_SIGNALS = (
    "يرجى",
    "رجاء",
    "شارك",
    "شاركي",
    "أرسل",
    "ارسل",
    "زوّد",
    "زود",
    "ما هو",
    "ماهي",
    "ما هي",
    "أكد",
    "تأكيد",
)


def response_asks_customer_name(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    if not normalized:
        return False
    return any(
        signal in normalized for signal in _EN_CUSTOMER_NAME_QUESTION_SIGNALS
    ) or _arabic_request_mentions(str(text or ""), _AR_CUSTOMER_NAME_QUESTION_SIGNALS)


def _arabic_request_mentions(raw_text: str, signals: tuple[str, ...]) -> bool:
    return any(request in raw_text for request in _AR_REQUEST_SIGNALS) and any(
        signal in raw_text for signal in signals
    )


def _response_asks_company_status(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    if any(
        pattern.search(normalized) for pattern in _EN_COMPANY_STATUS_QUESTION_PATTERNS
    ):
        return True
    return _arabic_request_mentions(
        str(text or ""), _AR_COMPANY_STATUS_QUESTION_SIGNALS
    )


def _response_asks_delivery_address(text: str) -> bool:
    normalized = " ".join(str(text or "").casefold().split())
    if any(
        pattern.search(normalized) for pattern in _EN_DELIVERY_ADDRESS_QUESTION_PATTERNS
    ):
        return True
    return _arabic_request_mentions(
        str(text or ""), _AR_DELIVERY_ADDRESS_QUESTION_SIGNALS
    )


def _join_labels(labels: list[str], *, language: str) -> str:
    if not labels:
        return ""
    if len(labels) == 1:
        return labels[0]
    if is_arabic_customer_language(language):
        return " و".join(labels)
    if len(labels) == 2:
        return f"{labels[0]} and {labels[1]}"
    return f"{', '.join(labels[:-1])}, and {labels[-1]}"


def _slot_value(value: str | None) -> str:
    return str(value or "").strip()


def _is_standalone_slot_question(text: str) -> bool:
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if "\n" in stripped or "|" in stripped:
        return False
    return len(stripped) <= 240


def apply_closed_question_guard(
    text: str,
    *,
    language: str,
    customer_name: str | None,
    company: str | None = None,
    customer_type: str | None = None,
    delivery_address: str | None = None,
) -> ClosedQuestionGuardResult:
    """Repair generated replies that ask for a slot already known by state."""
    asked_slots: list[_SlotQuestion] = []
    if response_asks_customer_name(text):
        asked_slots.append(_CUSTOMER_NAME_SLOT)
    if _response_asks_company_status(text):
        asked_slots.append(_COMPANY_STATUS_SLOT)
    if _response_asks_delivery_address(text):
        asked_slots.append(_DELIVERY_ADDRESS_SLOT)
    if not asked_slots:
        return ClosedQuestionGuardResult(text=text)

    known_values = {
        "customer_name": _slot_value(customer_name),
        "company_status": _slot_value(company) or _slot_value(customer_type),
        "delivery_address": _slot_value(delivery_address),
    }
    known_asked_slots = [slot for slot in asked_slots if known_values.get(slot.key)]
    if not known_asked_slots:
        return ClosedQuestionGuardResult(text=text)
    if not _is_standalone_slot_question(text):
        return ClosedQuestionGuardResult(text=text)

    missing_asked_slots = [
        slot for slot in asked_slots if not known_values.get(slot.key)
    ]
    name = _slot_value(customer_name)
    if is_arabic_customer_language(language):
        greeting = f"شكرًا، {name}." if name else "شكرًا."
        known_labels = _join_labels(
            [slot.known_label_ar for slot in known_asked_slots],
            language=language,
        )
        if missing_asked_slots:
            missing_labels = _join_labels(
                [slot.missing_label_ar for slot in missing_asked_slots],
                language=language,
            )
            repaired = (
                f"{greeting} لدي {known_labels} بالفعل. يرجى مشاركة {missing_labels}."
            )
        else:
            repaired = f"{greeting} لدي {known_labels} بالفعل، وسأتابع طلبك."
    else:
        greeting = f"Thank you, {name}." if name else "Thank you."
        known_labels = _join_labels(
            [slot.known_label_en for slot in known_asked_slots],
            language=language,
        )
        if missing_asked_slots:
            missing_labels = _join_labels(
                [slot.missing_label_en for slot in missing_asked_slots],
                language=language,
            )
            repaired = f"{greeting} I already have {known_labels}. Please share {missing_labels}."
        else:
            repaired = (
                f"{greeting} I already have {known_labels}, so I will continue "
                "with your request."
            )
    return ClosedQuestionGuardResult(
        text=repaired,
        repaired=True,
        reason="answered_slots_already_known",
    )
