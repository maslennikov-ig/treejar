from __future__ import annotations

from typing import Any, Protocol


class VectorStore(Protocol):
    """Abstract vector store interface.

    Implement this protocol to swap vector backends
    (pgvector, Qdrant, Pinecone, etc.)
    """

    async def search(
        self,
        query_embedding: list[float],
        limit: int = 5,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search for similar vectors with optional filters."""
        ...

    async def upsert(
        self,
        id: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> None:
        """Insert or update a vector with metadata."""
        ...
