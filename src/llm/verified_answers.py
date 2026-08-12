from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from src.services.customer_language import is_arabic_customer_language

QuestionClass = Literal["product", "service_low_risk", "service_high_risk", "social"]
SocialIntent = Literal["greeting", "gratitude", "goodbye", "assist_opener"]
FaqSupport = Literal["verified", "partial", "missing"]
PolicyAction = Literal["allow", "clarify", "handoff"]
ProductMatch = Literal["exact", "nearby", "missing"]
SalesFallbackIntent = Literal["price_objection", "retention", "off_catalog"]

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_UNICODE_TOKEN_RE = re.compile(r"[\w']+", re.UNICODE)
_WEEKDAY_PATTERN = r"monday|tuesday|wednesday|thursday|friday|saturday|sunday"
# `next` on its own is not a date. It reads as one in "the best next step", and
# that single word was enough to promote a summary request to a high-risk
# commitment question. It counts only when a time unit follows it.
_DATE_RE = re.compile(
    r"\b(?:today|tomorrow|tonight|"
    rf"next\s+(?:week|month|year|quarter|day|{_WEEKDAY_PATTERN})|"
    rf"{_WEEKDAY_PATTERN}|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}[/-]\d{1,2})\b",
    re.IGNORECASE,
)
_NUMBER_RE = re.compile(r"\b\d+(?:[-/]\d+)?\b")

