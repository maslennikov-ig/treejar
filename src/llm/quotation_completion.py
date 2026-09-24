"""Finish the quotation on the turn that makes it ready (tj-2ey4).

Live check 2026-09-24: consent was recorded, the customer had chosen exactly
one line, and then sent company, address and email in one message. The model
recorded the details, never called `create_quotation`, and asked for the name
it already had; the reply guard turned that into "I already have your name, so
I will continue with your request", and nothing continued.

The model still owns the reading of the message. This module reads only typed
state that validated tools wrote -- consent, the recorded selection, the
customer details and the quote lifecycle -- and answers one question: did this
turn make a quotation ready that nobody created? When it did, the runtime makes
the call the model was directed to make. No customer wording is inspected.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from src.dialogue.order_state import (
    QuoteConsent,
    QuoteLifecycle,
    quote_workflow_from_metadata,
)
from src.dialogue.state import DialogueState
from src.llm.order_quote_routes import QuotationItem
from src.services.escalation_state import is_active_human_handoff

_CLOSED_LIFECYCLES = frozenset({QuoteLifecycle.CREATING, QuoteLifecycle.CREATED})


@dataclass(frozen=True)
class QuotationReadiness:
    """The facts a quotation needs, as durable state holds them right now."""

    consent_granted: bool
    details_complete: bool
    lifecycle_open: bool
    items: tuple[QuotationItem, ...]

    @property
    def ready(self) -> bool:
        return (
            self.consent_granted
            and self.details_complete
            and self.lifecycle_open
            and bool(self.items)
        )


def recorded_quotation_items(conversation: Any) -> tuple[QuotationItem, ...]:
    """The recorded selection as quotation lines, or nothing if any line is open.

    `record_customer_requirements` writes these only for catalog SKUs with a
    quantity, so a complete selection is an exact one.
    """

    state = DialogueState.from_conversation(conversation)
    items: list[QuotationItem] = []
    for line in state.slots.selected_items:
        if not isinstance(line, Mapping):
            return ()
        sku = str(line.get("sku") or "").strip()
        quantity = line.get("quantity")
        if not sku or isinstance(quantity, bool) or not isinstance(quantity, int):
            return ()
        if quantity <= 0:
            return ()
        items.append(QuotationItem(sku=sku, quantity=quantity))
    return tuple(items)


def quotation_readiness(deps: Any) -> QuotationReadiness:
    from src.llm.engine import _quote_missing_customer_details

    conversation = deps.conversation
    metadata = getattr(conversation, "metadata_", None)
    workflow = quote_workflow_from_metadata(
        metadata if isinstance(metadata, Mapping) else None
    )
    return QuotationReadiness(
        consent_granted=workflow.consent is QuoteConsent.GRANTED,
        details_complete=not _quote_missing_customer_details(deps),
        lifecycle_open=workflow.lifecycle not in _CLOSED_LIFECYCLES,
        items=recorded_quotation_items(conversation),
    )


def quotation_items_to_complete(
    before: QuotationReadiness,
    deps: Any,
) -> tuple[QuotationItem, ...]:
    """Lines to quote now, or nothing when the turn owes no quotation.

    Owed only when this turn completed the consent or the details (a turn
    that merely changes the selection is the model's to answer) and the result
    is ready. The open lifecycle is also the proof that no quotation call got
    as far as Zoho this turn: `create_quotation` marks the workflow CREATING
    before its first side effect, so a created, deferred or failed attempt is
    never repeated here, along with any manager alert it raised. A call that
    was refused before that point -- too early, before the details were
    recorded -- did nothing, and is owed again.
    """

    if before.consent_granted and before.details_complete:
        return ()
    if getattr(deps, "quotation_created", False) is True:
        return ()
    if is_active_human_handoff(getattr(deps.conversation, "escalation_status", None)):
        return ()
    after = quotation_readiness(deps)
    if not after.ready:
        return ()
    return after.items


def _directive_value(value: str) -> str:
    """One line with no quote or bracket marks: a tool result stays data."""

    return " ".join(
        "".join(" " if char in '"`<>[]{}' else char for char in value).split()
    )


def quotation_completion_directive(
    items: Sequence[QuotationItem],
    tool_result: str,
) -> str:
    lines = "; ".join(f"{item.quantity} x SKU {item.sku}" for item in items)
    return (
        "QUOTATION CALL MADE BY THE RUNTIME -- the customer's consent, the chosen "
        "items and every required detail are recorded, so create_quotation was "
        f"called for: {lines}. Its result: {_directive_value(tool_result)} -- "
        "Write the reply to the customer's current message from that result: "
        "acknowledge the details they just sent in a few words, then state the "
        "quotation outcome exactly as the result gives it. Do not ask for any "
        "detail that is already recorded, and never say a quotation was created "
        "or sent unless the result says so."
    )


__all__ = [
    "QuotationReadiness",
    "quotation_completion_directive",
    "quotation_items_to_complete",
    "quotation_readiness",
    "recorded_quotation_items",
]
