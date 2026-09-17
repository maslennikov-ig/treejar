"""Model-owned customer intent tools, registered by the sales engine.

Runtime engine imports preserve existing patch points without a module cycle.
"""

from __future__ import annotations

import datetime
import logging
from copy import deepcopy
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import RunContext

from src.llm.catalog_planning import SalesDeps

logger = logging.getLogger("src.llm.engine")


class RecordedItem(BaseModel):
    """One product line exactly as the customer expressed it."""

    sku: str = Field(description="The catalog SKU, as returned by search_products.")
    quantity: int = Field(description="How many of this SKU the customer wants.")


MAX_RECORDED_QUANTITY = 10_000
MAX_RECORDED_BUDGET_AED = 100_000_000.0
MAX_RECORDED_TEXT_CHARS = 200


class CustomerDetailEvidence(BaseModel):
    """A model-interpreted detail backed by the current customer message."""

    field: Literal["name", "company", "customer_type", "address", "email", "phone"]
    value: str = Field(min_length=1, max_length=500)
    evidence: str = Field(min_length=1, max_length=2000)


async def record_customer_intent(
    ctx: RunContext[SalesDeps],
    evidence: str,
    quotation_consent: Literal["granted", "declined", "deferred"] | None = None,
    details: list[CustomerDetailEvidence] | None = None,
    accept_sent_quotation: bool = False,
) -> str:
    """Record your contextual interpretation of the CURRENT customer message.

    Copy evidence literally from the current message, never history. Judge short
    answers against the last assistant offer and history. Consent is permission
    to prepare a quotation, not order acceptance. Each detail needs its own
    evidence; customer_type='individual' means an explicitly personal purchase.
    Acceptance requires a sent, pending quotation. This tool only records state;
    choose quotation creation and manager notification tools separately.
    """
    from src.llm.engine import (
        QUOTE_CUSTOMER_DETAILS_KEY,
        QuoteConsent,
        QuoteDetails,
        QuoteLifecycle,
        QuoteWorkflowState,
        _customer_facts_write_scope,
        _has_sent_proposal,
        _mark_quotation_accepted,
        _metadata_quotation_decision_status,
        _normalize_customer_facts_mode,
        _quote_customer_details_from_metadata,
        quote_frame_from_metadata,
        quote_frame_to_metadata,
        quote_workflow_to_metadata,
        settings,
        unmask_pii,
    )

    current = ctx.deps.user_query
    if any(not d.value.strip() for d in details or []):
        return "Not recorded: detail values must not be blank."
    if not evidence.strip() or evidence not in current:
        return "Not recorded: evidence must be a literal excerpt of the current customer message."
    if any(not d.evidence.strip() or d.evidence not in current for d in details or []):
        return "Not recorded: every detail needs literal current-message evidence."
    if any(
        d.field == "customer_type" and d.value != "individual" for d in details or []
    ):
        return "Not recorded: customer_type must be individual; use company for a business."
    pii_map = ctx.deps.pii_map
    evidence = unmask_pii(evidence, pii_map)
    details = [
        d.model_copy(
            update={
                "value": unmask_pii(d.value, pii_map),
                "evidence": unmask_pii(d.evidence, pii_map),
            }
        )
        for d in details or []
    ]
    conversation = ctx.deps.conversation
    if (
        accept_sent_quotation
        and _has_sent_proposal(conversation)
        and _metadata_quotation_decision_status(conversation.metadata_ or {})
        in {"approved", "accepted"}
        and not details
        and quotation_consent is None
    ):
        return "Quotation acceptance already recorded. No manager was notified."
    if accept_sent_quotation and (
        not _has_sent_proposal(conversation)
        or _metadata_quotation_decision_status(conversation.metadata_ or {})
        not in {"", "pending"}
    ):
        return "Not recorded: no sent quotation is awaiting acceptance."
    if accept_sent_quotation and quotation_consent in {"declined", "deferred"}:
        return "Not recorded: acceptance conflicts with declined or deferred consent."
    original_metadata = deepcopy(conversation.metadata_)
    original_name = conversation.customer_name
    try:
        async with _customer_facts_write_scope(ctx.deps.db):
            if details:
                values: dict[str, str] = {d.field: d.value.strip() for d in details}
                metadata = dict(conversation.metadata_ or {})
                existing = _quote_customer_details_from_metadata(conversation)
                existing.update(values)
                metadata[QUOTE_CUSTOMER_DETAILS_KEY] = existing
                frame = quote_frame_from_metadata(metadata)
                if frame is not None:
                    metadata = quote_frame_to_metadata(
                        metadata,
                        frame.model_copy(
                            update={"quote_details": QuoteDetails(**existing)},
                            deep=True,
                        ),
                    )
                conversation.metadata_ = metadata
                if "name" in values:
                    conversation.customer_name = values["name"]
            if quotation_consent is not None:
                lifecycle = {
                    "granted": QuoteLifecycle.QUOTE_REQUESTED,
                    "declined": QuoteLifecycle.CONSULTATION,
                    "deferred": QuoteLifecycle.QUOTE_OFFERED,
                }[quotation_consent]
                conversation.metadata_ = quote_workflow_to_metadata(
                    conversation.metadata_,
                    QuoteWorkflowState(
                        consent=QuoteConsent(quotation_consent), lifecycle=lifecycle
                    ),
                )
            if accept_sent_quotation:
                _mark_quotation_accepted(
                    conversation,
                    accepted_at=datetime.datetime.now(datetime.UTC),
                    customer_text=evidence,
                )
            metadata = dict(conversation.metadata_ or {})
            metadata["model_customer_intent"] = {
                "evidence": evidence[:2000],
                "quotation_consent": quotation_consent,
                "accepted_sent_quotation": accept_sent_quotation,
                "details": [d.model_dump() for d in details or []],
            }
            conversation.metadata_ = metadata
            if details or accept_sent_quotation:
                from src.core.config import get_system_config
                from src.services.customer_memory import persist_model_customer_details

                mode = _normalize_customer_facts_mode(
                    await get_system_config(
                        ctx.deps.db, "customer_facts_mode", settings.customer_facts_mode
                    )
                )
                if mode == "enforce":
                    await persist_model_customer_details(
                        ctx.deps.db,
                        conversation=conversation,
                        details={d.field: d.value.strip() for d in details},
                        evidence={d.field: d.evidence for d in details},
                        source_message_id=ctx.deps.source_message_id,
                        accept_sent_quotation=accept_sent_quotation,
                    )
            await ctx.deps.db.flush()
    except Exception:
        conversation.metadata_ = original_metadata
        conversation.customer_name = original_name
        raise
    return "Customer intent recorded. No quotation was created and no manager was notified; use the relevant tool if needed."