_STOPWORDS = frozenset(
    {
        "a",
        "about",
        "across",
        "all",
        "an",
        "and",
        "are",
        "at",
        "can",
        "do",
        "for",
        "have",
        "how",
        "i",
        "in",
        "is",
        "me",
        "my",
        "of",
        "on",
        "or",
        "our",
        "please",
        "tell",
        "the",
        "their",
        "there",
        "they",
        "to",
        "we",
        "what",
        "when",
        "where",
        "with",
        "you",
        "your",
    }
)
_PRODUCT_SIGNALS = (
    "chair",
    "chairs",
    "desk",
    "desks",
    "pod",
    "pods",
    "booth",
    "booths",
    "bench",
    "benches",
    "cabinet",
    "cabinets",
    "drawer",
    "drawers",
    "imago",
    "mobile drawer",
    "mobile drawers",
    "novo",
    "pedestal",
    "pedestals",
    "skyland",
    "storage",
    "workstation",
    "workstations",
    "work station",
    "work stations",
    "table",
    "tables",
    "trend",
    "xten",
    "sofa",
    "sofas",
    "catalog",
    "sku",
    "model",
    "price",
    "stock",
    "spec",
    "specs",
    "ergonomic",
    "furniture",
    "كرسي",
    "كراسي",
    "أثاث",
    "اثاث",
    "مكتب",
    "مكاتب",
    "محطة عمل",
    "محطات عمل",
    "طاولة",
    "طاولات",
)
_PRODUCT_SIGNAL_TOKENS = frozenset(
    {
        "bed",
        "beds",
        "bookcase",
        "bookcases",
        "bookshelf",
        "bookshelves",
        "locker",
        "lockers",
        "mattress",
        "mattresses",
        "shelf",
        "shelves",
        "wardrobe",
        "wardrobes",
    }
)
_COMPACT_PRODUCT_SIGNALS = tuple(
    re.sub(r"[\s-]+", "", signal)
    for signal in _PRODUCT_SIGNALS
    if re.search(r"[a-z]", signal)
)
_PRODUCT_SELECTION_QUANTITY_RE = re.compile(
    r"(?:^|[^\w])\d{1,4}\s*(?:x|×)?\s*[\w'-]+",
    re.IGNORECASE | re.UNICODE,
)
_SKU_SELECTION_SIGNAL_RE = re.compile(
    r"\b(?:"
    r"[a-z]{1,4}[-\s]?\d{2,8}|"
    r"\d{2,}(?:-\d{1,})+|"
    r"[a-z0-9]+(?:[-.][a-z0-9]+)+"
    r")\b",
    re.IGNORECASE,
)
# A SKU written the way a person types it, with nothing between the letters and
# the digits. `tj-jxv7`, 2026-08-09: "hi do u have ch616 in black" classified as
# `service_low_risk`, because the message carries no product word and
# `_NUMBER_RE` needs a word boundary in front of its digits, which "ch616" does
# not give it. The turn then ran under the service directives -- answer only
# from the FAQ, do not state a price -- with an empty FAQ, so a customer asking
# whether we stock a chair we do stock was asked for a quantity instead.
#
# The letters and digits must be adjacent here. The spaced and hyphenated forms
# already reach `product` through `_SKU_SELECTION_SIGNAL_RE`, and allowing a
# separator would read "for 12" and "AED 300" as SKUs. Cyrillic letters count
# because the catalogue itself is written with them: 7 of 920 Treejar SKUs begin
# with Cyrillic "СН".
_COMPACT_SKU_RE = re.compile(
    r"\b[a-zА-я]{2,4}\d{2,8}\b",
    re.IGNORECASE,
)
_PRODUCT_DISCOVERY_PHRASES = (
    "anything for",
    "options",
    "what options",
    "show me",
    "tell me about",
    "looking for",
    "what do you have",
    "recommend",
    "pricing",
    "price",
    "stock",
    "catalog",
)
_CATALOG_DISCOVERY_CONTEXT_TERMS = (
    "apartment",
    "bedroom",
    "cafe",
    "children",
    "dining room",
    "hotel",
    "kids",
    "living room",
    "lounge",
    "reception area",
    "restaurant",
    "villa",
    "waiting area",
)
_BENIGN_PREFERENCE_PHRASES = (
    "i prefer",
    "we prefer",
    "prefer more",
    "prefer the",
    "more open",
    "more private",
    "open for team",
    "private workspace",
    "collaborative setup",
    "first option",
    "second option",
    "first one",
    "second one",
    "option one",
    "option two",
)
_ORDER_STATUS_SIGNALS = (
    "order status",
    "track my order",
    "tracking",
    "shipment",
    "where is my order",
    "delivery status",
    "status of my order",
    "حالة الطلب",
    "تتبع",
)
_SOCIAL_GREETING_PHRASES = frozenset(
    {
        "hello",
        "hi",
        "hey",
        "good morning",
        "good afternoon",
        "good evening",
        "مرحبا",
        "اهلا",
        "أهلا",
        "سلام عليكم",
        "السلام عليكم",
        "السلام عليكم ورحمة الله",
        "سلام عليكم ورحمة الله",
        "صباح الخير",
        "مساء الخير",
    }
)
_SOCIAL_GRATITUDE_PHRASES = frozenset(
    {
        "thanks",
        "thank you",
        "thx",
        "شكرا",
        "شكراً",
    }
)
_SOCIAL_GOODBYE_PHRASES = frozenset(
    {
        "bye",
        "goodbye",
        "see you",
        "مع السلامة",
    }
)
_SOCIAL_ASSIST_OPENER_PHRASES = frozenset(
    {
        "help",
        "i need help",
        "need help",
        "can you help",
        "مساعدة",
        "اريد مساعدة",
        "أريد مساعدة",
        "احتاج مساعدة",
        "أحتاج مساعدة",
    }
)
_SOCIAL_FILLER_TOKENS = frozenset(
    {
        "bot",
        "help",
        "me",
        "noor",
        "please",
        "pls",
        "treejar",
    }
)
_SOCIAL_ASSIST_TOKENS = frozenset(
    {
        "advice",
        "assist",
        "assistance",
        "help",
        "مساعدة",
    }
)
_LOW_RISK_FACT_QUESTION_TERMS = (
    "do you",
    "where",
    "what",
    "who",
    "when",
    "which",
    "is there",
    "are there",
    "can you",
    "could you",
    "هل",
    "أين",
    "وين",
    "ما",
    "متى",
    "كيف",
)
_LOCATION_TERMS = (
    "abu dhabi",
    "dubai",
    "dubai marina",
    "sharjah",
    "ajman",
    "uae",
    "ras al khaimah",
    "fujairah",
)
_UAE_WIDE_TERMS = ("uae", "across uae", "across the uae", "within uae")
_EXTERNAL_LOCATION_TERMS = (
    "saudi arabia",
    "saudi",
    "qatar",
    "oman",
    "kuwait",
    "bahrain",
)
_PAYMENT_SPECIFIC_TERMS = (
    "net 30",
    "net30",
    "net 60",
    "net60",
    "deferred payment",
    "payment terms",
    "credit terms",
    "credit term",
    "on credit",
    "postpaid",
    "delayed payment",
)
_DISCOUNT_SPECIFIC_TERMS = (
    "discount",
    "discounts",
    "% off",
    "percent off",
    "special price",
)
_QUOTE_PROPOSAL_PHRASES = (
    "sales order",
    "sale order",
    "commercial offer",
    "commercial proposal",
    "business proposal",
    "formal offer",
    "formal quotation",
    "proforma invoice",
    "pro forma invoice",
    "invoice",
)
_PROPOSAL_CONTEXT_TERMS = (
    "business",
    "commercial",
    "formal",
    "quotation",
    "quote",
    "for me",
)
_QUOTE_HOLD_RE = re.compile(
    r"(?:"
    r"\b(?:keep|maintain|preserve)\s+(?:the\s+)?"
    r"(?:no[\s-]+(?:quote|quotation)|(?:quote|quotation)[\s-]+hold)"
    r"(?:\s+(?:instruction|request))?\b|"
    r"\bno\s+(?:formal\s+)?(?:quote|quotation|commercial\s+offer|proposal)"
    r"\s+(?:yet|now)\b|"
    r"\bnot\s+ready\s+for\s+(?:an?\s+)?(?:quote|quotation|proposal)\b|"
    r"\bwithout\s+(?:creating|preparing|making|issuing|generating|sending)"
    r"\s+(?:an?\s+|any\s+|the\s+)?(?:formal\s+)?"
    r"(?:quote|quotation|commercial\s+offer|commercial\s+proposal|"
    r"proforma\s+invoice|pro\s+forma\s+invoice|invoice)\b|"
    r"\b(?:do\s+not|don't|dont)\s+"
    r"(?:want|need|request|accept|offer|create|prepare|make|issue|generate|send)\s+"
    r"(?:me\s+)?"
    r"(?:an?\s+|any\s+|the\s+)?(?:formal\s+)?"
    r"(?:quote|quotation|commercial\s+offer|commercial\s+proposal|"
    r"proforma\s+invoice|pro\s+forma\s+invoice|invoice)(?:\s+yet)?\b|"
    r"(?:بدون|لا)\s+(?:إنشاء|اعداد|إعداد|ارسال|إرسال)?\s*"
    r"(?:عرض\s+سعر|عرض\s+رسمي)|"
    r"(?:لا|لن)\s+(?:أريد|اريد|أحتاج|احتاج)\s+"
    r"(?:عرض\s+سعر|عرض\s+رسمي|فاتورة\s+مبدئية)"
    r")",
    re.IGNORECASE,
)
_PRICE_OBJECTION_TERMS = (
    "too expensive",
    "price is high",
    "prices are high",
    "price is too high",
    "cost is high",
    "costs too much",
    "cheaper",
    "competitor",
    "better price",
)
_EXTERNAL_PRICE_COMPARISON_TERMS = (
    "competitor",
    "another supplier",
    "other supplier",
    "elsewhere",
    "why should i buy",
)
_INTERNAL_PRICE_OPTIMIZATION_TERMS = (
    "configuration",
    "option",
    "alternative",
    "cross-sell",
    "cross sell",
    "within budget",
    "under aed",
    "below aed",
    "keep the total",
)
_INTERNAL_PRICE_OPTIMIZATION_ACTIONS = (
    "give me",
    "show me",
    "find",
    "recommend",
    "suggest",
)
_RETENTION_TERMS = (
    "don't think we need this anymore",
    "do not think we need this anymore",
    "don't need this anymore",
    "do not need this anymore",
    "no longer need this",
    "not interested anymore",
    "changed my mind",
    "maybe later",
)
_OFF_CATALOG_TERMS = (
    "helicopter",
    "spare parts",
    "gaming laptop",
    "gaming laptops",
    "laptop",
    "laptops",
    "mobile phone",
    "smartphone",
    "computer",
)
_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "delivery": (
        "delivery",
        "deliver",
        "delivered",
        "shipping",
        "ship",
        "lead time",
        "timeline",
        "deadline",
        "timeframe",
        "توصيل",
        "تسليم",
    ),
    "installation": (
        "installation",
        "install",
        "installed",
        "setup",
        "assembly",
        "logistics",
        "تركيب",
    ),
    "warranty": ("warranty", "guarantee", "guaranty", "ضمان"),
    "returns": (
        "return",
        "refund",
        "exchange",
        "cancel",
        "returns",
        "refunds",
        "إرجاع",
        "استرجاع",
    ),
    "payment": (
        "payment",
        "pay",
        "terms",
        "deferred",
        "credit",
        "invoice",
        "installment",
        "net 30",
        "net 60",
        "دفع",
        "السداد",
        "أقساط",
    ),
    # "office" is in almost every message an office-furniture customer sends,
    # and "location" is usually a delivery location. Both used to route a
    # customer to the showroom address: on 2026-08-09 "for a small office, 4
    # people" and "Leila, im the office manager" were both answered with a
    # Google Maps link. The topic now needs a term that is actually about
    # visiting us.
    "showroom": (
        "showroom",
        "branch",
        "store",
        "your office",
        "visit you",
        "come and see",
        "come see",
        "where are you located",
        "your location",
        "معرض",
    ),
    "company": (
        "company",
        "about treejar",
        "who are you",
        "service area",
        "capabilities",
    ),
}
_MANAGER_COMMITMENT_PHRASES = (
    "specific date",
    "specific time",
    "specific slot",
    "exact date",
    "exact time",
    "exact slot",
    "slot",
    "guarantee",
    "guaranteed",
)
_HIGH_RISK_TOPICS = frozenset(
    {"delivery", "installation", "warranty", "returns", "payment"}
)
# Of the high-risk topics, these three are ones where the answer *is* the
# contract: a warranty period, a return window, a payment term. There is no
# separable "do you do this at all". Delivery and installation are different —
# confirming Treejar delivers in the UAE commits nothing about when or at what
# price, so those reach the model when nothing more specific is asked.
_CONTRACT_TERM_TOPICS = frozenset({"warranty", "returns", "payment"})
_NEARBY_EQUIVALENTS = {
    "accessory": {"cabinet", "pedestal", "storage"},
    "accessories": {"cabinet", "pedestal", "storage"},
    "pod": {"booth"},
    "pods": {"booth", "booths"},
    "booth": {"pod", "pods"},
    "booths": {"pod", "pods"},
}


