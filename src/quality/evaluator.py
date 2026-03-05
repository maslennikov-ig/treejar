"""Quality evaluator — LLM-as-a-judge for conversation scoring.

Uses a dedicated PydanticAI Agent with structured output (EvaluationResult).
Evaluates completed dialogues against 15 criteria from the sales dialogue checklist.

See: docs/06-dialogue-evaluation-checklist.md
"""
from __future__ import annotations

import logging
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.message import Message
from src.quality.schemas import EvaluationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Evaluation Prompt (15 criteria embedded — no file I/O at runtime)
# https://github.com/treejar/docs/06-dialogue-evaluation-checklist.md
# ---------------------------------------------------------------------------

EVALUATION_PROMPT = """You are an expert quality assessor for Treejar, a furniture trading company in the UAE.
Your task is to evaluate a sales dialogue between a bot/manager (Siyyad from Treejar) and a customer.

Score each of the 15 criteria below on a 0-2 scale:
- 2 = fully met (clear evidence in the dialogue)
- 1 = partially met (some attempt but incomplete)
- 0 = not met (absent or actively violated)

## Evaluation Criteria

1. Always greeting + name (Siyyad) + company (Treejar) at the start.
2. Polite and professional greeting and introduction.
3. Asked the customer: "How should I address you?" (or equivalent).
4. Maintained a friendly tone and showed active listening throughout.
5. Demonstrated genuine interest in the client's needs.
6. Gave a sincere compliment or showed appreciation.
7. Briefly communicated Treejar's value proposition.
8. Asked clarifying questions about the customer's requirements.
9. Applied the "drill and hole" principle: focused on solving the client's problem, not just selling a product.
10. Once the problem was understood, proposed a comprehensive solution beyond the initial request.
11. Offered a discount, bundle deal, or bonus for a complete package.
12. Collected contact details: name, position, company, email, preferred communication channel.
13. Asked what the client's company does (its business/industry).
14. Closing: confirmed the order, details, and the concrete next step.
15. If the client wasn't ready to buy: agreed on the next contact date/time.

## Instructions

- Be objective. Quote specific dialogue moments in your comments.
- Score EVERY criterion. If absent, score 0.
- Return EXACTLY 15 criteria scores (rule_number 1-15).
- Compute total_score = sum of all 15 scores (max 30).
- Rating: excellent (26-30), good (20-25), satisfactory (14-19), poor (<14).
- In summary: highlight strengths, areas for improvement, recommendations for the next contact.
"""

# ---------------------------------------------------------------------------
# PydanticAI Judge Agent
# Dedicated agent — does NOT reuse sales_agent to avoid tool contamination.
# ---------------------------------------------------------------------------

_model = OpenAIChatModel(
    settings.openrouter_model_main,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

judge_agent: Agent[None, EvaluationResult] = Agent(
    _model,
    output_type=EvaluationResult,
    retries=2,
    instructions=EVALUATION_PROMPT,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def evaluate_conversation(
    conversation_id: UUID,
    db: AsyncSession,
) -> EvaluationResult:
    """Evaluate a conversation using the LLM judge.

    Loads all messages, formats them as a dialogue transcript, and sends
    to the judge agent for structured evaluation against 15 criteria.

    Args:
        conversation_id: UUID of the conversation to evaluate.
        db: Async SQLAlchemy session.

    Returns:
        EvaluationResult with scores for all 15 criteria.

    Raises:
        ValueError: If conversation has no messages to evaluate.
    """
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    if not messages:
        raise ValueError(f"No messages found for conversation {conversation_id}")

    # Format dialogue as plain text transcript
    dialogue_lines = [f"{msg.role}: {msg.content}" for msg in messages]
    dialogue_text = "\n".join(dialogue_lines)

    user_prompt = (
        f"Please evaluate the following sales dialogue "
        f"({len(messages)} messages):\n\n{dialogue_text}"
    )

    logger.info(
        "Evaluating conversation %s (%d messages)",
        conversation_id,
        len(messages),
    )

    run_result = await judge_agent.run(user_prompt)
    return run_result.output