async def record_proposal_response(
    ctx: RunContext[SalesDeps],
    evidence: str,
    decision: Literal["rejected", "pause"],
    pause_until: datetime.datetime | None = None,
) -> str:
    """Record rejection or a follow-up pause for an actually sent quotation.

    Interpret the CURRENT customer message in context; copy literal evidence.
    Rejection of a sent quotation differs from declining to generate one.
    For a pause provide a future ISO datetime with timezone if the customer gave
    a date; otherwise the default pause is three days. This sends no messages.
    """
    from src.llm.engine import (
        _customer_facts_write_scope,
        _normalize_customer_facts_mode,
        settings,
        unmask_pii,
    )

    if not evidence.strip() or evidence not in ctx.deps.user_query:
        return "Not recorded: evidence must be a literal current-message excerpt."
    from src.services.proposal_followup import record_model_proposal_response

    conversation = ctx.deps.conversation
    original_metadata = deepcopy(conversation.metadata_)
    try:
        async with _customer_facts_write_scope(ctx.deps.db):
            result = record_model_proposal_response(
                conversation,
                decision=decision,
                evidence=unmask_pii(evidence, ctx.deps.pii_map),
                decided_at=datetime.datetime.now(datetime.UTC),
                pause_until=pause_until,
                source_message_id=ctx.deps.source_message_id,
            )
            if decision == "rejected":
                from src.core.config import get_system_config
                from src.services.customer_memory import persist_model_customer_details

                mode = await get_system_config(
                    ctx.deps.db, "customer_facts_mode", settings.customer_facts_mode
                )
                if _normalize_customer_facts_mode(mode) == "enforce":
                    await persist_model_customer_details(
                        ctx.deps.db,
                        conversation=conversation,
                        details={},
                        evidence={},
                        source_message_id=ctx.deps.source_message_id,
                        reject_sent_quotation=True,
                    )
            await ctx.deps.db.flush()
    except ValueError as exc:
        conversation.metadata_ = original_metadata
        return f"Not recorded: {exc}"
    except Exception:
        conversation.metadata_ = original_metadata
        raise
    return f"Proposal response recorded: {result.reason}. No messages were sent."


