"""Owner-approved company facts that must reach the model without the RAG index.

The live knowledge base held no FAQ rows on 2026-09-23 (``index_documents`` is
never called), so a customer asking "Do you provide delivery and assembly in
Dubai?" got "I can't confirm Dubai delivery or assembly". The owner ruled the
same day that Noor answers these questions as ``docs/faq.md`` does, and on
2026-11-04 Julia provided the approved UAE/cross-border delivery, full-truck,
and assembly tariff policy (`tj-z3hw`). Only the entries listed here are
approved as standing facts; manager-controlled terms (warranty, payment, price
matching) stay out.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path

from src.dialogue.count_words import COUNT_PATTERN, count_value
from src.dialogue.order_state import (
    QuoteConsent,
    QuoteLifecycle,
    quote_workflow_from_metadata,
)
from src.llm.money import (
    amount_with_uae_vat,
    canonical_amount,
    find_customer_output_amounts,
    round_money,
)
from src.llm.verified_answers import _entry_topics, _query_topics

logger = logging.getLogger(__name__)

_FAQ_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "faq.md"

# FAQ question number -> approval that makes it a standing fact.
APPROVED_FAQ_QUESTIONS: dict[int, str] = {
    8: (
        "owner/client decision 2026-11-09 "
        "(Julia showroom address, hours, map & Jebel Ali self-pickup policy)"
    ),
    9: (
        "owner/client decision 2026-11-04 (Julia delivery & assembly tariff sheet) "
        "+ 2026-11-09 (Jebel Ali self-pickup)"
    ),
    10: "owner/client decision 2026-11-04 (Julia delivery & assembly tariff sheet)",
}

FAQ_SOURCE = "faq_static"

_DELIVERY_CHARGE_FIGURES: frozenset[float] = frozenset(
    {
        50.0,
        100.0,
        130.0,
        200.0,
        250.0,
        300.0,
        400.0,
        600.0,
        800.0,
        900.0,
        1200.0,
        1500.0,
        2000.0,
    }
)
_ASSEMBLY_UNIT_FEE = 30.0
_COUNT_TOKEN_RE = re.compile(rf"(?<![\w-])(?:{COUNT_PATTERN})(?![\w-])", re.IGNORECASE)
_DELIVERY_FOLLOWUP_QUALIFIER_RE = re.compile(
    r"\b(?:"
    r"dubai|sharjah|abu\s+dhabi|ajman|fujairah|ras\s+al\s+khaimah|"
    r"umm\s+al\s+quwain|al\s+ain|emirates?|uae|saudi(?:\s+arabia)?|oman|qatar|"
    r"truck|tonnes?|tons?|weight|free|express|display|projects?|made-to-order|"
    r"checkout|fees?|charges?|costs?|tariffs?|rates?"
    r")\b"
    r"|(?:دبي|الشارقة|أبوظبي|ابوظبي|عجمان|الفجيرة|رأس\s+الخيمة|ام\s+القيوين|"
    r"الإمارات|الامارات|السعودية|عمان|قطر|شاحنة|طن|وزن|مجاني|مجانا|سريع|"
    r"تكلفة|رسوم|تعرفة)",
    re.IGNORECASE,
)
_DELIVERY_DETAIL_CONTINUATION_RE = re.compile(
    r"(?:"
    r"\[(?:EMAIL|PHONE)_\d+\]"
    r"|[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}"
    r"|\b(?:trn|vat|po\s*box|quotation|quote|company|llc|fzc|fze|inc|ltd|"
    r"my\s+name\s+is|address|street|building|tower|floor|office|warehouse|"
    r"plot|area|district|yes|please\s+send|go\s+ahead|confirm)\b"
    r"|(?:عرض\s+سعر|نعم|أرسل|ارسل|شركة|اسمي|عنوان|شارع|مبنى|مكتب|مستودع)"
    r")",
    re.IGNORECASE,
)


_SHOWROOM_FOLLOWUP_QUALIFIER_RE = re.compile(
    r"\b(?:"
    r"hours?|open|closed?|sunday|saturday|monday|tuesday|wednesday|thursday|"
    r"friday|maps?|pin|directions?|address|pickup|collect|free"
    r")\b"
    r"|(?:ساعات|مفتوح|مغلق|الأحد|الاحد|السبت|الجمعة|خريطة|لوكيشن|عنوان|استلام|مجاني)",
    re.IGNORECASE,
)


def has_quote_delivery_context(
    conversation_metadata: Mapping[str, object] | None,
    *,
    quotation_active: bool = False,
) -> bool:
    """Whether the turn is inside an active quotation collection/issuance flow."""

    if quotation_active:
        return True
    if not isinstance(conversation_metadata, Mapping):
        return False
    workflow = quote_workflow_from_metadata(dict(conversation_metadata))
    if workflow.lifecycle in {
        QuoteLifecycle.QUOTE_REQUESTED,
        QuoteLifecycle.COLLECTING_DETAILS,
        QuoteLifecycle.CREATING,
    }:
        return True
    return (
        workflow.consent is QuoteConsent.GRANTED
        and workflow.lifecycle is not QuoteLifecycle.CREATED
    )


def _parse_approved_entries(text: str) -> tuple[dict[str, str], ...]:
    entries: list[dict[str, str]] = []
    for part in text.split("\n## ")[1:]:
        heading, _, body = part.partition("\n")
        number, dot, title = heading.strip().partition(". ")
        if not dot or not number.isdigit() or not body.strip():
            continue
        if int(number) not in APPROVED_FAQ_QUESTIONS:
            continue
        title = title.strip()
        entries.append(
            {
                "source": FAQ_SOURCE,
                "category": "faq",
                "title": title,
                "content": f"Q: {title}\nA: {body.strip()}",
            }
        )
    return tuple(entries)


@lru_cache(maxsize=1)
def approved_faq_entries() -> tuple[dict[str, str], ...]:
    try:
        text = _FAQ_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Approved FAQ source is missing: %s", _FAQ_PATH)
        return ()
    entries = _parse_approved_entries(text)
    if len(entries) != len(APPROVED_FAQ_QUESTIONS):
        logger.warning(
            "Approved FAQ source yielded %d of %d entries: %s",
            len(entries),
            len(APPROVED_FAQ_QUESTIONS),
            _FAQ_PATH,
        )
    return entries


def active_faq_topics(
    query: str,
    recent_history: Sequence[str] | None = None,
    *,
    quote_delivery_active: bool = False,
) -> set[str]:
    """Topics raised directly by ``query`` or continued across a quote/delivery flow."""

    topics = set(_query_topics(query))
    if topics:
        return topics
    is_delivery_continuation = bool(
        _DELIVERY_FOLLOWUP_QUALIFIER_RE.search(query)
        or _DELIVERY_DETAIL_CONTINUATION_RE.search(query)
    )
    is_showroom_continuation = bool(_SHOWROOM_FOLLOWUP_QUALIFIER_RE.search(query))
    if not is_delivery_continuation and not is_showroom_continuation:
        return set()
    history_topics = (
        set(_query_topics(" ".join(recent_history))) if recent_history else set()
    )
    continued: set[str] = set()
    if is_delivery_continuation:
        continued |= history_topics & {"delivery", "installation"}
        if not continued and quote_delivery_active:
            continued.add("delivery")
    if is_showroom_continuation:
        continued |= history_topics & {"showroom"}
    return continued


def with_approved_faq(
    query: str,
    faq_context: Sequence[Mapping[str, str]],
    *,
    recent_history: Sequence[str] | None = None,
    quote_delivery_active: bool = False,
) -> list[dict[str, str]]:
    """Add approved FAQ entries whose topic the customer's message raises."""

    merged = [dict(item) for item in faq_context]
    topics = active_faq_topics(
        query,
        recent_history,
        quote_delivery_active=quote_delivery_active,
    )
    if not topics:
        return merged
    seen_titles = {str(item.get("title", "")).casefold() for item in merged}
    for entry in approved_faq_entries():
        if entry["title"].casefold() in seen_titles:
            continue
        if topics & _entry_topics(f"{entry['title']} {entry['content']}"):
            merged.append(dict(entry))
    return merged


