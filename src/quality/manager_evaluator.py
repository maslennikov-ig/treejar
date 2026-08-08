"""Manager quality evaluator — LLM-as-a-judge for manager conversations.

Uses a dedicated PydanticAI Agent with structured output (ManagerEvaluationResult).
Evaluates post-escalation manager dialogues against 10 criteria from
docs/08-manager-evaluation-criteria.md. Also calculates quantitative
business metrics (response time, conversion, message count, deal amount).

See: docs/08-manager-evaluation-criteria.md
"""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Any
from uuid import UUID

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.llm.safety import (
    PATH_QUALITY_MANAGER,
    attach_llm_usage_telemetry,
    extract_llm_usage_telemetry,
    model_name_for_path,
    model_settings_for_path,
    run_agent_with_safety,
)
from src.models.conversation import Conversation
from src.models.conversation_summary import ConversationSummary
from src.models.escalation import Escalation
from src.models.manager_review import ManagerReview
from src.models.message import Message
from src.quality.config import AIQualityTranscriptMode
from src.quality.manager_schemas import (
    ManagerCriterionScore,
    ManagerEvaluationResult,
    compute_manager_rating,
)
from src.quality.transcript_context import (
    ReviewContextPurpose,
    build_review_transcript_context,
)

logger = logging.getLogger(__name__)
_provider = OpenRouterProvider(api_key=settings.openrouter_api_key)
_MANAGER_MODEL_NAME = model_name_for_path(PATH_QUALITY_MANAGER)

# ---------------------------------------------------------------------------
# Manager Evaluation Prompt (10 criteria from manager-evaluation-criteria.md)
# ---------------------------------------------------------------------------

MANAGER_EVALUATION_PROMPT = """You are a Treejar expert in evaluating the quality of manager conversations.
Your task is to evaluate a conversation between a manager and a customer after an escalation.

The manager took over after a handoff from the AI bot Noor. The escalation reason,
the context and the conversation itself are supplied below.

Score each of the 10 criteria on a 0-2 scale:
- 2 = the criterion is fully met
- 1 = partially met
- 0 = not met or violated

## Evaluation criteria

1. Fast pickup: the manager continued the conversation from where the bot left off.
2. Use of context: the manager used the customer data the bot had collected.
3. Professional tone: polite, literate, businesslike communication style.
4. Problem resolution: the specific request/problem that caused the escalation was handled.
5. Proactivity: additional solutions, alternatives or cross-sell were offered.
6. Objection handling: objections such as "too expensive", "out of stock", or competitor comparisons were handled.
7. Movement towards closing: a quotation, follow-up or concrete next step was offered.
8. Completeness of information: prices, availability, delivery times and terms were given.
9. Data collection: company, email and role were requested for the CRM/quotation.
10. Closing and follow-up: the outcome and the next concrete step were recorded.

## Instructions

- Be objective. Cite exact quotes or conversation fragments in `comment` when they are the evidence.
- Score EVERY criterion. If it is absent, score it 0.
- Return EXACTLY 10 criterion scores (`rule_number` from 1 to 10).
- The `rating` field must use only the canonical values: `excellent`, `good`, `satisfactory`, `poor`.
- Write every human-readable text field (`summary`, `rule_name`, `comment`) in English.
- Exact customer/conversation quotes may stay in their original language when they are evidence.
- Write `summary` in English as 3 short lines with these prefixes:
  `In brief:`
  `What held the outcome back:`
  `Recommendations:`
- `total_score` = the sum of all 10 scores (maximum 20).
"""

# ---------------------------------------------------------------------------
# PydanticAI Judge Agent (Manager)
# ---------------------------------------------------------------------------

_model = OpenAIChatModel(
    _MANAGER_MODEL_NAME,
    provider=_provider,
    settings=model_settings_for_path(
        PATH_QUALITY_MANAGER,
        model_name=_MANAGER_MODEL_NAME,
    ),
)

