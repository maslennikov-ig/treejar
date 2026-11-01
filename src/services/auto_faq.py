"""Auto-FAQ service — reviews adapted manager responses as FAQ candidates.

Handles deterministic safety/context checks and deduplication via cosine
similarity (threshold 0.92) against active knowledge base entries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_base import KnowledgeBase
from src.models.knowledge_base_candidate import KnowledgeBaseCandidate
from src.rag.embeddings import EmbeddingEngine
from src.services.auto_faq_types import AutoFAQCandidate

logger = logging.getLogger(__name__)

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
        .where(
            KnowledgeBase.deleted_at.is_(None),
            KnowledgeBase.embedding.is_not(None),
        )
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
    persist_candidate: bool = False,
    source_metadata: dict[str, Any] | None = None,
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
    result = AutoFAQSaveResult(
        status=checks.status,
        candidate=candidate,
        guard_reasons=checks.guard_reasons,
        duplicate_similarity=checks.duplicate_similarity,
    )
    if persist_candidate and candidate is not None:
        db.add(
            KnowledgeBaseCandidate(
                question=candidate.question,
                answer=candidate.answer,
                language=candidate.language,
                confidence=candidate.confidence,
                status=checks.status,
                guard_reasons=list(checks.guard_reasons),
                duplicate_similarity=checks.duplicate_similarity,
                original_question=candidate.question,
                manager_draft=manager_draft,
                customer_message=customer_message,
                metadata_=source_metadata,
            )
        )
        await db.commit()
    return result