def _positive_amount(value: object) -> float | None:
    canonical = canonical_amount(value)
    if canonical is None:
        return None
    try:
        parsed = float(canonical)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def grounded_faq_amounts(
    query: str,
    faq_context: Sequence[Mapping[str, str]] | None,
    *,
    recent_history: Sequence[str] | None = None,
    customer_amounts: Sequence[object] = (),
    quote_delivery_active: bool = False,
) -> tuple[float, ...]:
    """Approved AED figures (and bounded fee arithmetic) for a topic-matched FAQ turn."""

    if not faq_context:
        return ()
    topics = active_faq_topics(
        query,
        recent_history,
        quote_delivery_active=quote_delivery_active,
    )
    if not topics:
        return ()

    base_amounts: set[float] = set()
    for item in faq_context:
        item_text = f"{item.get('title', '')} {item.get('content', '')}"
        if not (topics & _entry_topics(item_text)):
            continue
        for token in find_customer_output_amounts(item_text):
            parsed = _positive_amount(token)
            if parsed is not None:
                base_amounts.add(parsed)

    if not base_amounts:
        return ()

    quantities = {
        qty
        for match in _COUNT_TOKEN_RE.finditer(str(query or ""))
        if (qty := count_value(match.group(0))) is not None and 1 <= qty <= 500
    }
    assembly_totals: set[float] = set()
    if _ASSEMBLY_UNIT_FEE in base_amounts:
        assembly_totals.add(_ASSEMBLY_UNIT_FEE)
        assembly_totals.update(
            round_money(qty * _ASSEMBLY_UNIT_FEE) for qty in quantities
        )

    delivery_charges = base_amounts & _DELIVERY_CHARGE_FIGURES
    cust_values = {
        parsed
        for raw in customer_amounts
        if (parsed := _positive_amount(raw)) is not None and parsed <= 1_000_000
    }

    combined = set(base_amounts) | assembly_totals
    for d_fee in delivery_charges:
        for a_fee in assembly_totals:
            combined.add(round_money(d_fee + a_fee))
        for c_val in cust_values:
            combined.add(round_money(c_val + d_fee))
            for a_fee in assembly_totals:
                combined.add(round_money(c_val + d_fee + a_fee))
    for c_val in cust_values:
        for a_fee in assembly_totals:
            combined.add(round_money(c_val + a_fee))

    with_vat: set[float] = set()
    for value in combined:
        excl, vat, incl = amount_with_uae_vat(value)
        with_vat.update((excl, vat, incl))

    return tuple(sorted(with_vat))