@dataclass(frozen=True)
class VerifiedAnswerDecision:
    question_class: QuestionClass
    faq_support: FaqSupport
    social_intent: SocialIntent | None = None
    policy_action: PolicyAction = "allow"
    matched_topics: tuple[str, ...] = ()
    matched_faq: tuple[dict[str, str], ...] = ()
    confirmed_fact: str | None = None
    asks_for_specific_commitment: bool = False
    requires_manager_handoff: bool = False
    is_order_status: bool = False
    sales_fallback_intent: SalesFallbackIntent | None = None


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _normalize_social_text(text: str) -> str:
    normalized = _normalize(text).casefold()
    normalized = re.sub(r"[^\w\s]+", "", normalized, flags=re.UNICODE)
    return " ".join(normalized.split())


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(_normalize(text))
        if token not in _STOPWORDS and len(token) > 1
    }


def _has_product_signal(normalized: str) -> bool:
    if set(_unicode_tokens(normalized)) & _PRODUCT_SIGNAL_TOKENS:
        return True
    if any(signal in normalized for signal in _PRODUCT_SIGNALS):
        return True
    compact = re.sub(r"[\s-]+", "", normalized)
    return any(signal in compact for signal in _COMPACT_PRODUCT_SIGNALS)


def _has_catalog_discovery_context(normalized: str) -> bool:
    return any(term in normalized for term in _CATALOG_DISCOVERY_CONTEXT_TERMS)


