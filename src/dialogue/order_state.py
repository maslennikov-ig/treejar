from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal, TypeGuard

from pydantic import BaseModel, Field, ValidationError

from src.dialogue.catalog_refs import extract_catalog_references

ORDER_RUNTIME_METADATA_KEY = "order_runtime"
QUOTE_FRAME_METADATA_KEY = "quote_frame"
ACTIVE_QUOTE_FRAME_STATUSES = frozenset({"collecting_details", "repair_required"})

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


class QuoteLine(BaseModel):
    sku: str
    quantity: int
    product_id: str | None = None
    display_name: str | None = None
    unit_price: float | None = None
    currency: str | None = None
    item_candidate: str | None = None

    @property
    def is_valid(self) -> bool:
        return bool(self.sku.strip()) and self.quantity > 0


class QuoteUnresolvedLine(BaseModel):
    sku: str | None = None
    quantity: int
    item_candidate: str

    @property
    def is_valid(self) -> bool:
        return self.quantity > 0 and bool(self.item_candidate.strip())


class QuoteFrame(BaseModel):
    version: int = 1
    frame_id: str | None = None
    source: str = "unknown"
    status: str = "collecting_details"
    lines: list[QuoteLine] = Field(default_factory=list)
    unresolved_items: list[QuoteUnresolvedLine] = Field(default_factory=list)
    quote_details: QuoteDetails = Field(default_factory=QuoteDetails)
    missing_quote_fields: list[str] = Field(default_factory=list)

    @property
    def has_valid_lines(self) -> bool:
        return bool(self.lines) and all(line.is_valid for line in self.lines)


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
    quote_frame: QuoteFrame | None = None
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

        quote_frame = quote_frame_from_metadata(metadata)

        return cls(lines=lines, quote_details=quote_details, quote_frame=quote_frame)


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


def quote_frame_from_metadata(metadata: Mapping[str, Any] | None) -> QuoteFrame | None:
    if not isinstance(metadata, Mapping):
        return None

    runtime = metadata.get(ORDER_RUNTIME_METADATA_KEY)
    if isinstance(runtime, Mapping):
        raw_frame = runtime.get(QUOTE_FRAME_METADATA_KEY)
        if isinstance(raw_frame, Mapping):
            try:
                frame = QuoteFrame.model_validate(raw_frame)
            except ValidationError:
                frame = None
            if frame is not None and frame.has_valid_lines:
                return frame

    return quote_frame_from_legacy_metadata(metadata)


def quote_frame_from_legacy_metadata(
    metadata: Mapping[str, Any] | None,
) -> QuoteFrame | None:
    if not isinstance(metadata, Mapping):
        return None

    selection = metadata.get("pending_quote_selection")
    if not isinstance(selection, Mapping):
        return None

    lines: list[QuoteLine] = []
    raw_items = selection.get("items")
    if isinstance(raw_items, list):
        for raw_item in raw_items:
            line = _quote_line_from_legacy_item(raw_item)
            if line is not None:
                lines.append(line)

    if not lines:
        return None

    source = _mapping_text(selection, "source") or "legacy_pending_quote_selection"
    unresolved_items: list[QuoteUnresolvedLine] = []
    raw_unresolved = selection.get("unresolved_items")
    if isinstance(raw_unresolved, list):
        for raw_item in raw_unresolved:
            unresolved_item = _quote_unresolved_line_from_legacy_item(raw_item)
            if unresolved_item is not None:
                unresolved_items.append(unresolved_item)
    has_unresolved = isinstance(raw_unresolved, list) and bool(raw_unresolved)
    return QuoteFrame(
        source=source,
        status="repair_required" if has_unresolved else "collecting_details",
        lines=lines,
        unresolved_items=unresolved_items,
        quote_details=_quote_details_from_metadata(metadata),
        missing_quote_fields=["items and quantities"] if has_unresolved else [],
    )


def quote_frame_to_metadata(
    metadata: Mapping[str, Any] | None,
    frame: QuoteFrame,
) -> dict[str, Any]:
    updated = dict(metadata or {})
    runtime = updated.get(ORDER_RUNTIME_METADATA_KEY)
    runtime_metadata = dict(runtime) if isinstance(runtime, Mapping) else {}
    runtime_metadata[QUOTE_FRAME_METADATA_KEY] = frame.model_dump()
    updated[ORDER_RUNTIME_METADATA_KEY] = runtime_metadata
    return updated


def quote_frame_is_active(frame: QuoteFrame | None) -> TypeGuard[QuoteFrame]:
    return (
        frame is not None
        and frame.has_valid_lines
        and frame.status in ACTIVE_QUOTE_FRAME_STATUSES
    )


def quote_frame_cleared_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    updated = dict(metadata or {})
    runtime = updated.get(ORDER_RUNTIME_METADATA_KEY)
    if not isinstance(runtime, Mapping):
        return updated
    runtime_metadata = dict(runtime)
    runtime_metadata.pop(QUOTE_FRAME_METADATA_KEY, None)
    if runtime_metadata:
        updated[ORDER_RUNTIME_METADATA_KEY] = runtime_metadata
    else:
        updated.pop(ORDER_RUNTIME_METADATA_KEY, None)
    return updated


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


def _quote_line_from_legacy_item(item: Any) -> QuoteLine | None:
    if not isinstance(item, Mapping):
        return None
    raw_quantity = item.get("quantity")
    if raw_quantity is None:
        return None
    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        return None
    if quantity <= 0:
        return None

    sku = _mapping_text(item, "sku")
    if not sku:
        return None

    unit_price: float | None = None
    raw_unit_price = item.get("unit_price")
    if raw_unit_price is not None:
        try:
            unit_price = float(raw_unit_price)
        except (TypeError, ValueError):
            unit_price = None

    return QuoteLine(
        sku=sku,
        quantity=quantity,
        product_id=_mapping_text(item, "product_id"),
        display_name=_mapping_text(item, "display_name"),
        unit_price=unit_price,
        currency=_mapping_text(item, "currency"),
        item_candidate=(
            _mapping_text(item, "item_candidate")
            or _mapping_text(item, "display_name")
            or sku
        ),
    )


def _quote_unresolved_line_from_legacy_item(item: Any) -> QuoteUnresolvedLine | None:
    if not isinstance(item, Mapping):
        return None
    raw_quantity = item.get("quantity")
    if raw_quantity is None:
        return None
    try:
        quantity = int(raw_quantity)
    except (TypeError, ValueError):
        return None
    if quantity <= 0:
        return None

    item_candidate = _mapping_text(item, "item_candidate")
    if not item_candidate:
        return None
    return QuoteUnresolvedLine(
        sku=_mapping_text(item, "sku"),
        quantity=quantity,
        item_candidate=item_candidate,
    )


def _quote_details_from_metadata(metadata: Mapping[str, Any]) -> QuoteDetails:
    raw_details = metadata.get("quote_customer_details")
    if not isinstance(raw_details, Mapping):
        return QuoteDetails()
    return QuoteDetails(
        name=_mapping_text(raw_details, "name"),
        company=_mapping_text(raw_details, "company"),
        customer_type=_mapping_text(raw_details, "customer_type"),
        email=_mapping_text(raw_details, "email"),
        phone=_mapping_text(raw_details, "phone"),
        address=_mapping_text(raw_details, "address"),
    )


def _mapping_text(value: Mapping[str, Any], key: str) -> str | None:
    raw = value.get(key)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    return None
