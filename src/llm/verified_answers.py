from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

QuestionClass = Literal["product", "service_low_risk", "service_high_risk"]
FaqSupport = Literal["verified", "partial", "missing"]
ProductMatch = Literal["exact", "nearby", "missing"]

_TOKEN_RE = re.compile(r"[a-z0-9']+")
_DATE_RE = re.compile(
    r"\b(?:today|tomorrow|tonight|next|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{1,2}[/-]\d{1,2})\b",
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
    "workstation",
    "workstations",
    "table",
    "tables",
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
    "مكتب",
    "طاولة",
)
_PRODUCT_DISCOVERY_PHRASES = (
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
    "showroom": ("showroom", "location", "office", "branch", "store"),
    "company": (
        "company",
        "about treejar",
        "who are you",
        "service area",
        "capabilities",
    ),
}
_HIGH_RISK_TOPICS = frozenset(
    {"delivery", "installation", "warranty", "returns", "payment"}
)
_NEARBY_EQUIVALENTS = {
    "pod": {"booth"},
    "pods": {"booth", "booths"},
    "booth": {"pod", "pods"},
    "booths": {"pod", "pods"},
}


@dataclass(frozen=True)
class VerifiedAnswerDecision:
    question_class: QuestionClass
    faq_support: FaqSupport
    matched_topics: tuple[str, ...] = ()
    matched_faq: tuple[dict[str, str], ...] = ()
    confirmed_fact: str | None = None
    asks_for_specific_commitment: bool = False
    requires_manager_handoff: bool = False
    is_order_status: bool = False


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _tokenize(text: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(_normalize(text))
        if token not in _STOPWORDS and len(token) > 1
    }


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


def classify_question(query: str) -> QuestionClass:
    normalized = _normalize(query)
    has_product_signal = any(signal in normalized for signal in _PRODUCT_SIGNALS)
    has_product_discovery = any(
        phrase in normalized for phrase in _PRODUCT_DISCOVERY_PHRASES
    )

    if has_product_signal and has_product_discovery:
        return "product"

    if any(
        keyword in normalized
        for topic in _HIGH_RISK_TOPICS
        for keyword in _TOPIC_KEYWORDS[topic]
    ) or _asks_for_specific_commitment(normalized):
        return "service_high_risk"

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
    if any(location in normalized for location in _LOCATION_TERMS):
        return True
    return any(
        phrase in normalized
        for phrase in ("specific", "exact", "slot", "available", "by ", " on ")
    )


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

    requested_locations = {
        location for location in _LOCATION_TERMS if location in normalized_query
    }
    if (
        requested_locations
        and not (
            requested_locations
            & {location for location in _LOCATION_TERMS if location in normalized_entry}
        )
        and "across uae" not in normalized_entry
        and "across the uae" not in normalized_entry
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
            is_order_status=True,
        )

    question_class = classify_question(query)
    if question_class == "product":
        return VerifiedAnswerDecision(question_class="product", faq_support="missing")

    matched_topics, matched_faq = _matching_faq_entries(
        query, question_class, faq_context
    )
    if not matched_faq:
        return VerifiedAnswerDecision(
            question_class=question_class,
            faq_support="missing",
            matched_topics=matched_topics,
            requires_manager_handoff=True,
        )

    asks_for_specific_commitment = _asks_for_specific_commitment(query)
    faq_support: FaqSupport = "verified"
    if asks_for_specific_commitment and not any(
        _entry_supports_specificity(query, _entry_text(item)) for item in matched_faq
    ):
        faq_support = "partial"

    confirmed_fact = _extract_answer_text(matched_faq[0]["content"])
    requires_manager_handoff = faq_support == "missing" or (
        question_class == "service_high_risk" and faq_support == "partial"
    )
    if question_class == "service_low_risk" and faq_support == "missing":
        requires_manager_handoff = True

    return VerifiedAnswerDecision(
        question_class=question_class,
        faq_support=faq_support,
        matched_topics=matched_topics,
        matched_faq=matched_faq,
        confirmed_fact=confirmed_fact or None,
        asks_for_specific_commitment=asks_for_specific_commitment,
        requires_manager_handoff=requires_manager_handoff,
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
    lang = language.lower()
    is_arabic = lang == "ar"

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


def classify_product_match(query: str, candidates: Sequence[str]) -> ProductMatch:
    if not candidates:
        return "missing"

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
