"""Auto-FAQ service — saves adapted manager responses as new FAQ entries.

All FAQ entries are normalized to English before saving to ensure
consistent deduplication and retrieval across languages.

Handles deduplication via cosine similarity (threshold 0.92) to avoid
storing near-duplicate answers in the knowledge base.
"""

from __future__ import annotations

import asyncio
import logging

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


async def _normalize_to_english(question: str, answer: str) -> tuple[str, str]:
    """Translate a Q&A pair to English using the fast LLM model.

    Returns:
        Tuple of (english_question, english_answer).
        Falls back to original text if translation fails.
    """
    try:
        content = f"Q: {question}\nA: {answer}"
        result = await asyncio.wait_for(
            _translate_agent.run(content), timeout=30.0
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


async def save_to_faq(
    db: AsyncSession,
    question: str,
    adapted_answer: str,
    manager_draft: str,
    embedding_engine: EmbeddingEngine,
) -> KnowledgeBase | None:
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
        The created KnowledgeBase entry, or None if a duplicate was found.
    """
    # 1. Normalize Q&A to English for consistent storage
    en_question, en_answer = await _normalize_to_english(question, adapted_answer)
    content_text = f"Q: {en_question}\nA: {en_answer}"

    logger.info(
        "Normalized FAQ to English: %r -> %r", question[:60], en_question[:60]
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
            return None

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
    return kb_entry