manager_judge_agent: Agent[None, ManagerEvaluationResult] = Agent(
    _model,
    output_type=ManagerEvaluationResult,
    retries=0,
    instructions=MANAGER_EVALUATION_PROMPT,
    model_settings=model_settings_for_path(
        PATH_QUALITY_MANAGER,
        model_name=_MANAGER_MODEL_NAME,
    ),
)

INSUFFICIENT_MANAGER_SUMMARY = (
    "In brief: Insufficient data for an AI evaluation.\n"
    "What held the outcome back: transcript content is unavailable in this mode.\n"
    "Recommendations: Review the conversation manually if needed."
)


@manager_judge_agent.output_validator
async def validate_manager_evaluation(
    ctx: RunContext[None], result: ManagerEvaluationResult
) -> ManagerEvaluationResult:
    """Validate criteria count and recompute score deterministically."""
    if len(result.criteria) != 10:
        raise ModelRetry(
            f"You returned {len(result.criteria)} criteria, but EXACTLY 10 are required "
            f"(one per rule_number 1-10). Please re-evaluate and return scores for ALL 10 rules."
        )
    computed_total = sum(c.score for c in result.criteria)
    computed_rating = compute_manager_rating(computed_total)
    return result.model_copy(
        update={"total_score": float(computed_total), "rating": computed_rating}
    )


# ---------------------------------------------------------------------------
# Quantitative Metrics (Component 6)
# ---------------------------------------------------------------------------


class ManagerMetrics:
    """Container for quantitative manager metrics."""

    def __init__(
        self,
        first_response_time_seconds: int | None = None,
        message_count: int | None = None,
        deal_converted: bool = False,
        deal_amount: float | None = None,
    ) -> None:
        self.first_response_time_seconds = first_response_time_seconds
        self.message_count = message_count
        self.deal_converted = deal_converted
        self.deal_amount = deal_amount


def _insufficient_manager_evaluation() -> ManagerEvaluationResult:
    criteria = [
        ManagerCriterionScore(
            rule_number=rule_number,
            rule_name=f"Rule {rule_number}",
            score=0,
            comment="Insufficient data: transcript content is unavailable for evaluation.",
        )
        for rule_number in range(1, 11)
    ]
    return ManagerEvaluationResult(
        criteria=criteria,
        summary=INSUFFICIENT_MANAGER_SUMMARY,
        total_score=0.0,
        rating="poor",
    )


def is_insufficient_manager_evaluation(result: ManagerEvaluationResult) -> bool:
    """Return True for local no-action manager QA results."""
    return result.summary == INSUFFICIENT_MANAGER_SUMMARY