async def record_customer_requirements(
    ctx: RunContext[SalesDeps],
    items: list[RecordedItem] | None = None,
    budget_cap_aed: float | None = None,
    needed_by: str | None = None,
    decision_authority: str | None = None,
    company_activity: str | None = None,
    replace_items: bool = False,
    remove_skus: list[str] | None = None,
) -> str:
    """Record what the customer told you, so the conversation stops re-asking it.

    Call this the moment the customer gives any of these, in any wording. "Ten
    of those", "we'll take a dozen", "around 10 chairs" are all a quantity.
    Recording is not answering: you still owe the customer a reply that carries
    something new, and the confirmation of what you recorded rides along inside
    it rather than standing in for it.

    Args:
        items: Product lines the customer has settled on, as SKU and quantity.
        budget_cap_aed: The most the customer will spend, in AED. Per the unit
            they stated it in; say which in your reply.
        needed_by: When they need it, in the customer's own words.
        decision_authority: Who signs this off, in the customer's own words.
        company_activity: What the customer's company does.
        replace_items: Replace the entire selection with items, including an
            empty list to clear it. Use when the customer changes their choice.
            Invalid replacement lines leave all requirements unchanged.
        remove_skus: Remove these exact previously selected SKUs. An unknown
            SKU rejects the change. Do not combine removal with replacement.
    """

    from src.llm.engine import (
        DialogueState,
        _customer_facts_write_scope,
        _find_catalog_product_by_sku,
    )

    logger.info(
        "LLM Tool called: record_customer_requirements(items=%s, budget=%s)",
        len(items or []),
        budget_cap_aed,
    )
    conversation = ctx.deps.conversation
    original_metadata = deepcopy(conversation.metadata_)
    state = DialogueState.from_conversation(conversation)
    slots = state.slots

    recorded: list[str] = []
    rejected: list[str] = []

    existing = {
        str(item.get("sku")): item
        for item in slots.selected_items
        if isinstance(item, dict) and item.get("sku")
    }
    if replace_items and remove_skus:
        return "Not recorded: use replacement or SKU removal, not both."
    removal_keys = {sku.strip() for sku in remove_skus or []}
    unknown_removals = removal_keys - set(existing)
    if unknown_removals:
        return "Not recorded: removal SKUs are not selected: " + ", ".join(
            sorted(unknown_removals)
        )
    if replace_items:
        existing = {}
    for sku in removal_keys:
        existing.pop(sku)
    for item in items or []:
        sku = str(item.sku).strip()
        if not 1 <= item.quantity <= MAX_RECORDED_QUANTITY:
            rejected.append(f"{sku or '?'}: quantity {item.quantity} is out of range")
            continue
        product = await _find_catalog_product_by_sku(ctx.deps.db, sku)
        if product is None:
            # A mis-heard SKU must not become a fact. Search first, then record.
            rejected.append(f"{sku or '?'}: not a catalog SKU, search_products first")
            continue
        canonical = str(product.sku)
        existing[canonical] = {"sku": canonical, "quantity": item.quantity}
        recorded.append(f"{item.quantity} x {canonical}")
    if rejected and (replace_items or removal_keys):
        return "Not recorded: " + "; ".join(rejected) + ". Requirements unchanged."
    slots.selected_items = list(existing.values())
    if replace_items:
        recorded.append("selection replaced" if existing else "selection cleared")
    if removal_keys:
        recorded.append("removed " + ", ".join(sorted(removal_keys)))

    def _text(value: str | None) -> str | None:
        cleaned = " ".join(str(value or "").split())[:MAX_RECORDED_TEXT_CHARS]
        return cleaned or None

    if budget_cap_aed is not None:
        if 0 < budget_cap_aed <= MAX_RECORDED_BUDGET_AED:
            slots.budget_cap_aed = float(budget_cap_aed)
            recorded.append(f"budget {budget_cap_aed:g} AED")
        else:
            rejected.append(f"budget {budget_cap_aed:g} is out of range")
    for slot_name, value in (
        ("needed_by", needed_by),
        ("decision_authority", decision_authority),
        ("company_activity", company_activity),
    ):
        cleaned = _text(value)
        if cleaned:
            setattr(slots, slot_name, cleaned)
            recorded.append(f"{slot_name.replace('_', ' ')}: {cleaned}")

    if not recorded and not rejected:
        return "Nothing to record."

    try:
        async with _customer_facts_write_scope(ctx.deps.db):
            conversation.metadata_ = state.to_metadata(conversation.metadata_)
            await ctx.deps.db.flush()
    except Exception:
        conversation.metadata_ = original_metadata
        raise

    parts = []
    if recorded:
        parts.append("Recorded: " + "; ".join(recorded) + ".")
    if rejected:
        parts.append("Not recorded: " + "; ".join(rejected) + ".")
    parts.append(
        "Carry what you recorded into your reply so the customer can correct "
        "it -- alongside the answer, never instead of one. A turn whose whole "
        "content is a confirmation of what they just said is not a reply."
    )
    return " ".join(parts)
