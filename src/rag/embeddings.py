from __future__ import annotations

import logging

from fastembed import TextEmbedding
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.knowledge_base import KnowledgeBase
from src.models.product import Product

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Singleton engine for generating embeddings using BAAI/bge-m3."""

    _instance: EmbeddingEngine | None = None
    _model: TextEmbedding | None = None

    def __new__(cls) -> EmbeddingEngine:
        """Ensure singleton pattern to avoid loading the model multiple times."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    def _get_model(self) -> TextEmbedding:
        """Lazy load the embedding model."""
        if self._model is None:
            logger.info(f"Loading embedding model {settings.embedding_model}...")
            self._model = TextEmbedding(model_name=settings.embedding_model)
            logger.info("Embedding model loaded successfully.")
        return self._model

    def embed(self, text: str) -> list[float]:
        """Generate an embedding for a single text string."""
        model = self._get_model()
        # model.embed returns a generator of numpy arrays
        generator = model.embed([text])
        for result in generator:
            return list(float(x) for x in result)
        return []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of text strings."""
        model = self._get_model()
        generator = model.embed(texts)
        # Convert generator of numpy arrays to list of lists of floats
        return [vec.tolist() for vec in generator]


async def generate_product_embeddings(db: AsyncSession) -> int:
    """Generate embeddings for all active products that lack them.
    
    Returns:
        The number of products processed.
    """
    engine = EmbeddingEngine()

    # Fetch active products without embeddings
    stmt = select(Product).where(
        Product.embedding.is_(None),
        Product.is_active.is_(True)
    )
    result = await db.execute(stmt)
    products = result.scalars().all()

    if not products:
        return 0

    logger.info(f"Generating embeddings for {len(products)} products...")

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

        # Generate embeddings synchronously
        # For production with many products, this might block the event loop,
        # so consider asyncio.to_thread if necessary.
        # But fastembed is generally fast for small batches (32).
        embeddings = engine.embed_batch(texts)

        # Update products
        for product, embedding in zip(batch, embeddings):
            product.embedding = embedding

        processed_count += len(batch)

        # Commit each batch
        await db.commit()
        logger.info(f"Processed batch of size {len(batch)}. Total: {processed_count}")

    return processed_count


async def index_knowledge_base(db: AsyncSession) -> int:
    """Generate embeddings for all knowledge base records that lack them.
    
    Returns:
        The number of knowledge base records processed.
    """
    engine = EmbeddingEngine()

    stmt = select(KnowledgeBase).where(KnowledgeBase.embedding.is_(None))
    result = await db.execute(stmt)
    records = result.scalars().all()

    if not records:
        return 0

    logger.info(f"Generating embeddings for {len(records)} knowledge base records...")

    batch_size = 32
    processed_count = 0

    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]

        texts = [r.content for r in batch]
        embeddings = engine.embed_batch(texts)

        for record, embedding in zip(batch, embeddings):
            record.embedding = embedding

        processed_count += len(batch)

        await db.commit()

    return processed_count
