"""Manager handoff tool; keep the side effect behind the critical-case policy."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic_ai import RunContext

from src.llm.catalog_planning import SalesDeps
from src.llm.escalation_policy import (
    B2B_HANDOFF_TRIGGERS,
    NON_PAUSING_HANDOFF_TRIGGERS,
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
        return (
            "The manager already has this sourcing request. Do not mention it "
            "again unless the customer asks; answer the rest of the message."
        )

    manager_reason = decision.reason
    if trigger in B2B_HANDOFF_TRIGGERS:
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
        return (
            "The sourcing request was passed to a manager; you stay in the "
            "conversation. Say plainly that Treejar does not carry this item in "
            "its office furniture catalog and that a manager can check sourcing "
            "options, then answer every other part of the customer's message."
        )
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