def _has_product_selection_signal(normalized: str) -> bool:
    if _has_product_signal(normalized) and bool(
        _NUMBER_RE.search(normalized)
        or _PRODUCT_SELECTION_QUANTITY_RE.search(normalized)
    ):
        return True
    if _COMPACT_SKU_RE.search(normalized):
        return True
    return bool(
        _NUMBER_RE.search(normalized) and _SKU_SELECTION_SIGNAL_RE.search(normalized)
    )


def _unicode_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token for token in _UNICODE_TOKEN_RE.findall(_normalize_social_text(text))
    )


def _entry_text(item: Mapping[str, str]) -> str:
    title = item.get("title", "")
    content = item.get("content", "")
    return f"{title}\n{content}".strip()


def _extract_answer_text(content: str) -> str:
    if "\nA:" in content:
        return content.split("\nA:", 1)[1].strip()
    if content.startswith("A:"):
        return content.removeprefix("A:").strip()
    return content.strip()


def is_order_status_query(query: str) -> bool:
    normalized = _normalize(query)
    return any(signal in normalized for signal in _ORDER_STATUS_SIGNALS)


def is_social_greeting_query(query: str) -> bool:
    normalized = _normalize_social_text(query)
    return normalized in _SOCIAL_GREETING_PHRASES


def _split_social_greeting_prefix(query: str) -> tuple[str, str] | None:
    normalized = _normalize_social_text(query)
    for phrase in sorted(_SOCIAL_GREETING_PHRASES, key=len, reverse=True):
        if normalized == phrase:
            return phrase, ""
        if normalized.startswith(f"{phrase} "):
            return phrase, normalized[len(phrase) :].strip()
    return None


def _is_social_filler_text(text: str) -> bool:
    if not text:
        return True
    tokens = tuple(token for token in text.split() if token)
    return bool(tokens) and all(token in _SOCIAL_FILLER_TOKENS for token in tokens)


def _is_assist_opener_text(text: str) -> bool:
    normalized = _normalize_social_text(text)
    if not normalized:
        return False
    if normalized in _SOCIAL_ASSIST_OPENER_PHRASES:
        return True
    tokens = tuple(token for token in normalized.split() if token)
    return bool(tokens) and all(
        token in (_SOCIAL_FILLER_TOKENS | _SOCIAL_ASSIST_TOKENS) for token in tokens
    )


def classify_social_intent(query: str) -> tuple[SocialIntent | None, str]:
    normalized = _normalize_social_text(query)
    social_prefix = _split_social_greeting_prefix(query)

    if social_prefix is not None:
        _, tail = social_prefix
        if not tail:
            return "greeting", ""
        if _is_assist_opener_text(tail) or _is_social_filler_text(tail):
            return "assist_opener", ""
        return None, tail

    if normalized in _SOCIAL_GRATITUDE_PHRASES:
        return "gratitude", ""
    if normalized in _SOCIAL_GOODBYE_PHRASES:
        return "goodbye", ""
    if _is_assist_opener_text(normalized):
        return "assist_opener", ""
    return None, query


def _is_benign_no_match(query: str) -> bool:
    normalized = _normalize(query).casefold()
    if not normalized:
        return True
    if _has_product_signal(normalized):
        return False
    if any(signal in normalized for signal in _ORDER_STATUS_SIGNALS):
        return False
    if any(
        keyword in normalized
        for keywords in _TOPIC_KEYWORDS.values()
        for keyword in keywords
    ):
        return False
    if _asks_for_specific_commitment(normalized):
        return False
    if any(term in normalized for term in _LOW_RISK_FACT_QUESTION_TERMS):
        return False
    if _has_catalog_discovery_context(normalized):
        return True
    if "?" in query:
        return False

    tokens = _unicode_tokens(query)
    if 0 < len(tokens) <= 8 and any(
        phrase in normalized for phrase in _BENIGN_PREFERENCE_PHRASES
    ):
        return True
    return 0 < len(tokens) <= 3


