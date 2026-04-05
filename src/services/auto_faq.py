"""Auto-FAQ service — saves adapted manager responses as new FAQ entries.

All FAQ entries are normalized to English before saving to ensure
consistent deduplication and retrieval across languages.

Handles deduplication via cosine similarity (threshold 0.92) to avoid
storing near-duplicate answers in the knowledge base.
"""

from __future__ import annotations

import asyncio
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
from src.models.knowledge_base import KnowledgeBase
from src.rag.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)

# Entries with cosine similarity above this threshold are considered duplicates
DUPLICATE_THRESHOLD = 0.92
AutoFAQSaveStatus = Literal["saved", "duplicate", "blocked_context_specific"]

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

_TRANSLATE_SYSTEM_PROMPT = """\
You are a precise translator for a knowledge base.
Translate the given Q&A pair into clear, professional English.
Preserve ALL factual content (numbers, dates, prices, product names, SKUs).
Return ONLY the translated text in the exact same "Q: ...\nA: ..." format.
If the text is already in English, return it unchanged."""

_translate_model = OpenAIChatModel(
    settings.openrouter_model_fast,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

_translate_agent: Agent[None, str] = Agent(
    model=_translate_model,
    system_prompt=_TRANSLATE_SYSTEM_PROMPT,
)


@dataclass(frozen=True)
class AutoFAQSaveResult:
    status: AutoFAQSaveStatus
    entry: KnowledgeBase | None = None
    guard_reasons: tuple[str, ...] = ()


async def _normalize_to_english(question: str, answer: str) -> tuple[str, str]:
    """Translate a Q&A pair to English using the fast LLM model.

    Returns:
        Tuple of (english_question, english_answer).
        Falls back to original text if translation fails.
    """
    try:
        content = f"Q: {question}\nA: {answer}"
        result = await asyncio.wait_for(_translate_agent.run(content), timeout=30.0)
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


async def save_to_faq(
    db: AsyncSession,
    question: str,
    adapted_answer: str,
    manager_draft: str,
    embedding_engine: EmbeddingEngine,
) -> AutoFAQSaveResult:
    """Save a manager's adapted answer as a new FAQ entry.

    The Q&A pair is normalized to English before saving to ensure
    consistent deduplication and retrieval across all languages.

    Args:
        db: Async database session.
        question: The original customer question (any language).
        adapted_answer: The polished answer (any language).
        manager_draft: The raw draft from the manager.
        embedding_engine: Engine for generating embeddings.

    Returns:
        Structured result describing whether the entry was saved, skipped as a
        duplicate, or blocked as context-specific private-only knowledge.
    """
    # 1. Normalize Q&A to English for consistent storage
    en_question, en_answer = await _normalize_to_english(question, adapted_answer)
    content_text = f"Q: {en_question}\nA: {en_answer}"

    logger.info("Normalized FAQ to English: %r -> %r", question[:60], en_question[:60])

    guard_reasons = _detect_context_specific_reasons(
        adapted_answer,
        manager_draft,
        en_answer,
    )
    if guard_reasons:
        logger.info(
            "Blocking auto-FAQ global save for context-specific answer: reasons=%s",
            ",".join(guard_reasons),
        )
        return AutoFAQSaveResult(
            status="blocked_context_specific",
            guard_reasons=guard_reasons,
        )

    # 2. Generate embedding for the English content
    embedding = await embedding_engine.embed_async(content_text)

    # 3. Check for duplicates: find the most similar existing KB entry
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

    if nearest is not None:
        distance = nearest.distance
        similarity = 1 - (distance or 0)
        if similarity > DUPLICATE_THRESHOLD:
            logger.info(
                "Duplicate FAQ detected (similarity=%.3f > %.2f). Skipping.",
                similarity,
                DUPLICATE_THRESHOLD,
            )
            return AutoFAQSaveResult(status="duplicate")

    # 4. Create new KB entry (always in English)
    title = en_question[:200]
    kb_entry = KnowledgeBase(
        source="auto_faq",
        category="faq",
        title=title,
        content=content_text,
        language="en",
        embedding=embedding,
        is_auto_generated=True,
        original_question=question,
        manager_draft=manager_draft,
    )
    db.add(kb_entry)
    await db.commit()
    await db.refresh(kb_entry)

    logger.info("Auto-FAQ entry created: title=%r, id=%s", title[:50], kb_entry.id)
    return AutoFAQSaveResult(status="saved", entry=kb_entry)
