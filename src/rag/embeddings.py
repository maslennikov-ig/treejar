from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.knowledge_base import KnowledgeBase
from src.models.product import Product

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer as SentenceTransformerType
else:
    SentenceTransformerType = Any

# Kept as a module attribute so patch("src.rag.embeddings.SentenceTransformer")
# continues to work without importing torch / sentence_transformers on module load.
SentenceTransformer: Any = None

EMBEDDING_CACHE_MAX_ENTRIES = 128
EMBEDDING_CACHE_TTL_SECONDS = 60.0

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Singleton engine for generating text embeddings."""

    _instance: EmbeddingEngine | None = None
    _model: SentenceTransformerType | None = None
    _lock: threading.Lock = threading.Lock()
    _cache: OrderedDict[tuple[str, str], tuple[tuple[float, ...], float]]
    _cache_lock: threading.Lock

    def __new__(cls) -> EmbeddingEngine:
        """Ensure singleton pattern to avoid loading the model multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
            cls._instance._cache = OrderedDict()
            cls._instance._cache_lock = threading.Lock()
        return cls._instance

    def clear_cache(self) -> None:
        """Clear the bounded in-memory query embedding cache."""
        with self._cache_lock:
            self._cache.clear()

    def _get_cached_embedding(self, key: tuple[str, str]) -> list[float] | None:
        now = time.monotonic()
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            vec_tuple, expires_at = entry
            if now >= expires_at:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return list(vec_tuple)

    def _store_cached_embedding(
        self,
        key: tuple[str, str],
        vector: list[float],
    ) -> None:
        vec_tuple = tuple(vector)
        expires_at = time.monotonic() + EMBEDDING_CACHE_TTL_SECONDS
        with self._cache_lock:
            self._cache[key] = (vec_tuple, expires_at)
            self._cache.move_to_end(key)
            while len(self._cache) > EMBEDDING_CACHE_MAX_ENTRIES:
                self._cache.popitem(last=False)

    def _get_model(self) -> SentenceTransformerType:
        """Lazy load the embedding model with double-checked locking."""
        if self._model is None:
            with self._lock:
                if self._model is None:
                    logger.info(
                        "Loading embedding model %s...", settings.embedding_model
                    )
                    st_cls = SentenceTransformer
                    if st_cls is None:
                        from sentence_transformers import (
                            SentenceTransformer as _SentenceTransformer,
                        )

                        st_cls = _SentenceTransformer
                    self._model = st_cls(settings.embedding_model)
                    logger.info("Embedding model loaded successfully.")
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text string."""
        cache_key = (settings.embedding_model, text)
        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached
        model = self._get_model()
        embedding = model.encode(text, normalize_embeddings=True)
        vector: list[float] = embedding.tolist()
        self._store_cached_embedding(cache_key, vector)
        return list(vector)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of text strings."""
        model = self._get_model()
        embeddings = model.encode(texts, normalize_embeddings=True)
        return [e.tolist() for e in embeddings]

    async def embed_async(self, text: str) -> list[float]:
        """Generate an embedding for a single text string without blocking the event loop."""
        cache_key = (settings.embedding_model, text)
        cached = self._get_cached_embedding(cache_key)
        if cached is not None:
            return cached
        return await asyncio.to_thread(self.embed, text)

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of text strings without blocking the event loop."""
        return await asyncio.to_thread(self.embed_batch, texts)

    async def warmup_async(self) -> None:
        """Preload the embedding model without blocking the event loop."""
        await asyncio.to_thread(self._get_model)


async def generate_product_embeddings(db: AsyncSession) -> int:
    """Generate embeddings for all active products that lack them.

    Returns:
        The number of products processed.
    """
    engine = EmbeddingEngine()

    # Fetch active products without embeddings
    stmt = select(Product).where(
        Product.embedding.is_(None), Product.is_active.is_(True)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    if not products:
        return 0

    logger.info("Generating embeddings for %d products...", len(products))

    # Process in batches to avoid high memory spikes
    batch_size = 32
    processed_count = 0

    for i in range(0, len(products), batch_size):
        batch = products[i : i + batch_size]

        # Format strings for embedding: "Name | Category | Description"
        texts = []
        for p in batch:
            cat = p.category or ""
            desc = p.description_en or ""
            text = f"{p.name_en} | {cat} | {desc}"
            texts.append(text)

        embeddings = await engine.embed_batch_async(texts)

        # Update products
        for product, embedding in zip(batch, embeddings, strict=False):
            product.embedding = embedding

        processed_count += len(batch)

        # Commit each batch
        await db.commit()
        logger.info(
            "Processed batch of size %d. Total: %d", len(batch), processed_count
        )

    return processed_count


async def index_knowledge_base(db: AsyncSession) -> int:
    """Generate embeddings for all knowledge base records that lack them.

    Returns:
        The number of knowledge base records processed.
    """
    engine = EmbeddingEngine()

    stmt = select(KnowledgeBase).where(
        KnowledgeBase.embedding.is_(None),
        KnowledgeBase.deleted_at.is_(None),
    )
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return 0

    logger.info("Generating embeddings for %d knowledge base records...", len(records))

    batch_size = 32
    processed_count = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]

        texts = [r.content for r in batch]
        embeddings = await engine.embed_batch_async(texts)

        for record, embedding in zip(batch, embeddings, strict=False):
            record.embedding = embedding

        processed_count += len(batch)

        await db.commit()

    return processed_count
