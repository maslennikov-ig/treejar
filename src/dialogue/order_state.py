from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.dialogue.catalog_refs import extract_catalog_references

OrderLineStatus = Literal["unresolved", "resolved", "needs_quantity"]
OrderDecisionRoute = Literal[
    "legacy_fallback",
    "product_selection",
    "quote_details",
    "quantity_clarification",
]


class QuoteDetails(BaseModel):
    name: str | None = None
    company: str | None = None
    customer_type: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None


class OrderLine(BaseModel):
    catalog_ref: str
    quantity: int | None = None
    source_text: str
    sku: str | None = None
    resolved_sku: str | None = None
    status: OrderLineStatus = "unresolved"
    confidence: Literal["high", "medium", "low"] = "high"


class OrderIntent(BaseModel):
    lines: list[OrderLine] = Field(default_factory=list)
    quote_details: QuoteDetails = Field(default_factory=QuoteDetails)
    source_text: str = ""

    @property
    def has_complete_lines(self) -> bool:
        return bool(self.lines) and all(
            line.quantity and line.quantity > 0 for line in self.lines
        )


class OrderState(BaseModel):
    version: int = 1
    lines: list[OrderLine] = Field(default_factory=list)
    quote_details: QuoteDetails = Field(default_factory=QuoteDetails)
    quote_status: str | None = None
    missing_quote_fields: list[str] = Field(default_factory=list)

    @classmethod
    def from_legacy_metadata(cls, metadata: Mapping[str, Any] | None) -> OrderState:
        if not isinstance(metadata, Mapping):
            return cls()

        lines: list[OrderLine] = []
        selection = metadata.get("pending_quote_selection")
        if isinstance(selection, Mapping):
            raw_items = selection.get("items")
            if isinstance(raw_items, list):
                for item in raw_items:
                    line = _line_from_legacy_item(item)
                    if line is not None:
                        lines.append(line)

        quote_details = QuoteDetails()
        raw_details = metadata.get("quote_customer_details")
        if isinstance(raw_details, Mapping):
            quote_details = QuoteDetails(
                name=_mapping_text(raw_details, "name"),
                company=_mapping_text(raw_details, "company"),
                customer_type=_mapping_text(raw_details, "customer_type"),
                email=_mapping_text(raw_details, "email"),
                phone=_mapping_text(raw_details, "phone"),
                address=_mapping_text(raw_details, "address"),
            )

        return cls(lines=lines, quote_details=quote_details)


class OrderDecision(BaseModel):
    route: OrderDecisionRoute = "legacy_fallback"
    handled: bool = False
    side_effects_allowed: bool = False
    reason_codes: list[str] = Field(default_factory=list)


class OrderRuntimeTrace(BaseModel):
    route: str = "legacy_fallback"
    handled: bool = False
    reason_codes: list[str] = Field(default_factory=list)
    source: str = "catalog_refs"
    line_count: int = 0
    total_ms: float = 0.0
    phase_ms: dict[str, float] = Field(default_factory=dict)


_QUANTITY_WORD_PATTERN = "ONE|TWO|THREE|FOUR|FIVE|SIX|SEVEN|EIGHT|NINE|TEN"
_NEXT_ORDER_LINE_RE = re.compile(
    rf"\s+(?:and|or)\s+(?=(?:\d{{1,3}}|{_QUANTITY_WORD_PATTERN})\b)",
    flags=re.IGNORECASE,
)
_TRAILING_QUANTITY_AFTER_REF_RE = re.compile(
    rf"\s+(?=(?:\d{{1,3}}|{_QUANTITY_WORD_PATTERN})"
    r"\s+(?:x|pcs?|pieces?|units?|positions?)\b)",
    flags=re.IGNORECASE,
)
_PRODUCT_SEGMENT_STOP_RE = re.compile(
    r"[.;!?\n]|\bwith\s+(?:delivery|assembly)\b|"
    r"\b(?:delivery|assembly|please|confirm|quote|quotation|prepare)\b",
    flags=re.IGNORECASE,
)


def extract_order_intent_from_text(text: str) -> OrderIntent:
    refs = extract_catalog_references(text)
    lines = [
        OrderLine(
            catalog_ref=ref.normalized,
            quantity=ref.quantity,
            source_text=_source_text_for_catalog_ref(text, ref),
            sku=ref.normalized,
            status="unresolved" if ref.quantity is not None else "needs_quantity",
        )
        for ref in refs
    ]
    return OrderIntent(lines=lines, source_text=text)


def order_lines_snapshot(intent: OrderIntent) -> list[dict[str, object]]:
    snapshot: list[dict[str, object]] = []
    for line in intent.lines:
        if not line.quantity or line.quantity <= 0:
            continue
        snapshot.append(
            {
                "catalog_ref": line.catalog_ref,
                "quantity": line.quantity,
                "source_text": line.source_text,
            }
        )
    return snapshot


def _source_text_for_catalog_ref(text: str, ref: Any) -> str:
    raw = str(getattr(ref, "raw", "") or "").strip()
    start = getattr(ref, "start", None)
    end = getattr(ref, "end", None)
    if not isinstance(start, int) or not isinstance(end, int):
        return raw
    if start < 0 or end <= start or end > len(text):
        return raw

    left = _source_text_left_bound(text, start, getattr(ref, "quantity", None))
    right = _source_text_right_bound(text, end)
    candidate = " ".join(text[left:right].strip(" \t\r\n,;:-").split())
    return candidate or raw


def _source_text_left_bound(
    text: str,
    ref_start: int,
    quantity: int | None,
) -> int:
    if quantity is None:
        return ref_start

    prefix_start = max(0, ref_start - 64)
    prefix = text[prefix_start:ref_start]
    quantity_re = re.compile(
        rf"(?:^|[^\w])(?:{quantity}|{_QUANTITY_WORD_PATTERN})"
        r"(?:\s+(?:x|pcs?|pieces?|units?|positions?))?\s*$",
        flags=re.IGNORECASE,
    )
    match = quantity_re.search(prefix)
    if match is None:
        return ref_start

    return prefix_start + match.end()


def _source_text_right_bound(text: str, ref_end: int) -> int:
    window = text[ref_end : ref_end + 96]
    candidates: list[int] = []
    for pattern in (
        _NEXT_ORDER_LINE_RE,
        _TRAILING_QUANTITY_AFTER_REF_RE,
        _PRODUCT_SEGMENT_STOP_RE,
    ):
        match = pattern.search(window)
        if match is not None:
            candidates.append(ref_end + match.start())
    if not candidates:
        return min(len(text), ref_end + len(window))
    return min(candidates)


def _line_from_legacy_item(item: Any) -> OrderLine | None:
    if not isinstance(item, Mapping):
        return None
    raw_quantity = item.get("quantity")
    if isinstance(raw_quantity, int):
        quantity = raw_quantity
    elif isinstance(raw_quantity, str):
        try:
            quantity = int(raw_quantity)
        except ValueError:
            return None
    else:
        return None
    if quantity <= 0:
        return None

    item_candidate = _mapping_text(item, "item_candidate")
    sku = _mapping_text(item, "sku")
    if not item_candidate and not sku:
        return None
    catalog_ref = sku or item_candidate
    if not catalog_ref:
        return None
    return OrderLine(
        catalog_ref=catalog_ref,
        quantity=quantity,
        source_text=item_candidate or catalog_ref,
        sku=sku or catalog_ref,
    )


def _mapping_text(value: Mapping[str, Any], key: str) -> str | None:
    raw = value.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
