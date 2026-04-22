"""Auto-FAQ service — saves adapted manager responses as new FAQ entries.

All FAQ entries are normalized to English before saving to ensure
consistent deduplication and retrieval across languages.

Handles deduplication via cosine similarity (threshold 0.92) to avoid
storing near-duplicate answers in the knowledge base.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.llm.safety import (
    PATH_AUTO_FAQ_TRANSLATE,
    model_name_for_path,
    model_settings_for_path,
    run_agent_with_safety,
)
from src.models.knowledge_base import KnowledgeBase
from src.rag.embeddings import EmbeddingEngine
from src.services.auto_faq_types import AutoFAQCandidate

logger = logging.getLogger(__name__)
AUTO_FAQ_TRANSLATE_MODEL_NAME = model_name_for_path(PATH_AUTO_FAQ_TRANSLATE)

# Entries with cosine similarity above this threshold are considered duplicates
DUPLICATE_THRESHOLD = 0.92
CONFIDENCE_THRESHOLD = 0.75
AutoFAQSaveStatus = Literal[
    "needs_confirmation",
    "saved",
    "duplicate",
    "blocked_context_specific",
    "blocked_unsafe",
    "low_confidence",
    "missing_candidate",
]

_TIME_SPECIFIC_PROMISE_RE = re.compile(
    r"\b(?:today|tomorrow|tonight|this week|next week|this month|next month|"
    r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2})\b",
    re.IGNORECASE,
)
_PROJECT_SPECIFIC_LOGISTICS_RE = re.compile(
    r"\b(?:deliver(?:y)? to|install(?:ation)? at|ship to|site visit|"
    r"dubai marina|tower|floor|loading bay|gate pass|warehouse)\b",
    re.IGNORECASE,
)
_ONE_OFF_OFFER_RE = re.compile(
    r"\b(?:discount|special offer|special price|promo|promotion|"
    r"complimentary|free delivery|best price|better price|waive(?:d)?)\b",
    re.IGNORECASE,
)
_CUSTOMER_SPECIFIC_COMMITMENT_RE = re.compile(
    r"\b(?:for this order|for your order|for your project|for your company|"
    r"for your office|for you|case by case|custom arrangement|exception)\b",
    re.IGNORECASE,
)
_CALLBACK_COMMITMENT_RE = re.compile(
    r"\b(?:call you|contact you|message you|reach out|get back to you|"
    r"will call|will contact|our manager|sales manager)\b",
    re.IGNORECASE,
)
_ABSOLUTE_CLAIM_RE = re.compile(
    r"\b(?:always|never|guarantee(?:d)?|no questions asked|risk[- ]free|"
    r"100%\s*(?:guarantee|refund|free))\b",
    re.IGNORECASE,
)
_SENSITIVE_OR_REGULATED_RE = re.compile(
    r"\b(?:medical advice|legal advice|diagnos(?:e|is)|prescription|"
    r"password|credit card|bank account|iban|wire transfer|crypto(?:currency)?)\b",
    re.IGNORECASE,
)

_TRANSLATE_SYSTEM_PROMPT = """\
You are a precise translator for a knowledge base.
Translate the given Q&A pair into clear, professional English.
Preserve ALL factual content (numbers, dates, prices, product names, SKUs).
Return ONLY the translated text in the exact same "Q: ...\nA: ..." format.
If the text is already in English, return it unchanged."""

_translate_model = OpenAIChatModel(
    AUTO_FAQ_TRANSLATE_MODEL_NAME,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    settings=model_settings_for_path(
        PATH_AUTO_FAQ_TRANSLATE,
        model_name=AUTO_FAQ_TRANSLATE_MODEL_NAME,
    ),
)

_translate_agent: Agent[None, str] = Agent(
    model=_translate_model,
    system_prompt=_TRANSLATE_SYSTEM_PROMPT,
    retries=0,
    model_settings=model_settings_for_path(
        PATH_AUTO_FAQ_TRANSLATE,
        model_name=AUTO_FAQ_TRANSLATE_MODEL_NAME,
    ),
)


@dataclass(frozen=True)
class AutoFAQSaveResult:
    status: AutoFAQSaveStatus
    candidate: AutoFAQCandidate | None = None
    entry: KnowledgeBase | None = None
    guard_reasons: tuple[str, ...] = ()
    duplicate_similarity: float | None = None


@dataclass(frozen=True)
class _CandidatePostCheckResult:
    status: AutoFAQSaveStatus
    guard_reasons: tuple[str, ...] = ()
    duplicate_similarity: float | None = None
    embedding: list[float] | None = None


async def _normalize_to_english(question: str, answer: str) -> tuple[str, str]:
    """Translate a Q&A pair to English using the fast LLM model.

    Returns:
        Tuple of (english_question, english_answer).
        Falls back to original text if translation fails.
    """
    try:
        content = f"Q: {question}\nA: {answer}"
        result = await run_agent_with_safety(
            _translate_agent,
            PATH_AUTO_FAQ_TRANSLATE,
            content,
            model_name=AUTO_FAQ_TRANSLATE_MODEL_NAME,
        )
        translated = result.output.strip()

        # Parse back into Q and A
        if "\nA:" in translated:
            parts = translated.split("\nA:", 1)
            q = parts[0].removeprefix("Q:").strip()
            a = parts[1].strip()
            return q, a

        # Fallback: return original if parsing fails
        logger.warning("Failed to parse translated FAQ, using original text")
        return question, answer
    except Exception:
        logger.exception("LLM translation failed, saving FAQ in original language")
        return question, answer


def _detect_context_specific_reasons(*texts: str) -> tuple[str, ...]:
    combined = "\n".join(text for text in texts if text)
    reasons: list[str] = []

    if _TIME_SPECIFIC_PROMISE_RE.search(combined):
        reasons.append("time_specific_promise")
    if _PROJECT_SPECIFIC_LOGISTICS_RE.search(combined):
        reasons.append("project_specific_logistics")
    if _ONE_OFF_OFFER_RE.search(combined):
        reasons.append("one_off_offer")
    if _CUSTOMER_SPECIFIC_COMMITMENT_RE.search(combined):
        reasons.append("customer_specific_commitment")
    if _CALLBACK_COMMITMENT_RE.search(combined):
        reasons.append("callback_commitment")

    return tuple(reasons)


def _detect_unsafe_reasons(*texts: str) -> tuple[str, ...]:
    combined = "\n".join(text for text in texts if text)
    reasons: list[str] = []

    if _ABSOLUTE_CLAIM_RE.search(combined):
        reasons.append("absolute_claim")
    if _SENSITIVE_OR_REGULATED_RE.search(combined):
        reasons.append("sensitive_or_regulated")

    return tuple(reasons)


def _candidate_content(candidate: AutoFAQCandidate) -> str:
    return f"Q: {candidate.question}\nA: {candidate.answer}"


async def _nearest_duplicate_similarity(
    db: AsyncSession,
    embedding: list[float],
) -> float | None:
    stmt = (
        select(
            KnowledgeBase.id,
            KnowledgeBase.embedding.cosine_distance(embedding).label("distance"),
        )
        .where(KnowledgeBase.embedding.is_not(None))
        .order_by("distance")
        .limit(1)
    )
    result = await db.execute(stmt)
    nearest = result.first()
    if nearest is None:
        return None

    distance = nearest.distance
    return 1 - (distance or 0)


async def _run_candidate_post_checks(
    db: AsyncSession,
    candidate: AutoFAQCandidate | None,
    *,
    manager_draft: str,
    customer_message: str,
    embedding_engine: EmbeddingEngine,
) -> _CandidatePostCheckResult:
    if candidate is None:
        return _CandidatePostCheckResult(
            status="missing_candidate",
            guard_reasons=("missing_candidate",),
        )

    if candidate.confidence < CONFIDENCE_THRESHOLD:
        return _CandidatePostCheckResult(
            status="low_confidence",
            guard_reasons=("low_confidence",),
        )

    unsafe_reasons = _detect_unsafe_reasons(
        candidate.question,
        candidate.answer,
        customer_message,
        manager_draft,
    )
    if unsafe_reasons:
        return _CandidatePostCheckResult(
            status="blocked_unsafe",
            guard_reasons=unsafe_reasons,
        )

    context_reasons = _detect_context_specific_reasons(
        candidate.question,
        candidate.answer,
        customer_message,
        manager_draft,
    )
    if context_reasons:
        logger.info(
            "Blocking auto-FAQ global save for context-specific answer: reasons=%s",
            ",".join(context_reasons),
        )
        return _CandidatePostCheckResult(
            status="blocked_context_specific",
            guard_reasons=context_reasons,
        )

    content_text = _candidate_content(candidate)
    embedding = await embedding_engine.embed_async(content_text)
    duplicate_similarity = await _nearest_duplicate_similarity(db, embedding)

    if duplicate_similarity is not None and duplicate_similarity >= DUPLICATE_THRESHOLD:
        logger.info(
            "Duplicate FAQ detected (similarity=%.3f >= %.2f). Skipping.",
            duplicate_similarity,
            DUPLICATE_THRESHOLD,
        )
        return _CandidatePostCheckResult(
            status="duplicate",
            duplicate_similarity=duplicate_similarity,
        )

    return _CandidatePostCheckResult(
        status="needs_confirmation",
        duplicate_similarity=duplicate_similarity,
        embedding=embedding,
    )


async def review_auto_faq_candidate(
    db: AsyncSession,
    candidate: AutoFAQCandidate | None,
    *,
    manager_draft: str,
    customer_message: str,
    embedding_engine: EmbeddingEngine,
) -> AutoFAQSaveResult:
    """Run deterministic checks and return a candidate for admin confirmation.

    This never saves to the knowledge base. A passing candidate returns
    ``needs_confirmation`` so an admin must explicitly approve persistence.
    """
    checks = await _run_candidate_post_checks(
        db,
        candidate,
        manager_draft=manager_draft,
        customer_message=customer_message,
        embedding_engine=embedding_engine,
    )
    return AutoFAQSaveResult(
        status=checks.status,
        candidate=candidate,
        guard_reasons=checks.guard_reasons,
        duplicate_similarity=checks.duplicate_similarity,
    )


async def save_confirmed_faq_candidate(
    db: AsyncSession,
    candidate: AutoFAQCandidate,
    *,
    original_question: str,
    manager_draft: str,
    customer_message: str,
    embedding_engine: EmbeddingEngine,
) -> AutoFAQSaveResult:
    """Persist a candidate after explicit admin confirmation."""
    checks = await _run_candidate_post_checks(
        db,
        candidate,
        manager_draft=manager_draft,
        customer_message=customer_message,
        embedding_engine=embedding_engine,
    )
    if checks.status != "needs_confirmation":
        return AutoFAQSaveResult(
            status=checks.status,
            candidate=candidate,
            guard_reasons=checks.guard_reasons,
            duplicate_similarity=checks.duplicate_similarity,
        )

    content_text = _candidate_content(candidate)
    title = candidate.question[:200]
    kb_entry = KnowledgeBase(
        source="auto_faq",
        category="faq",
        title=title,
        content=content_text,
        language="en",
        embedding=checks.embedding,
        is_auto_generated=True,
        original_question=original_question,
        manager_draft=manager_draft,
    )
    db.add(kb_entry)
    await db.commit()
    await db.refresh(kb_entry)

    logger.info(
        "Auto-FAQ entry created after confirmation: title=%r, id=%s",
        title[:50],
        kb_entry.id,
    )
    return AutoFAQSaveResult(status="saved", candidate=candidate, entry=kb_entry)


async def save_to_faq(
    db: AsyncSession,
    question: str,
    adapted_answer: str,
    manager_draft: str,
    embedding_engine: EmbeddingEngine,
    *,
    admin_confirmed: bool = False,
) -> AutoFAQSaveResult:
    """Review or save a manager's adapted answer as a new FAQ entry.

    The Q&A pair is normalized to English for consistent deduplication and
    retrieval across all languages. By default this function only returns a
    candidate that needs admin confirmation; pass ``admin_confirmed=True`` only
    from an explicit admin approval action.

    Args:
        db: Async database session.
        question: The original customer question (any language).
        adapted_answer: The polished answer (any language).
        manager_draft: The raw draft from the manager.
        embedding_engine: Engine for generating embeddings.
        admin_confirmed: Whether an admin explicitly approved saving.

    Returns:
        Structured result describing whether the candidate needs confirmation,
        was saved, or was rejected by deterministic post-checks.
    """
    en_question, en_answer = await _normalize_to_english(question, adapted_answer)
    candidate = AutoFAQCandidate(
        question=en_question,
        answer=en_answer,
        confidence=1.0,
        language="en",
    )
    logger.info("Normalized FAQ to English: %r -> %r", question[:60], en_question[:60])

    if not admin_confirmed:
        return await review_auto_faq_candidate(
            db,
            candidate,
            manager_draft=manager_draft,
            customer_message=adapted_answer,
            embedding_engine=embedding_engine,
        )

    return await save_confirmed_faq_candidate(
        db,
        candidate,
        original_question=question,
        manager_draft=manager_draft,
        customer_message=adapted_answer,
        embedding_engine=embedding_engine,
    )
