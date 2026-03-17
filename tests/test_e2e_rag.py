"""E2E tests for the RAG pipeline: search_products tool.

Covers:
  - Successful product search with mocked EmbeddingEngine + DB.
  - Empty results scenario.
  - Discount application per CRM segment.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.engine import SalesDeps, search_products
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conversation(stage: SalesStage = SalesStage.SOLUTION) -> Any:
    conv = MagicMock(spec=Conversation)
    conv.phone = "+971500000001"
    conv.sales_stage = stage.value
    conv.language = "en"
    conv.customer_name = None
    conv.escalation_status = "none"
    return conv


def _make_deps(
    conv: Conversation,
    crm_context: dict[str, Any] | None = None,
) -> SalesDeps:
    return SalesDeps(
        db=AsyncMock(spec=AsyncSession),
        redis=AsyncMock(spec=Redis),
        conversation=conv,
        embedding_engine=AsyncMock(spec=EmbeddingEngine),
        zoho_inventory=AsyncMock(spec=ZohoInventoryClient),
        zoho_crm=AsyncMock(spec=ZohoCRMClient),
        messaging_client=AsyncMock(spec=MessagingProvider),
        pii_map={},
        crm_context=crm_context,
    )


@dataclass
class _FakeRunContext:
    deps: SalesDeps


# ---------------------------------------------------------------------------
# Fixtures: mock products
# ---------------------------------------------------------------------------


def _fake_product_read(
    sku: str = "CHAIR-01",
    name_en: str = "Ergonomic Office Chair",
    price: float = 500.0,
    currency: str = "AED",
    description_en: str = "Premium ergonomic chair",
) -> Any:
    """Return a lightweight object that looks like ProductRead."""
    import uuid
    from datetime import datetime

    from src.schemas.product import ProductRead

    return ProductRead(
        id=uuid.uuid4(),
        sku=sku,
        name_en=name_en,
        name_ar=None,
        description_en=description_en,
        category="Chairs",
        subcategory=None,
        price=price,
        currency=currency,
        stock=10,
        image_url=None,
        attributes=None,
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPerformSearchProducts:
    """Test the search_products tool (RAG pipeline)."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.rag_search_products")
    async def test_returns_formatted_product_info(self, mock_search: AsyncMock) -> None:
        """Successful search returns formatted product strings."""
        from src.schemas.product import ProductSearchResult

        product = _fake_product_read()
        mock_search.return_value = ProductSearchResult(
            products=[product],
            query_interpreted="office chair",
            total_found=1,
        )

        conv = _make_conversation()
        deps = _make_deps(conv, crm_context={"Segment": "Unknown"})
        ctx = _FakeRunContext(deps=deps)

        result = await search_products(ctx, "ergonomic chair")  # type: ignore[arg-type]

        assert "CHAIR-01" in result
        assert "Ergonomic Office Chair" in result
        assert "AED" in result
        mock_search.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("src.llm.engine.rag_search_products")
    async def test_empty_results(self, mock_search: AsyncMock) -> None:
        """When no products match, return appropriate message."""
        from src.schemas.product import ProductSearchResult

        mock_search.return_value = ProductSearchResult(
            products=[],
            query_interpreted="nonexistent item",
            total_found=0,
        )

        conv = _make_conversation()
        deps = _make_deps(conv)
        ctx = _FakeRunContext(deps=deps)

        result = await search_products(ctx, "nonexistent item")  # type: ignore[arg-type]
        assert "No products found" in result

    @pytest.mark.asyncio
    @patch("src.llm.engine.rag_search_products")
    async def test_wholesale_discount_applied(self, mock_search: AsyncMock) -> None:
        """Wholesale segment should get 15% discount on prices."""
        from src.schemas.product import ProductSearchResult

        product = _fake_product_read(price=1000.0)
        mock_search.return_value = ProductSearchResult(
            products=[product],
            query_interpreted="chair",
            total_found=1,
        )

        conv = _make_conversation()
        deps = _make_deps(conv, crm_context={"Segment": "Wholesale"})
        ctx = _FakeRunContext(deps=deps)

        result = await search_products(ctx, "chair")  # type: ignore[arg-type]

        # 1000 * 0.85 = 850.00
        assert "850.00" in result

    @pytest.mark.asyncio
    @patch("src.llm.engine.rag_search_products")
    async def test_horeca_discount_applied(self, mock_search: AsyncMock) -> None:
        """Horeca segment should get 10% discount on prices."""
        from src.schemas.product import ProductSearchResult

        product = _fake_product_read(price=200.0)
        mock_search.return_value = ProductSearchResult(
            products=[product],
            query_interpreted="table",
            total_found=1,
        )

        conv = _make_conversation()
        deps = _make_deps(conv, crm_context={"Segment": "Horeca"})
        ctx = _FakeRunContext(deps=deps)

        result = await search_products(ctx, "table")  # type: ignore[arg-type]

        # 200 * 0.90 = 180.00
        assert "180.00" in result

    @pytest.mark.asyncio
    @patch("src.llm.engine.rag_search_products")
    async def test_unknown_segment_no_discount(self, mock_search: AsyncMock) -> None:
        """Unknown segment gets base price (0% discount)."""
        from src.schemas.product import ProductSearchResult

        product = _fake_product_read(price=100.0)
        mock_search.return_value = ProductSearchResult(
            products=[product],
            query_interpreted="desk",
            total_found=1,
        )

        conv = _make_conversation()
        deps = _make_deps(conv, crm_context={"Segment": "Unknown"})
        ctx = _FakeRunContext(deps=deps)

        result = await search_products(ctx, "desk")  # type: ignore[arg-type]

        # 100 * 1.0 = 100.00
        assert "100.00" in result

    @pytest.mark.asyncio
    @patch("src.llm.engine.rag_search_products")
    async def test_multiple_products_formatted(self, mock_search: AsyncMock) -> None:
        """Multiple products should be separated by '---'."""
        from src.schemas.product import ProductSearchResult

        products = [
            _fake_product_read(sku="A1", name_en="Item A", price=100.0),
            _fake_product_read(sku="B2", name_en="Item B", price=200.0),
        ]
        mock_search.return_value = ProductSearchResult(
            products=products,
            query_interpreted="office furniture",
            total_found=2,
        )

        conv = _make_conversation()
        deps = _make_deps(conv, crm_context={"Segment": "Unknown"})
        ctx = _FakeRunContext(deps=deps)

        result = await search_products(ctx, "office furniture")  # type: ignore[arg-type]

        assert "---" in result
        assert "A1" in result
        assert "B2" in result
