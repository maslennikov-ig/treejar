"""Extended unit tests for EmbeddingEngine and generate_product_embeddings
covering commit-count assertions (TCG-04) and singleton state isolation
(TCG-08)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.embeddings import EmbeddingEngine, generate_product_embeddings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockProduct:
    """Minimal Product stand-in that mirrors the attributes accessed by
    generate_product_embeddings."""

    def __init__(self, name: str, category: str, desc: str) -> None:
        self.name_en = name
        self.category = category
        self.description_en = desc
        self.embedding: list[float] | None = None


# ---------------------------------------------------------------------------
# TCG-04: commit called exactly once per batch
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_product_embeddings_commits_once_for_single_batch() -> None:
    """With 2 products and the default batch_size=32, there is only 1 batch,
    so db.commit must be called exactly once."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    products = [
        _MockProduct("Table", "Furniture", "Solid oak table"),
        _MockProduct("Chair", "Furniture", "Ergonomic office chair"),
    ]

    mock_result.scalars.return_value.all.return_value = products
    mock_db.execute.return_value = mock_result

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.embed_batch_async = AsyncMock(
            return_value=[[0.1] * 1024, [0.2] * 1024]
        )

        processed = await generate_product_embeddings(mock_db)

    assert processed == 2
    assert mock_db.commit.call_count == 1, (
        f"Expected exactly 1 commit for 1 batch, got {mock_db.commit.call_count}"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_product_embeddings_commits_once_per_batch_multiple_batches() -> None:
    """With 65 products and batch_size=32, there are 3 batches (32+32+1),
    so db.commit must be called exactly 3 times."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    products = [_MockProduct(f"Product {i}", "Cat", "Desc") for i in range(65)]
    mock_result.scalars.return_value.all.return_value = products
    mock_db.execute.return_value = mock_result

    # The batches are of size 32, 32, 1.  embed_batch_async is called 3 times.
    def _embed_side_effect(texts: list[str]) -> list[list[float]]:
        return [[0.5] * 1024 for _ in texts]

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.embed_batch_async = AsyncMock(side_effect=_embed_side_effect)

        processed = await generate_product_embeddings(mock_db)

    assert processed == 65
    assert mock_db.commit.call_count == 3, (
        f"Expected 3 commits for 3 batches, got {mock_db.commit.call_count}"
    )


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_product_embeddings_returns_zero_when_no_products() -> None:
    """If there are no products without embeddings, the function returns 0
    and never calls commit."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    with patch("src.rag.embeddings.EmbeddingEngine"):
        processed = await generate_product_embeddings(mock_db)

    assert processed == 0
    mock_db.commit.assert_not_called()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_product_embeddings_assigns_embeddings_to_products() -> None:
    """Embeddings returned from the engine must be stored on the product objects."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    product_a = _MockProduct("Desk", "Furniture", "Standing desk")
    product_b = _MockProduct("Lamp", "Lighting", "LED desk lamp")

    mock_result.scalars.return_value.all.return_value = [product_a, product_b]
    mock_db.execute.return_value = mock_result

    embedding_a = [0.11] * 1024
    embedding_b = [0.22] * 1024

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.embed_batch_async = AsyncMock(return_value=[embedding_a, embedding_b])

        await generate_product_embeddings(mock_db)

    assert product_a.embedding == embedding_a
    assert product_b.embedding == embedding_b


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_product_embeddings_formats_text_correctly() -> None:
    """The text fed to the embedding engine must follow 'name | cat | desc'."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    product = _MockProduct("Oak Table", "Furniture", "Solid and durable")
    mock_result.scalars.return_value.all.return_value = [product]
    mock_db.execute.return_value = mock_result

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.embed_batch_async = AsyncMock(return_value=[[0.1] * 1024])

        await generate_product_embeddings(mock_db)

        called_texts = mock_instance.embed_batch_async.call_args[0][0]

    assert called_texts == ["Oak Table | Furniture | Solid and durable"]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_generate_product_embeddings_handles_none_category_and_desc() -> None:
    """Products with None category or description must not raise; empty string
    is used as fallback."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    product = _MockProduct("Shelf", None, None)  # type: ignore[arg-type]
    mock_result.scalars.return_value.all.return_value = [product]
    mock_db.execute.return_value = mock_result

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_instance = MockEngine.return_value
        mock_instance.embed_batch_async = AsyncMock(return_value=[[0.1] * 1024])

        processed = await generate_product_embeddings(mock_db)

        called_texts = mock_instance.embed_batch_async.call_args[0][0]

    assert processed == 1
    # None becomes "" in the formatted text
    assert called_texts == ["Shelf |  | "]


# ---------------------------------------------------------------------------
# TCG-08: Singleton state isolation between tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_singleton_returns_same_instance() -> None:
    """EmbeddingEngine.__new__ must always return the same object within a
    Python process when the class-level _instance is not reset."""
    # Ensure a clean slate first
    EmbeddingEngine._instance = None

    try:
        with patch("src.rag.embeddings.TextEmbedding"):
            engine_a = EmbeddingEngine()
            engine_b = EmbeddingEngine()
            assert engine_a is engine_b
    finally:
        EmbeddingEngine._instance = None


@pytest.mark.unit
def test_singleton_reset_between_tests() -> None:
    """Resetting _instance at class level allows a fresh singleton to be
    created.  This verifies the reset pattern used by test fixtures."""
    EmbeddingEngine._instance = None

    with patch("src.rag.embeddings.TextEmbedding"):
        first = EmbeddingEngine()

    EmbeddingEngine._instance = None

    with patch("src.rag.embeddings.TextEmbedding"):
        second = EmbeddingEngine()

    # After the reset, a new object is created
    assert first is not second
    EmbeddingEngine._instance = None


@pytest.mark.unit
def test_singleton_class_level_patch_works() -> None:
    """Patching TextEmbedding at the class level prevents any real model
    loading when EmbeddingEngine._get_model is called."""
    EmbeddingEngine._instance = None

    try:
        with patch("src.rag.embeddings.TextEmbedding") as MockTextEmbedding:
            mock_model = MagicMock()

            def _fake_embed(texts: list[str]):  # type: ignore[no-untyped-def]
                class _FakeArray:
                    def __iter__(self):  # type: ignore[no-untyped-def]
                        return iter([0.42] * 1024)

                    def tolist(self) -> list[float]:
                        return [0.42] * 1024

                for _ in texts:
                    yield _FakeArray()

            mock_model.embed.side_effect = _fake_embed
            MockTextEmbedding.return_value = mock_model

            engine = EmbeddingEngine()
            result = engine.embed("test sentence")

        assert len(result) == 1024
        assert result[0] == 0.42
        MockTextEmbedding.assert_called_once()
    finally:
        EmbeddingEngine._instance = None


@pytest.mark.unit
def test_singleton_model_not_loaded_until_embed_called() -> None:
    """_get_model is lazy: the TextEmbedding constructor must not be called
    until embed() or embed_batch() is invoked."""
    EmbeddingEngine._instance = None
    EmbeddingEngine._model = None

    try:
        with patch("src.rag.embeddings.TextEmbedding") as MockTextEmbedding:
            MockTextEmbedding.return_value = MagicMock()
            _engine = EmbeddingEngine()
            # Model not yet loaded
            MockTextEmbedding.assert_not_called()
    finally:
        EmbeddingEngine._instance = None
        EmbeddingEngine._model = None