async def calculate_manager_metrics(
    escalation: Escalation,
    conversation: Conversation,
    db: AsyncSession,
) -> ManagerMetrics:
    """Calculate quantitative business metrics for a manager interaction.

    Args:
        escalation: The escalation that triggered manager involvement.
        conversation: The conversation being evaluated.
        db: Async SQLAlchemy session.

    Returns:
        ManagerMetrics with response time, message count, conversion, and deal amount.
    """
    # First response time: first manager message after escalation
    first_mgr_msg_stmt = select(func.min(Message.created_at)).where(
        Message.conversation_id == conversation.id,
        Message.role == "manager",
        Message.created_at >= escalation.created_at,
    )
    first_mgr_time_result = await db.scalar(first_mgr_msg_stmt)

    first_response_time_seconds: int | None = None
    if first_mgr_time_result is not None:
        esc_time = escalation.created_at
        if esc_time.tzinfo is None:
            esc_time = esc_time.replace(tzinfo=UTC)
        mgr_time = first_mgr_time_result
        if mgr_time.tzinfo is None:
            mgr_time = mgr_time.replace(tzinfo=UTC)
        delta = (mgr_time - esc_time).total_seconds()
        first_response_time_seconds = int(max(delta, 0))

    # Manager message count
    mgr_msg_count_stmt = (
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "manager",
        )
    )
    message_count_result = await db.scalar(mgr_msg_count_stmt)
    message_count = message_count_result or 0

    # Deal conversion
    deal_converted = conversation.zoho_deal_id is not None

    # Deal amount
    deal_amount = float(conversation.deal_amount) if conversation.deal_amount else None

    return ManagerMetrics(
        first_response_time_seconds=first_response_time_seconds,
        message_count=message_count,
        deal_converted=deal_converted,
        deal_amount=deal_amount,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def evaluate_manager_conversation(
    escalation_id: UUID,
    db: AsyncSession,
    model_name: str | None = None,
    transcript_mode: AIQualityTranscriptMode | str = AIQualityTranscriptMode.SUMMARY,
    cache_telemetry_enabled: bool = True,
) -> tuple[ManagerEvaluationResult, ManagerMetrics]:
    """Evaluate a manager's post-escalation conversation.

    Loads the escalation, related conversation and messages, formats the
    dialogue transcript with escalation context, and sends to the manager
    judge agent for structured evaluation. Also calculates quantitative metrics.

    Args:
        escalation_id: UUID of the escalation to evaluate.
        db: Async SQLAlchemy session.

    Returns:
        Tuple of (ManagerEvaluationResult, ManagerMetrics).

    Raises:
        ValueError: If escalation not found or no post-escalation messages.
    """
    selected_model = model_name_for_path(PATH_QUALITY_MANAGER, model_name)
    mode = AIQualityTranscriptMode(transcript_mode)

    # Load escalation with conversation
    esc_stmt = select(Escalation).where(Escalation.id == escalation_id)
    esc_result = await db.execute(esc_stmt)
    escalation = esc_result.scalar_one_or_none()

    if escalation is None:
        raise ValueError(f"Escalation {escalation_id} not found")

    conv_stmt = select(Conversation).where(
        Conversation.id == escalation.conversation_id
    )
    conv_result = await db.execute(conv_stmt)
    conversation = conv_result.scalar_one_or_none()

    if conversation is None:
        raise ValueError(f"Conversation for escalation {escalation_id} not found")

    # Load messages after escalation
    msg_stmt = (
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.created_at >= escalation.created_at,
            Message.role.in_(["user", "manager"]),
        )
        .order_by(Message.created_at)
    )
    msg_result = await db.execute(msg_stmt)
    messages = msg_result.scalars().all()

    if not messages:
        raise ValueError(
            f"No post-escalation messages found for escalation {escalation_id}"
        )

    all_msg_stmt = (
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.created_at, Message.id)
    )
    all_msg_result = await db.execute(all_msg_stmt)
    all_messages = list(all_msg_result.scalars().all())
    if not all_messages:
        all_messages = list(messages)

    # Calculate quantitative metrics
    metrics = await calculate_manager_metrics(escalation, conversation, db)

    escalation_context = (
        f"Escalation reason: {escalation.reason}\n"
        f"Escalation notes: {escalation.notes or 'n/a'}\n"
        f"Manager: {escalation.assigned_to or 'not specified'}\n"
    )
    summary_text = None
    if mode != AIQualityTranscriptMode.FULL:
        try:
            summary_result = await db.execute(
                select(ConversationSummary).where(
                    ConversationSummary.conversation_id == conversation.id
                )
            )
            summary = summary_result.scalar_one_or_none()
            summary_text = (
                summary.summary_text
                if isinstance(summary, ConversationSummary)
                else getattr(summary, "summary_text", None)
            )
            if not isinstance(summary_text, str):
                summary_text = None
        except Exception:
            logger.debug(
                "Conversation summary unavailable for manager quality context",
                exc_info=True,
            )

    context = build_review_transcript_context(
        all_messages,
        purpose=ReviewContextPurpose.MANAGER_QA,
        entity_type="escalation",
        entity_id=escalation_id,
        transcript_mode=mode,
        activity_at=getattr(messages[-1], "created_at", None),
        summary_text=summary_text,
        focus_after=escalation.created_at,
        escalation_context=escalation_context,
    )
    if context.insufficient_evidence:
        return _insufficient_manager_evaluation(), metrics

    user_prompt = (
        f"Evaluate the manager's conversation after the escalation.\n\n{context.prompt}"
    )

    logger.info(
        "Evaluating manager for escalation %s (%d post-escalation messages)",
        escalation_id,
        len(messages),
    )

    # Call LLM judge
    run_result = await run_agent_with_safety(
        manager_judge_agent,
        PATH_QUALITY_MANAGER,
        user_prompt,
        model_name=selected_model,
        model=OpenAIChatModel(
            selected_model,
            provider=_provider,
            settings=model_settings_for_path(
                PATH_QUALITY_MANAGER,
                model_name=selected_model,
            ),
        ),
        cache_telemetry_enabled=cache_telemetry_enabled,
    )
    evaluation = run_result.output

    # Defense-in-depth: recompute score/rating deterministically
    computed_total = float(sum(c.score for c in evaluation.criteria))
    computed_rating = compute_manager_rating(computed_total)
    if evaluation.total_score != computed_total or evaluation.rating != computed_rating:
        evaluation = evaluation.model_copy(
            update={"total_score": computed_total, "rating": computed_rating}
        )

    attach_llm_usage_telemetry(
        evaluation,
        extract_llm_usage_telemetry(
            path=PATH_QUALITY_MANAGER,
            model_name=selected_model,
            result=run_result,
        ),
    )
    return evaluation, metrics


