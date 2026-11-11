"""Manager handoff tool; keep the side effect behind the critical-case policy."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal

from pydantic_ai import RunContext

from src.llm.catalog_planning import SalesDeps
from src.llm.escalation_policy import (
    B2B_HANDOFF_TRIGGERS,
    NON_PAUSING_HANDOFF_TRIGGERS,
    WHOLESALE_HANDOFF_METADATA_KEY,
    critical_escalation_decision,
)
from src.services.escalation_state import is_active_human_handoff

logger = logging.getLogger("src.llm.engine")

_NON_PAUSING_LEADS_KEY = "manager_sourcing_leads_notified"


async def escalate_to_manager(
    ctx: RunContext[SalesDeps],
    reason: str,
    escalation_type: Literal[
        "order_confirmation", "human_requested", "general"
    ] = "general",
) -> str:
    """Notify a manager only for a current, customer-evidenced critical case.

    Args:
        reason: Clear explanation of why escalation is needed.
        escalation_type: Requested handoff type; the policy selects the actual type.
    """
    logger.info(
        "LLM Tool called: escalate_to_manager(reason=%r, type=%s)",
        reason,
        escalation_type,
    )
    from src.integrations.notifications.escalation import notify_manager_escalation

    if is_active_human_handoff(ctx.deps.conversation.escalation_status):
        return "Manager handoff is already active. Do not create another notification."

    recent_messages = ctx.deps.recent_history or []
    decision = critical_escalation_decision(
        customer_text=ctx.deps.user_query,
        conversation_metadata=ctx.deps.conversation.metadata_ or {},
        recent_history=recent_messages,
        quote_acceptance_recorded_this_turn=getattr(
            ctx.deps, "quote_acceptance_recorded_this_turn", False
        ),
    )
    if not decision.allowed or decision.escalation_type is None:
        logger.warning(
            "Noncritical manager escalation blocked: requested_type=%s reason=%r",
            escalation_type,
            reason,
        )
        return (
            "Escalation was not created because this turn has no critical "
            "human-only trigger. Continue helping autonomously, state any "
            "uncertainty plainly, and offer one safe next step. Do not say that "
            "a manager was notified."
        )

    trigger = decision.trigger
    non_pausing = trigger in NON_PAUSING_HANDOFF_TRIGGERS
    metadata = (
        dict(ctx.deps.conversation.metadata_)
        if isinstance(ctx.deps.conversation.metadata_, dict)
        else {}
    )
    notified_leads = metadata.get(_NON_PAUSING_LEADS_KEY)
    if non_pausing and isinstance(notified_leads, list) and trigger in notified_leads:
        if trigger == "external_order_support":
            return (
                "The manager already has this external order inquiry. Do not "
                "create another alert; answer any catalog, stock, showroom, or "
                "policy question you can verify and leave order-specific "
                "readiness for the team to confirm."
            )
        return (
            "The manager already has this sourcing request. Do not mention it "
            "again unless the customer asks; answer the rest of the message."
        )

    manager_reason = decision.reason
    if trigger in B2B_HANDOFF_TRIGGERS or trigger == "external_order_support":
        brief = " ".join(str(reason or "").split())[:300]
        if brief:
            manager_reason = f"{manager_reason} Assistant brief: {brief}"

    await notify_manager_escalation(
        conversation=ctx.deps.conversation,
        reason=manager_reason,
        recent_messages=recent_messages,
        db=ctx.deps.db,
        escalation_type=decision.escalation_type,
        pause_bot=not non_pausing,
    )

    if non_pausing:
        metadata[_NON_PAUSING_LEADS_KEY] = [
            *(notified_leads if isinstance(notified_leads, list) else []),
            trigger,
        ]
        ctx.deps.conversation.metadata_ = metadata
        if trigger == "external_order_support":
            return (
                "A manager has been notified to check this existing order; you "
                "stay in the conversation. Let the customer know our team has "
                "been notified to confirm their order details or pickup "
                "readiness, do not invent order status or pickup timing, and "
                "answer every other product, stock, or showroom question in "
                "their message."
            )
        return (
            "The sourcing request was passed to a manager; you stay in the "
            "conversation. Say plainly that Treejar does not carry this item in "
            "its office furniture catalog and that a manager can check sourcing "
            "options, then answer every other part of the customer's message."
        )
    if trigger == "wholesale_or_bulk_project":
        metadata[WHOLESALE_HANDOFF_METADATA_KEY] = datetime.now(UTC).isoformat()
        ctx.deps.conversation.metadata_ = metadata
    if trigger in B2B_HANDOFF_TRIGGERS:
        return (
            "Manager has been notified and will take over this project. In the "
            "same reply, present the 2-3 standard in-stock catalog reference "
            "options already returned by search_products with their verified "
            "prices (excl. 5% VAT) -- their photos are sent automatically -- "
            "confirm a manager will handle project pricing and any custom work "
            "without promising a discount, lead time or delivery date, and end "
            "with one short question for the brief: company name, target "
            "delivery timeline and delivery location in the UAE."
        )

    return (
        "Manager has been notified. Acknowledge the customer's request politely "
        "and let them know a human manager will review their conversation shortly."
    )


_NON_SALES_NOTICE_KEY = "non_sales_notice"


async def report_non_sales_inquiry(
    ctx: RunContext[SalesDeps],
    inquiry_type: Literal["supplier_pitch", "recruitment", "other_non_sales"],
    summary: str,
) -> str:
    """Log a supplier/partnership pitch or job/CV inquiry for internal review without pausing Noor.

    Args:
        inquiry_type: Whether the sender is pitching as a supplier/manufacturer, applying for a job/internship, or making another non-sales outreach.
        summary: Concise 1-sentence summary of who reached out and what they offered or asked.
    """
    logger.info(
        "LLM Tool called: report_non_sales_inquiry(type=%s, summary=%r)",
        inquiry_type,
        summary,
    )
    from src.integrations.notifications.escalation import notify_manager_escalation
    from src.schemas.common import EscalationType

    if is_active_human_handoff(ctx.deps.conversation.escalation_status):
        return "Manager handoff is already active. Do not create another notification."

    metadata = (
        dict(ctx.deps.conversation.metadata_)
        if isinstance(ctx.deps.conversation.metadata_, dict)
        else {}
    )
    if metadata.get(_NON_SALES_NOTICE_KEY):
        return (
            "Already logged for internal review; you stay active in the chat. "
            "Reply briefly and politely within the sales channel boundary without "
            "sharing staff personal contact numbers or asking sales/quotation questions."
        )

    clean_summary = " ".join(str(summary or "").split())[:240]
    label = {
        "supplier_pitch": "supplier pitch",
        "recruitment": "job application",
        "other_non_sales": "non-sales inquiry",
    }.get(inquiry_type, "non-sales inquiry")

    metadata[_NON_SALES_NOTICE_KEY] = {
        "intent": inquiry_type,
        "summary": clean_summary,
        "source": "model_tool",
        "at": datetime.now(UTC).isoformat(),
    }
    ctx.deps.conversation.metadata_ = metadata
    reason_detail = f" ({clean_summary})" if clean_summary else ""
    await notify_manager_escalation(
        conversation=ctx.deps.conversation,
        reason=(
            f"Not a sales lead: {label} on the sales line{reason_detail}. "
            "For your review; Noor keeps answering."
        ),
        recent_messages=[*(ctx.deps.recent_history or []), ctx.deps.user_query],
        db=ctx.deps.db,
        escalation_type=EscalationType.GENERAL,
        pause_bot=False,
    )

    if inquiry_type == "supplier_pitch":
        return (
            "Logged for Treejar's commercial team (chat is not paused). Politely "
            "let the sender know this WhatsApp line is for office furniture "
            "customer inquiries, mention that you have passed their note to "
            "Treejar's commercial team (or direct them to treejartrading.ae), "
            "do not share staff personal numbers, and do not ask sales or "
            "quotation questions."
        )
    if inquiry_type == "recruitment":
        return (
            "Logged internally (chat is not paused). Politely let the sender know "
            "this WhatsApp line handles office furniture sales inquiries and "
            "direct them to treejartrading.ae for careers; do not claim their "
            "application was forwarded to HR, and do not ask sales or quotation "
            "questions."
        )
    return (
        "Logged internally (chat is not paused). Politely state that this "
        "WhatsApp line assists only with Treejar office furniture inquiries, and "
        "do not ask sales or quotation questions."
    )