def classify_question(query: str) -> QuestionClass:
    social_intent, routed_query = classify_social_intent(query)
    if social_intent is not None:
        return "social"

    normalized = _normalize(routed_query).casefold()
    has_product_signal = _has_product_signal(normalized)
    has_product_selection = _has_product_selection_signal(normalized)
    has_product_discovery = any(
        phrase in normalized for phrase in _PRODUCT_DISCOVERY_PHRASES
    )
    has_catalog_discovery_context = _has_catalog_discovery_context(normalized)
    has_high_risk_service_topic = any(
        keyword in normalized
        for topic in _HIGH_RISK_TOPICS
        for keyword in _TOPIC_KEYWORDS[topic]
    )

    if _has_commercial_terms_risk(normalized):
        return "service_high_risk"

    if has_product_signal and (has_product_discovery or has_product_selection):
        return "product"

    if (
        has_catalog_discovery_context
        and has_product_discovery
        and not has_high_risk_service_topic
    ):
        return "product"

    if is_quote_or_proposal_request(normalized):
        return "service_low_risk"

    if has_product_signal and not has_high_risk_service_topic:
        return "product"

    if has_high_risk_service_topic or _asks_for_specific_commitment(normalized):
        return "service_high_risk"

    if has_product_selection:
        return "product"

    if has_product_signal and has_product_discovery:
        return "product"

    if has_product_signal:
        return "product"

    return "service_low_risk"


