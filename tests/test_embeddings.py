from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.rag.embeddings import (
    EmbeddingEngine,
    generate_product_embeddings,
    index_knowledge_base,
)


@pytest.fixture
def mock_embedding_engine():
    with patch("src.rag.embeddings.TextEmbedding") as MockTextEmbedding:
        mock_model = MockTextEmbedding.return_value

        # Mocks the embed generator
        def mock_embed(texts):
            class MockArray:
                def __iter__(self):
                    return iter([0.1] * 1024)
                def tolist(self):
                    return [0.1] * 1024
            
            for _ in texts:
                yield MockArray()

        mock_model.embed.side_effect = mock_embed

        # Reset singleton instance before tests
        EmbeddingEngine._instance = None
        engine = EmbeddingEngine()
        yield engine
        # Reset after
        EmbeddingEngine._instance = None


@pytest.mark.unit
def test_embedding_engine_singleton(mock_embedding_engine):
    """Test that EmbeddingEngine operates as a singleton."""
    engine1 = EmbeddingEngine()
    engine2 = EmbeddingEngine()
    assert engine1 is engine2


@pytest.mark.unit
def test_embedding_embed(mock_embedding_engine):
    """Test embed single text."""
    result = mock_embedding_engine.embed("Hello world")
    assert isinstance(result, list)
    assert len(result) == 1024
    assert result[0] == 0.1


@pytest.mark.unit
def test_embedding_embed_batch(mock_embedding_engine):
    """Test embed multiple texts."""
    result = mock_embedding_engine.embed_batch(["text1", "text2"])
    assert isinstance(result, list)
    assert len(result) == 2
    assert len(result[0]) == 1024


@pytest.mark.asyncio
@pytest.mark.unit
async def test_generate_product_embeddings():
    """Test generating embeddings for active products missing them."""
    # We mock DB session and execution
    mock_db = AsyncMock()
    mock_result = MagicMock()

    class MockProduct:
        def __init__(self, name, category, desc):
            self.name_en = name
            self.category = category
            self.description_en = desc
            self.embedding = None

    products = [
        MockProduct("Table", "Furniture", "A nice table"),
        MockProduct("Chair", "Furniture", "A nice chair"),
    ]

    mock_result.scalars.return_value.all.return_value = products
    mock_db.execute.return_value = mock_result

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.embed_batch.return_value = [[0.1]*1024, [0.2]*1024]

        processed = await generate_product_embeddings(mock_db)

        assert processed == 2
        assert mock_db.commit.called
        assert products[0].embedding == [0.1] * 1024
        assert products[1].embedding == [0.2] * 1024


@pytest.mark.asyncio
@pytest.mark.unit
async def test_index_knowledge_base_embeddings():
    """Test generating embeddings for knowledge base records."""
    mock_db = AsyncMock()
    mock_result = MagicMock()

    class MockRecord:
        def __init__(self, content):
            self.content = content
            self.embedding = None

    records = [MockRecord("Content 1")]
    mock_result.scalars.return_value.all.return_value = records
    mock_db.execute.return_value = mock_result

    with patch("src.rag.embeddings.EmbeddingEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.embed_batch.return_value = [[0.5]*1024]

        processed = await index_knowledge_base(mock_db)

        assert processed == 1
        assert mock_db.commit.called
        assert records[0].embedding == [0.5] * 1024
