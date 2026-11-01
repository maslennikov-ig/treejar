from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import TYPE_CHECKING, Any

from src.core.config import settings

if TYPE_CHECKING:
    from src.rag.embeddings import EmbeddingEngine

EMBEDDING_CACHE_MAX_ENTRIES = 128
EMBEDDING_CACHE_TTL_SECONDS = 60.0

_SHARED_CACHE: OrderedDict[tuple[int, str, str], tuple[tuple[float, ...], float]] = (
    OrderedDict()
)
_SHARED_CACHE_LOCK = threading.Lock()


def clear_embedding_cache() -> None:
    """Clear the bounded in-memory query embedding cache."""
    with _SHARED_CACHE_LOCK:
        _SHARED_CACHE.clear()


def _get_cached_embedding(key: tuple[int, str, str]) -> list[float] | None:
    now = time.monotonic()
    with _SHARED_CACHE_LOCK:
        entry = _SHARED_CACHE.get(key)
        if entry is None:
            return None
        vec_tuple, expires_at = entry
        if now >= expires_at:
            del _SHARED_CACHE[key]
            return None
        _SHARED_CACHE.move_to_end(key)
        return list(vec_tuple)


def _store_cached_embedding(key: tuple[int, str, str], vector: list[float]) -> None:
    vec_tuple = tuple(vector)
    expires_at = time.monotonic() + EMBEDDING_CACHE_TTL_SECONDS
    with _SHARED_CACHE_LOCK:
        _SHARED_CACHE[key] = (vec_tuple, expires_at)
        _SHARED_CACHE.move_to_end(key)
        while len(_SHARED_CACHE) > EMBEDDING_CACHE_MAX_ENTRIES:
            _SHARED_CACHE.popitem(last=False)


class CachedEmbeddingEngine:
    """Bounded LRU/TTL query cache wrapper around an EmbeddingEngine instance.

    Lives outside `src/rag/embeddings.py` so `PINNED_RETRIEVAL_CONTRACT_SHA`
    remains byte-for-byte intact while duplicate queries within a turn
    (e.g. `search_knowledge` + `search_behavior_rules`) reuse a defensive copy.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    @property
    def inner(self) -> Any:
        return self._inner

    def clear_cache(self) -> None:
        clear_embedding_cache()

    def _cache_key(self, text: str) -> tuple[int, str, str]:
        return (id(self._inner), settings.embedding_model, text)

    def embed(self, text: str) -> list[float]:
        key = self._cache_key(text)
        cached = _get_cached_embedding(key)
        if cached is not None:
            return cached
        vector = self._inner.embed(text)
        if isinstance(vector, list):
            _store_cached_embedding(key, vector)
            return list(vector)
        return vector  # type: ignore[no-any-return]

    async def embed_async(self, text: str) -> list[float]:
        key = self._cache_key(text)
        cached = _get_cached_embedding(key)
        if cached is not None:
            return cached
        vector = await self._inner.embed_async(text)
        if isinstance(vector, list):
            _store_cached_embedding(key, vector)
            return list(vector)
        return vector  # type: ignore[no-any-return]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return self._inner.embed_batch(texts)  # type: ignore[no-any-return]

    async def embed_batch_async(self, texts: list[str]) -> list[list[float]]:
        return await self._inner.embed_batch_async(texts)  # type: ignore[no-any-return]

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


def wrap_embedding_engine(engine: EmbeddingEngine) -> EmbeddingEngine:
    """Wrap an embedding engine with bounded query caching unless already wrapped."""
    if engine is None or isinstance(engine, CachedEmbeddingEngine):
        return engine
    return CachedEmbeddingEngine(engine)  # type: ignore[return-value]