def _query_topics(query: str) -> tuple[str, ...]:
    normalized = _normalize(query)
    topics = [
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return tuple(topics)


def _asks_for_specific_commitment(query: str) -> bool:
    normalized = _normalize(query)
    if bool(_DATE_RE.search(normalized)):
        return True
    if any(location in normalized for location in _EXTERNAL_LOCATION_TERMS):
        return True
    if any(location in normalized for location in _LOCATION_TERMS):
        return True
    if _has_commercial_terms_risk(normalized):
        return True
    return any(
        phrase in normalized
        for phrase in ("specific", "exact", "slot", "available", "by ", " on ")
    )


def _has_commercial_terms_risk(query: str) -> bool:
    normalized = _normalize(query).casefold()
    return any(term in normalized for term in _PAYMENT_SPECIFIC_TERMS) or any(
        term in normalized for term in _DISCOUNT_SPECIFIC_TERMS
    )


def requires_manager_commitment(query: str) -> bool:
    """Does answering this need authority the assistant does not have?

    Escalation is for questions the assistant cannot answer without committing
    Treejar to something unpublished. Three things create that need:

    - a ``manager_required`` capability in ``COMMERCIAL_CAPABILITIES``, which is
      discounts and payment or other commercial exceptions;
    - a topic where the answer is itself a contract term: warranty, returns,
      payment;
    - a place outside the declared service area, where nothing is published;
    - a commitment pinned to a date or a named slot, which only a manager can
      confirm.

    Everything else is a capability question — "do you do this at all?" — and
    the model answers it from the knowledge-base block under
    ``build_service_runtime_directives``, which already forbids inventing
    commitments, dates, prices, and terms. Escalating those was the defect:
    two deterministic template routes existed only to paper over it, and each
    new low-risk question invited a third. A location inside the service area
    is deliberately absent from this list; naming Dubai does not turn "do you
    deliver?" into a scheduling promise.
    """

    normalized = _normalize(query).casefold()
    if _has_commercial_terms_risk(normalized):
        return True
    if set(_query_topics(normalized)) & _CONTRACT_TERM_TOPICS:
        return True
    if any(location in normalized for location in _EXTERNAL_LOCATION_TERMS):
        return True
    if _DATE_RE.search(normalized):
        return True
    return any(phrase in normalized for phrase in _MANAGER_COMMITMENT_PHRASES)


def is_quote_or_proposal_request(query: str) -> bool:
    normalized = _normalize(query).casefold()
    if is_quote_or_proposal_hold(normalized):
        return False
    if any(phrase in normalized for phrase in _QUOTE_PROPOSAL_PHRASES):
        return True
    if "quotation" in normalized or "quote" in normalized:
        return True
    return "proposal" in normalized and any(
        term in normalized for term in _PROPOSAL_CONTEXT_TERMS
    )


def is_quote_or_proposal_hold(query: str) -> bool:
    normalized = _normalize(query).casefold()
    return bool(normalized and _QUOTE_HOLD_RE.search(normalized))


def detect_sales_fallback_intent(query: str) -> SalesFallbackIntent | None:
    normalized = _normalize(query).casefold()

    if any(term in normalized for term in _RETENTION_TERMS):
        return "retention"
    if any(term in normalized for term in _PRICE_OBJECTION_TERMS):
        internal_optimization = any(
            term in normalized for term in _INTERNAL_PRICE_OPTIMIZATION_TERMS
        ) and any(term in normalized for term in _INTERNAL_PRICE_OPTIMIZATION_ACTIONS)
        external_comparison = any(
            term in normalized for term in _EXTERNAL_PRICE_COMPARISON_TERMS
        )
        if internal_optimization and not external_comparison:
            return None
        return "price_objection"
    if any(
        term in normalized for term in _OFF_CATALOG_TERMS
    ) and not _has_product_signal(normalized):
        return "off_catalog"
    return None


def _entry_topics(entry_text: str) -> set[str]:
    normalized = _normalize(entry_text)
    return {
        topic
        for topic, keywords in _TOPIC_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    }


def _entry_supports_specificity(query: str, entry_text: str) -> bool:
    normalized_query = _normalize(query)
    normalized_entry = _normalize(entry_text)

    if bool(_DATE_RE.search(normalized_query)) and not (
        _DATE_RE.search(normalized_entry) or _NUMBER_RE.search(normalized_entry)
    ):
        return False

    requested_external_locations = {
        location
        for location in _EXTERNAL_LOCATION_TERMS
        if location in normalized_query
    }
    if requested_external_locations and not (
        requested_external_locations
        & {
            location
            for location in requested_external_locations
            if location in normalized_entry
        }
    ):
        return False

    requested_locations = {
        location for location in _LOCATION_TERMS if location in normalized_query
    }
    if (
        requested_locations
        and not (
            requested_locations
            & {location for location in _LOCATION_TERMS if location in normalized_entry}
        )
        and not any(term in normalized_entry for term in _UAE_WIDE_TERMS)
    ):
        return False

    requested_payment_terms = {
        term for term in _PAYMENT_SPECIFIC_TERMS if term in normalized_query
    }
    if requested_payment_terms and not any(
        term in normalized_entry for term in requested_payment_terms
    ):
        return False

    return not (
        bool(_NUMBER_RE.search(normalized_query))
        and not bool(_NUMBER_RE.search(normalized_entry))
    )


def _matching_faq_entries(
    query: str,
    question_class: QuestionClass,
    faq_context: Sequence[Mapping[str, str]],
) -> tuple[tuple[str, ...], tuple[dict[str, str], ...]]:
    topics = _query_topics(query)
    query_tokens = _tokenize(query)
    matches: list[tuple[int, int, dict[str, str]]] = []

    for raw_item in faq_context:
        item = {
            "title": raw_item.get("title", ""),
            "content": raw_item.get("content", ""),
        }
        entry_text = _entry_text(item)
        entry_topics = _entry_topics(entry_text)

        if topics:
            overlap_topics = tuple(topic for topic in topics if topic in entry_topics)
            if not overlap_topics:
                continue
            score = len(overlap_topics) * 10
        else:
            overlap_tokens = query_tokens & _tokenize(entry_text)
            if not overlap_tokens:
                continue
            score = len(overlap_tokens)

        if question_class == "service_low_risk":
            score += len(query_tokens & _tokenize(entry_text))

        matches.append((score, len(entry_text), item))

    matches.sort(key=lambda item: (-item[0], -item[1]))
    matched_items = tuple(item for _, _, item in matches)
    return topics, matched_items


def evaluate_verified_answer_policy(
    query: str,
    faq_context: Sequence[Mapping[str, str]],
) -> VerifiedAnswerDecision:
    if is_order_status_query(query):
        return VerifiedAnswerDecision(
            question_class="service_low_risk",
            faq_support="missing",
            policy_action="allow",
            is_order_status=True,
        )

    social_intent, routed_query = classify_social_intent(query)
    question_class = classify_question(query)
    sales_fallback_intent = detect_sales_fallback_intent(routed_query)
    if question_class != "service_high_risk" and sales_fallback_intent is not None:
        return VerifiedAnswerDecision(
            question_class=question_class,
            faq_support="missing",
            social_intent=social_intent,
            policy_action="allow",
            sales_fallback_intent=sales_fallback_intent,
        )
    if question_class == "social":
        policy_action: PolicyAction = (
            "clarify" if social_intent == "assist_opener" else "allow"
        )
        return VerifiedAnswerDecision(
            question_class="social",
            faq_support="verified",
            social_intent=social_intent,
            policy_action=policy_action,
        )
    if question_class == "product":
        return VerifiedAnswerDecision(
            question_class="product",
            faq_support="missing",
            policy_action="allow",
        )

    matched_topics, matched_faq = _matching_faq_entries(
        routed_query, question_class, faq_context
    )
    if not matched_faq:
        if question_class == "service_low_risk" and is_quote_or_proposal_request(
            routed_query
        ):
            policy_action = "allow"
        elif question_class == "service_low_risk" and _is_benign_no_match(routed_query):
            policy_action = "clarify"
        elif requires_manager_commitment(routed_query):
            policy_action = "handoff"
        else:
            policy_action = "allow"
        return VerifiedAnswerDecision(
            question_class=question_class,
            faq_support="missing",
            matched_topics=matched_topics,
            policy_action=policy_action,
            requires_manager_handoff=policy_action == "handoff",
        )

    asks_for_specific_commitment = _asks_for_specific_commitment(routed_query)
    faq_support: FaqSupport = "verified"
    if asks_for_specific_commitment and not any(
        _entry_supports_specificity(routed_query, _entry_text(item))
        for item in matched_faq
    ):
        faq_support = "partial"

    confirmed_fact = _extract_answer_text(matched_faq[0]["content"])
    final_policy_action: PolicyAction = "allow"
    if faq_support == "missing" or (
        question_class == "service_high_risk"
        and faq_support == "partial"
        and requires_manager_commitment(routed_query)
    ):
        final_policy_action = "handoff"

    return VerifiedAnswerDecision(
        question_class=question_class,
        faq_support=faq_support,
        policy_action=final_policy_action,
        matched_topics=matched_topics,
        matched_faq=matched_faq,
        confirmed_fact=confirmed_fact or None,
        asks_for_specific_commitment=asks_for_specific_commitment,
        requires_manager_handoff=final_policy_action == "handoff",
    )


def build_service_runtime_directives(
    decision: VerifiedAnswerDecision,
) -> tuple[str, ...]:
    support_phrase = f"{decision.faq_support} FAQ support"
    directives = [
        f"service policy branch active with {support_phrase}",
        "answer only from the FAQ facts already provided in the knowledge base block",
        "do not invent any commitments, dates, prices, warranty terms, return terms, or payment terms",
        "if a detail is not explicitly confirmed in the FAQ, say only the confirmed general part",
    ]
    if decision.question_class == "service_high_risk":
        directives.append(
            "this is a high-risk service question, so do not add new promises beyond the confirmed FAQ fact"
        )
    if decision.faq_support == "partial":
        directives.append(
            "the FAQ only confirms a general part of the answer; do not imply that specific slots, dates, or conditions are confirmed"
        )
    return tuple(directives)


def build_service_handoff_reason(query: str, decision: VerifiedAnswerDecision) -> str:
    if decision.faq_support == "partial" and decision.confirmed_fact:
        return (
            "Verified-answer policy requires manager confirmation: FAQ only confirms "
            f"the general fact '{decision.confirmed_fact}' for question '{query}'."
        )
    return (
        "Verified-answer policy requires manager confirmation because no verified FAQ "
        f"support was found for '{query}'."
    )


def build_service_handoff_response(
    decision: VerifiedAnswerDecision, language: str
) -> str:
    is_arabic = is_arabic_customer_language(language)

    if decision.confirmed_fact:
        if is_arabic:
            return (
                f"{decision.confirmed_fact} "
                "وبخصوص التفاصيل المحددة، سيتواصل معك مديرنا لتأكيدها بدقة."
            )
        return (
            f"{decision.confirmed_fact} "
            "For the specific details, our manager will confirm that for you."
        )

    if is_arabic:
        return "أريد أن أكون دقيقًا، لذلك سيتواصل معك مديرنا لتأكيد هذه المعلومة."
    return "I want to be accurate, so our manager will confirm this for you."


def build_sales_fallback_response(intent: SalesFallbackIntent, language: str) -> str:
    is_arabic = is_arabic_customer_language(language)

    if intent == "price_objection":
        if is_arabic:
            return (
                "أتفهم أن السعر مهم. للمقارنة بشكل عادل، أرسل لي موديل المنافس "
                "والمواصفات والسعر، وسأساعدك في مقارنته بخيارات Treejar المتاحة "
                "بدون تأكيد أي خصم غير معتمد."
            )
        return (
            "I understand price matters. To compare fairly, please share the "
            "competitor's model, specs, and price. I can then compare it with "
            "Treejar's available office furniture options without promising "
            "unapproved pricing."
        )

    if intent == "retention":
        if is_arabic:
            return (
                "لا مشكلة، وشكرًا لإخباري. إذا عاد مشروع تجهيز المكتب لاحقًا، "
                "أرسل لي الكمية والميزانية والموعد المطلوب وسأكمل معك من هناك."
            )
        return (
            "No problem, thanks for letting me know. If the office setup comes "
            "back later, send me the quantity, budget, and timeline, and I can "
            "pick it up from there."
        )

    if is_arabic:
        return (
            "لا، نحن نركز على أثاث المكاتب ومنتجات بيئة العمل، وليس على "
            "قطع غيار الطائرات أو أجهزة اللابتوب المخصصة للألعاب. يمكنني مساعدتك "
            "في المكاتب والكراسي المريحة والتخزين وأثاث غرف الاجتماعات."
        )
    return (
        "No, we focus on office furniture and workplace products, not "
        "helicopter spare parts or gaming laptops. I can help with desks, "
        "ergonomic chairs, storage, or meeting-room furniture."
    )


def build_clarification_response(language: str) -> str:
    if is_arabic_customer_language(language):
        return "يمكنني المساعدة في المنتجات والأسعار والتوفر والتوصيل أو عروض الأسعار. ماذا تحتاج؟"
    return "I can help with products, prices, stock, delivery, or quotations. What do you need?"


def build_quote_or_proposal_clarification_response(language: str) -> str:
    if is_arabic_customer_language(language):
        return "يمكنني تجهيز عرض سعر أو فاتورة أولية. يرجى تأكيد المنتجات والكمية لكل منتج تريد إدراجه."
    return (
        "I can prepare a quotation or proforma invoice. Please confirm the item(s) "
        "and quantity for each item you want included."
    )


_CAPACITY_WORD_VALUES = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "twelve": 12,
}
_CAPACITY_RE = re.compile(
    r"\b(?P<count>\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|twelve)"
    r"(?:[\s-]+)(?:person|people|staff|employees?|users?|seats?)\b",
    re.IGNORECASE,
)
_WORKSTATION_MATCH_TERMS = frozenset(
    {"desk", "desks", "workstation", "workstations", "bench", "benches"}
)
_PRIVACY_MATCH_TERMS = frozenset(
    {
        "private",
        "privacy",
        "panel",
        "panels",
        "divider",
        "dividers",
        "screen",
        "screens",
        "enclosed",
    }
)
_STRUCTURED_ATTRIBUTE_VALUE_RE = re.compile(
    r"\b(?:brand|family|line|model|series|finish|colou?r)\s*[:=-]?\s*"
    r"(?P<after>[a-z][a-z0-9-]{1,30})\b|"
    r"\b(?P<before>[a-z][a-z0-9-]{1,30})\s+(?:finish|colou?r)\b|"
    r"\bin\s+(?P<modifier>[a-z][a-z0-9-]{1,30})\b",
    re.IGNORECASE,
)
_STRUCTURED_MODEL_IDENTIFIER_RE = re.compile(
    r"(?<![a-z0-9])(?=[a-z0-9-]*[a-z])(?=[a-z0-9-]*\d)"
    r"[a-z0-9]+(?:-[a-z0-9]+)+(?![a-z0-9])",
    re.IGNORECASE,
)
_STRUCTURED_UPPER_IDENTIFIER_RE = re.compile(
    r"(?<![a-z0-9])[A-Z][A-Z0-9]{2,}(?![a-z0-9-])"
)
_STRUCTURED_DISCRIMINATOR_EXCLUSIONS = frozenset(
    {"aed", "dhs", "sku", "stock", "privacy", "private", "panel", "panels"}
)


