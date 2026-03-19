"""Auto-FAQ service — saves adapted manager responses as new FAQ entries.

Handles deduplication via cosine similarity (threshold 0.92) to avoid
storing near-duplicate answers in the knowledge base.
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.knowledge_base import KnowledgeBase
from src.rag.embeddings import EmbeddingEngine

logger = logging.getLogger(__name__)

# Entries with cosine similarity above this threshold are considered duplicates
DUPLICATE_THRESHOLD = 0.92


async def save_to_faq(
    db: AsyncSession,
    question: str,
    adapted_answer: str,
    manager_draft: str,
    embedding_engine: EmbeddingEngine,
) -> KnowledgeBase | None:
    """Save a manager's adapted answer as a new FAQ entry.

    Args:
        db: Async database session.
        question: The original customer question.
        adapted_answer: The polished answer (after response_adapter).
        manager_draft: The raw draft from the manager.
        embedding_engine: Engine for generating embeddings.

    Returns:
        The created KnowledgeBase entry, or None if a duplicate was found.
    """
    # 1. Generate embedding for the adapted answer
    content_text = f"Q: {question}\nA: {adapted_answer}"
    embedding = await embedding_engine.embed_async(content_text)

    # 2. Check for duplicates: find the most similar existing KB entry
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

    # 3. Create new KB entry
    title = question[:200]
    kb_entry = KnowledgeBase(
        source="auto_faq",
        category="faq",
        title=title,
        content=content_text,
        language="auto",
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