async def save_manager_review(
    db: AsyncSession,
    escalation_id: UUID,
    conversation_id: UUID,
    evaluation: ManagerEvaluationResult,
    metrics: ManagerMetrics,
    manager_name: str | None = None,
) -> ManagerReview:
    """Save a manager evaluation result to the database.

    Args:
        db: Async SQLAlchemy session.
        escalation_id: UUID of the evaluated escalation.
        conversation_id: UUID of the conversation.
        evaluation: LLM evaluation result.
        metrics: Quantitative metrics.
        manager_name: Name of the manager (from escalation.assigned_to).

    Returns:
        Persisted ManagerReview ORM object.
    """
    criteria_data: list[dict[str, Any]] = [
        {
            "rule_number": c.rule_number,
            "rule_name": c.rule_name,
            "score": c.score,
            "max_score": 2,
            "comment": c.comment,
        }
        for c in evaluation.criteria
    ]

    computed_total = float(sum(c.score for c in evaluation.criteria))
    rating_str = compute_manager_rating(computed_total)

    review = ManagerReview(
        escalation_id=escalation_id,
        conversation_id=conversation_id,
        manager_name=manager_name,
        total_score=computed_total,
        max_score=20,
        rating=rating_str,
        criteria=criteria_data,
        summary=evaluation.summary,
        first_response_time_seconds=metrics.first_response_time_seconds,
        message_count=metrics.message_count,
        deal_converted=metrics.deal_converted,
        deal_amount=metrics.deal_amount,
        reviewer="ai",
    )
    db.add(review)
    await db.flush()
    return review


async def escalation_already_reviewed(
    db: AsyncSession,
    escalation_id: UUID,
) -> bool:
    """Check if an escalation already has a manager review."""
    stmt = (
        select(func.count())
        .select_from(ManagerReview)
        .where(ManagerReview.escalation_id == escalation_id)
    )
    result = await db.execute(stmt)
    count = result.scalar_one()
    return count > 0


async def get_unreviewed_resolved_escalations(
    db: AsyncSession,
    limit: int = 50,
) -> list[UUID]:
    """Find resolved escalations that have not been reviewed yet.

    An escalation is eligible for review if:
    - status == 'resolved'
    - No entry in manager_reviews for this escalation_id
    """
    from sqlalchemy import exists as sa_exists

    stmt = (
        select(Escalation.id)
        .where(
            Escalation.status == "resolved",
            ~sa_exists().where(ManagerReview.escalation_id == Escalation.id),
        )
        .order_by(Escalation.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