def _capacity_value(text: str) -> int | None:
    match = _CAPACITY_RE.search(_normalize(text))
    if match is None:
        return None
    raw_count = match.group("count").casefold()
    return int(raw_count) if raw_count.isdigit() else _CAPACITY_WORD_VALUES[raw_count]


def _explicit_structured_discriminators(query: str) -> set[str]:
    raw_values = {
        value.casefold()
        for match in _STRUCTURED_ATTRIBUTE_VALUE_RE.finditer(query)
        if (value := next((group for group in match.groups() if group), None))
    }
    values = {token for raw_value in raw_values for token in _tokenize(raw_value)}
    return values - _STRUCTURED_DISCRIMINATOR_EXCLUSIONS


def _explicit_structured_identifiers(text: str) -> set[str]:
    identifiers = {
        match.group(0).casefold()
        for match in _STRUCTURED_MODEL_IDENTIFIER_RE.finditer(text)
    }
    identifiers.update(
        match.group(0).casefold()
        for match in _STRUCTURED_UPPER_IDENTIFIER_RE.finditer(text)
    )
    return identifiers - _STRUCTURED_DISCRIMINATOR_EXCLUSIONS


def _matches_structured_workstation_constraints(
    query: str,
    candidate: str,
) -> bool:
    query_tokens = _tokenize(query)
    if not (
        query_tokens & _WORKSTATION_MATCH_TERMS and query_tokens & _PRIVACY_MATCH_TERMS
    ):
        return False
    requested_capacity = _capacity_value(query)
    if requested_capacity is None:
        return False

    candidate_tokens = _tokenize(candidate)
    discriminators = _explicit_structured_discriminators(query)
    identifiers = _explicit_structured_identifiers(query)
    return bool(
        candidate_tokens & _WORKSTATION_MATCH_TERMS
        and candidate_tokens & _PRIVACY_MATCH_TERMS
        and _capacity_value(candidate) == requested_capacity
        and discriminators.issubset(candidate_tokens)
        and identifiers.issubset(_explicit_structured_identifiers(candidate))
    )


