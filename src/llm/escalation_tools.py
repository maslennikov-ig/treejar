"""Manager handoff tool; keep the side effect behind the critical-case policy."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic_ai import RunContext

from src.llm.catalog_planning import SalesDeps
from src.llm.escalation_policy import critical_escalation_decision
from src.services.escalation_state import is_active_human_handoff

logger = logging.getLogger("src.llm.engine")


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

    await notify_manager_escalation(
        conversation=ctx.deps.conversation,
        reason=decision.reason,
        recent_messages=recent_messages,
        db=ctx.deps.db,
        escalation_type=decision.escalation_type,
    )

    return (
        "Manager has been notified. Acknowledge the customer's request politely "
        "and let them know a human manager will review their conversation shortly."
    )
