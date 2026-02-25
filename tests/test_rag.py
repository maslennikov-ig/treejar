from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.rag.pipeline import search_knowledge, search_products
from src.schemas.product import ProductSearchQuery


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_products_pipeline():
    """Test RAG pipeline for products with filters and vector sorting."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()

    # Mocking a SQLAlchemy product object
    class MockProduct:
        def __init__(self, id, sku, name, category, price, stock):
            self.id = id
            self.sku = sku
            self.name_en = name
            self.name_ar = None
            self.description_en = None
            self.category = category
            self.subcategory = None
            self.price = price
            self.currency = "AED"
            self.stock = stock
            self.image_url = None
            self.attributes = {}
            self.is_active = True
            # Needed for Pydantic from_attributes
            from datetime import UTC, datetime
            self.created_at = datetime.now(UTC)
            self.updated_at = datetime.now(UTC)

    import uuid
    mock_products = [
        MockProduct(str(uuid.uuid4()), "SKU1", "Table", "Furniture", 100.0, 10),
    ]

    mock_result.scalars.return_value.all.return_value = mock_products
    mock_db.execute.return_value = mock_result

    mock_embedding_engine = MagicMock()
    mock_embedding_engine.embed.return_value = [0.1] * 1024

    query = ProductSearchQuery(
        query="wood table",
        category="Furniture",
        min_price=50.0,
        max_price=200.0,
        in_stock_only=True,
        limit=5
    )

    result = await search_products(mock_db, query, mock_embedding_engine)

    # Assert query was executed
    assert mock_db.execute.called
    mock_embedding_engine.embed.assert_called_with("wood table")

    # Assert result structure matches expected ProductSearchResult
    assert result.total_found == 1
    assert result.products[0].sku == "SKU1"
    assert result.products[0].price == 100.0


@pytest.mark.asyncio
@pytest.mark.unit
async def test_search_knowledge_pipeline():
    """Test RAG pipeline for knowledge base retrieval."""
    mock_db = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()

    class MockKB:
        def __init__(self, id, source, category, title, content):
            self.id = id
            self.source = source
            self.category = category
            self.title = title
            self.content = content

    mock_records = [
        MockKB("1", "faq", "faq", "Test Q", "Test A")
    ]

    mock_result.scalars.return_value.all.return_value = mock_records
    mock_db.execute.return_value = mock_result

    mock_embedding_engine = MagicMock()
    mock_embedding_engine.embed.return_value = [0.1] * 1024

    result = await search_knowledge(mock_db, "test question", mock_embedding_engine, limit=3)

    assert mock_db.execute.called
    assert len(result) == 1
    assert result[0]["title"] == "Test Q"
    assert result[0]["category"] == "faq"