def classify_product_match(query: str, candidates: Sequence[str]) -> ProductMatch:
    if not candidates:
        return "missing"

    if any(
        _matches_structured_workstation_constraints(query, candidate)
        for candidate in candidates
    ):
        return "exact"

    normalized_query = _normalize(query)
    candidate_tokens = [_tokenize(candidate) for candidate in candidates]
    query_tokens = {
        token
        for token in _tokenize(normalized_query)
        if token not in {"tell", "about", "your", "show", "what", "have"}
    }

    exact_terms = {
        token
        for token in query_tokens
        if token not in {"product", "products", "office", "treejar"}
    }

    def _term_variants(term: str) -> set[str]:
        variants = {term}
        if term.endswith("s") and len(term) > 3:
            variants.add(term[:-1])
        else:
            variants.add(f"{term}s")
        return variants

    if exact_terms and any(
        all(
            any(variant in candidate for variant in _term_variants(term))
            for term in exact_terms
        )
        for candidate in candidate_tokens
    ):
        return "exact"

    overlap_terms = set(exact_terms)
    for term in exact_terms:
        overlap_terms.update(_term_variants(term))
        overlap_terms.update(_NEARBY_EQUIVALENTS.get(term, set()))

    if any(candidate & overlap_terms for candidate in candidate_tokens):
        return "nearby"

    return "missing"
