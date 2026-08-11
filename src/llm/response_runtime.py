"""Response transport types and reply construction helpers."""

from __future__ import annotations

import inspect
import re
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal

from src.dialogue.order_state import QuoteConsent
from src.llm.response_policy import RenderedReply
from src.services.runtime_execution_evidence import RuntimeToolTrace


@dataclass
class LLMResponse:
    text: str
    tokens_in: int | None
    tokens_out: int | None
    cost: float | None
    model: str
    usage_provenance: Literal["provider_reported", "deterministic_static"] = (
        "provider_reported"
    )
    text_provenance: Literal[
        "model", "model_repaired", "deterministic_replacement", "deterministic_static"
    ] = "model"
    deferred_product_media: tuple[ProductMediaPayload, ...] = ()
    tool_traces: tuple[RuntimeToolTrace, ...] = ()


@dataclass(frozen=True)
class CustomerFactsRun:
    context_text: str | None = None
    past_order_response: str | None = None


@asynccontextmanager
async def _customer_facts_write_scope(db: Any) -> AsyncIterator[None]:
    """Isolate optional memory writes so failures do not poison legacy handling."""

    begin_nested = getattr(db, "begin_nested", None)
    if not callable(begin_nested):
        yield
        return

    transaction = begin_nested()
    if inspect.isawaitable(transaction):
        close = getattr(transaction, "close", None)
        if callable(close):
            close()
        yield
        return

    if hasattr(transaction, "__aenter__") and hasattr(transaction, "__aexit__"):
        async with transaction:
            yield
        return

    yield


@dataclass(frozen=True)
class ProductMediaPayload:
    url: str
    caption: str
    product_key: str
    zoho_item_id: str | None = None
    reference_tokens: tuple[str, ...] = ()


def _response_from_rendered_reply(
    rendered: RenderedReply,
    *,
    tokens_in: int | None,
    tokens_out: int | None,
    cost: float | None,
    model: str,
    usage_provenance: Literal["provider_reported", "deterministic_static"],
    deferred_product_media: tuple[ProductMediaPayload, ...] = (),
    tool_traces: tuple[RuntimeToolTrace, ...] = (),
) -> LLMResponse:
    """Build the transport response only from text that passed the policy."""

    return LLMResponse(
        text=rendered.text,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost=cost,
        model=model,
        usage_provenance=usage_provenance,
        text_provenance=rendered.provenance,
        deferred_product_media=deferred_product_media,
        tool_traces=tool_traces,
    )


_PRODUCT_REFERENCE_VARIANT_WORDS = frozenset(
    {
        "beige",
        "black",
        "blue",
        "brown",
        "green",
        "grey",
        "gray",
        "new",
        "orange",
        "red",
        "walnut",
        "white",
        "yellow",
    }
)


def _normalized_product_reference(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold()).split())


def _product_media_is_referenced(
    item: ProductMediaPayload,
    response_text: str,
) -> bool:
    if not item.reference_tokens:
        return True

    normalized_response = _normalized_product_reference(response_text)
    response_words = set(normalized_response.split())
    for raw_reference in item.reference_tokens:
        reference = _normalized_product_reference(raw_reference)
        if not reference:
            continue
        if reference in normalized_response:
            return True

        reference_words = [
            word
            for word in reference.split()
            if word not in _PRODUCT_REFERENCE_VARIANT_WORDS
        ]
        if (
            len(reference_words) >= 2
            and any(any(char.isdigit() for char in word) for word in reference_words)
            and all(word in response_words for word in reference_words)
        ):
            return True

    return False


@dataclass(frozen=True)
class ExactQuoteCandidate:
    quantity: int
    item_candidate: str
    sku: str | None


@dataclass(frozen=True)
class PurchaseSelectionItem:
    quantity: int
    item_candidate: str
    sku: str
    stated_unit_price: float | None = None
    stated_currency: str | None = None


@dataclass(frozen=True)
class PurchaseSelection:
    items: tuple[PurchaseSelectionItem, ...]
    order_runtime_trace: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class OrderRuntimePurchaseSelection:
    selection: PurchaseSelection | None
    block_legacy: bool = False


@dataclass(frozen=True)
class ResolvedPurchaseSelectionItem:
    requested: PurchaseSelectionItem
    product: Any
    availability: int | None
    unit_price: float | None
    currency: str
    availability_source: Literal["zoho", "catalog", "unconfirmed"]
    source_caption: str | None = None


@dataclass(frozen=True)
class PurchaseSelectionResolution:
    resolved: tuple[ResolvedPurchaseSelectionItem, ...]
    unresolved: tuple[PurchaseSelectionItem, ...]


@dataclass(frozen=True)
class SalesOpportunityRequest:
    amount: float | None
    currency: str | None
    quote_consent: QuoteConsent
    decision_horizon_days: int | None = None
    decision_horizon_hours: int | None = None


@dataclass(frozen=True)
class SalesOpportunityWriteResult:
    verified: bool
    deal_id: str | None = None
    stage: str | None = None
    reused: bool = False
    error: str | None = None


@dataclass(frozen=True)
class PendingReferenceRoute:
    selection: PurchaseSelection | None = None
    clear_pending_reference_quantity: bool = False
    clear_pending_question_frame: bool = False


@dataclass(frozen=True)
class CommercialPriceDecision:
    unit_price: float
    currency: str
    source: Literal["catalog", "zoho", "unavailable"]
    catalog_price: float | None
    zoho_rate: float | None
