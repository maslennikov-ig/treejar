"""E2E tests for Pydantic-AI tools: get_stock, lookup_customer, create_deal, create_quotation.

Covers:
  - Inventory stock lookup (found / not found).
  - CRM contact lookup (found / not found / no client).
  - CRM deal creation (existing contact / new contact / failures).
  - Quotation generation: line items, VAT, PDF, WhatsApp send.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.engine import (
    QuotationItem,
    SalesDeps,
    create_deal,
    create_quotation,
    get_stock,
    lookup_customer,
)
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_conversation(
    stage: SalesStage = SalesStage.QUOTING,
    phone: str = "+971501234567",
    customer_name: str | None = "Ahmed",
) -> Any:
    conv = MagicMock(spec=Conversation)
    conv.phone = phone
    conv.sales_stage = stage.value
    conv.language = "en"
    conv.customer_name = customer_name
    conv.escalation_status = "none"
    return conv


def _make_deps(
    conv: Conversation,
    *,
    zoho_inventory: Any = None,
    zoho_crm: Any = None,
    messaging_client: Any = None,
    crm_context: dict[str, Any] | None = None,
) -> SalesDeps:
    return SalesDeps(
        db=AsyncMock(spec=AsyncSession),
        redis=AsyncMock(spec=Redis),
        conversation=conv,
        embedding_engine=AsyncMock(spec=EmbeddingEngine),
        zoho_inventory=zoho_inventory or AsyncMock(spec=ZohoInventoryClient),
        zoho_crm=zoho_crm,
        messaging_client=messaging_client or AsyncMock(spec=MessagingProvider),
        pii_map={},
        crm_context=crm_context,
    )


@dataclass
class _FakeRunContext:
    deps: SalesDeps


# ====================================================================
# get_stock
# ====================================================================


class TestGetStock:
    """Tests for the get_stock tool (Inventory)."""

    @pytest.mark.asyncio
    async def test_stock_found(self) -> None:
        """When SKU exists, report available count."""
        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock.return_value = {"available_stock": 42}

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_inventory=mock_inv)
        ctx = _FakeRunContext(deps=deps)

        result = await get_stock(ctx, "CHAIR-01")  # type: ignore[arg-type]

        assert "42" in result
        assert "CHAIR-01" in result
        mock_inv.get_stock.assert_awaited_once_with("CHAIR-01")

    @pytest.mark.asyncio
    async def test_stock_not_found(self) -> None:
        """When SKU does not exist, report not found."""
        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock.return_value = None

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_inventory=mock_inv)
        ctx = _FakeRunContext(deps=deps)

        result = await get_stock(ctx, "NONEXISTENT")  # type: ignore[arg-type]
        assert "not found" in result


# ====================================================================
# lookup_customer
# ====================================================================


class TestLookupCustomer:
    """Tests for the lookup_customer tool (CRM)."""

    @pytest.mark.asyncio
    async def test_customer_found(self) -> None:
        mock_crm = AsyncMock(spec=ZohoCRMClient)
        mock_crm.find_contact_by_phone.return_value = {
            "id": "crm_123",
            "First_Name": "John",
            "Last_Name": "Doe",
            "Email": "john@example.com",
            "Segment": "Wholesale",
        }

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=mock_crm)
        ctx = _FakeRunContext(deps=deps)

        result = await lookup_customer(ctx, "+971501234567")  # type: ignore[arg-type]

        assert "FOUND" in result
        assert "John Doe" in result
        assert "Wholesale" in result

    @pytest.mark.asyncio
    async def test_customer_not_found(self) -> None:
        mock_crm = AsyncMock(spec=ZohoCRMClient)
        mock_crm.find_contact_by_phone.return_value = None

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=mock_crm)
        ctx = _FakeRunContext(deps=deps)

        result = await lookup_customer(ctx, "+971999999999")  # type: ignore[arg-type]
        assert "NOT found" in result

    @pytest.mark.asyncio
    async def test_crm_client_unavailable(self) -> None:
        """When CRM client is None, return error string."""
        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=None)
        ctx = _FakeRunContext(deps=deps)

        result = await lookup_customer(ctx, "+971501234567")  # type: ignore[arg-type]
        assert "not available" in result


# ====================================================================
# create_deal
# ====================================================================


class TestCreateDeal:
    """Tests for the create_deal tool (CRM)."""

    @pytest.mark.asyncio
    async def test_deal_with_existing_contact(self) -> None:
        mock_crm = AsyncMock(spec=ZohoCRMClient)
        mock_crm.find_contact_by_phone.return_value = {"id": "contact_001"}
        mock_crm.create_deal.return_value = {
            "details": {"id": "deal_001"},
        }

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=mock_crm)
        ctx = _FakeRunContext(deps=deps)

        result = await create_deal(ctx, "Office Chairs x10", 5000.0)  # type: ignore[arg-type]

        assert "deal_001" in result
        assert "Successfully created" in result
        mock_crm.create_deal.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deal_creates_contact_if_missing(self) -> None:
        mock_crm = AsyncMock(spec=ZohoCRMClient)
        mock_crm.find_contact_by_phone.return_value = None
        mock_crm.create_contact.return_value = {
            "details": {"id": "new_contact_001"},
        }
        mock_crm.create_deal.return_value = {
            "details": {"id": "deal_002"},
        }

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=mock_crm)
        ctx = _FakeRunContext(deps=deps)

        result = await create_deal(ctx, "New Deal", 1000.0)  # type: ignore[arg-type]

        assert "deal_002" in result
        mock_crm.create_contact.assert_awaited_once()
        mock_crm.create_deal.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deal_fails_when_contact_creation_fails(self) -> None:
        mock_crm = AsyncMock(spec=ZohoCRMClient)
        mock_crm.find_contact_by_phone.return_value = None
        mock_crm.create_contact.return_value = {"error": "API error"}

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=mock_crm)
        ctx = _FakeRunContext(deps=deps)

        result = await create_deal(ctx, "Bad Deal")  # type: ignore[arg-type]
        assert "Failed to create customer" in result

    @pytest.mark.asyncio
    async def test_crm_unavailable(self) -> None:
        conv = _make_conversation()
        deps = _make_deps(conv, zoho_crm=None)
        ctx = _FakeRunContext(deps=deps)

        result = await create_deal(ctx, "No CRM")  # type: ignore[arg-type]
        assert "not available" in result


# ====================================================================
# create_quotation
# ====================================================================


class TestCreateQuotation:
    """Tests for the create_quotation tool (Inventory + PDF + Messaging)."""

    @pytest.mark.asyncio
    @patch("src.services.pdf.generator.render_quotation_html", return_value="<html>QUOTE</html>")
    @patch("src.services.pdf.generator.generate_pdf", new_callable=AsyncMock)
    async def test_quotation_happy_path(
        self,
        mock_gen_pdf: AsyncMock,
        mock_render: AsyncMock,
    ) -> None:
        """Full quotation flow: fetch items, build PDF, send via messaging."""
        mock_gen_pdf.return_value = b"%PDF-fake-bytes"

        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock_bulk.return_value = [
            {
                "sku": "CHAIR-01",
                "item_id": "zoho_item_001",
                "rate": 500.0,
                "name": "Ergonomic Chair",
                "description": "A great chair",
                "image_document_id": None,
            },
        ]
        mock_inv.create_sale_order.return_value = {
            "saleorder": {"salesorder_number": "SO-0001"},
        }

        mock_messaging = AsyncMock(spec=MessagingProvider)

        conv = _make_conversation()
        deps = _make_deps(
            conv,
            zoho_inventory=mock_inv,
            messaging_client=mock_messaging,
            crm_context={"Segment": "Wholesale"},
        )
        ctx = _FakeRunContext(deps=deps)

        items = [QuotationItem(sku="CHAIR-01", quantity=3)]
        result = await create_quotation(ctx, items)  # type: ignore[arg-type]

        assert "SO-0001" in result
        assert "Successfully generated" in result
        mock_inv.get_stock_bulk.assert_awaited_once()
        mock_inv.create_sale_order.assert_awaited_once()
        mock_messaging.send_media.assert_awaited_once()

        # Verify PDF was generated with bytes
        mock_gen_pdf.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_quotation_sku_not_found(self) -> None:
        """When a requested SKU is missing from stock, return error."""
        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock_bulk.return_value = []  # no items found

        conv = _make_conversation()
        deps = _make_deps(conv, zoho_inventory=mock_inv, crm_context={"Segment": "Unknown"})
        ctx = _FakeRunContext(deps=deps)

        items = [QuotationItem(sku="NONEXISTENT", quantity=1)]
        result = await create_quotation(ctx, items)  # type: ignore[arg-type]

        assert "not found" in result

    @pytest.mark.asyncio
    @patch("src.services.pdf.generator.render_quotation_html", return_value="<html></html>")
    @patch("src.services.pdf.generator.generate_pdf", new_callable=AsyncMock)
    async def test_quotation_messaging_failure(
        self,
        mock_gen_pdf: AsyncMock,
        mock_render: AsyncMock,
    ) -> None:
        """When messaging fails, report the error but PDF was generated."""
        mock_gen_pdf.return_value = b"%PDF-bytes"

        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock_bulk.return_value = [
            {
                "sku": "DESK-01",
                "item_id": "zoho_item_002",
                "rate": 800.0,
                "name": "Standing Desk",
                "description": "Height adjustable",
                "image_document_id": None,
            },
        ]
        mock_inv.create_sale_order.return_value = {
            "saleorder": {"salesorder_number": "SO-0002"},
        }

        mock_messaging = AsyncMock(spec=MessagingProvider)
        mock_messaging.send_media.side_effect = Exception("Wazzup API timeout")

        conv = _make_conversation()
        deps = _make_deps(
            conv,
            zoho_inventory=mock_inv,
            messaging_client=mock_messaging,
            crm_context={"Segment": "Unknown"},
        )
        ctx = _FakeRunContext(deps=deps)

        items = [QuotationItem(sku="DESK-01", quantity=1)]
        result = await create_quotation(ctx, items)  # type: ignore[arg-type]

        assert "failed to send" in result.lower()

    @pytest.mark.asyncio
    @patch("src.services.pdf.generator.render_quotation_html", return_value="<html>Q</html>")
    @patch("src.services.pdf.generator.generate_pdf", new_callable=AsyncMock)
    async def test_quotation_vat_calculation(
        self,
        mock_gen_pdf: AsyncMock,
        mock_render: AsyncMock,
    ) -> None:
        """Verify correct VAT (5%) and grand total are in the PDF context."""
        mock_gen_pdf.return_value = b"%PDF-bytes"

        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock_bulk.return_value = [
            {
                "sku": "TABLE-01",
                "item_id": "zoho_003",
                "rate": 1000.0,
                "name": "Conference Table",
                "description": "Big table",
                "image_document_id": None,
            },
        ]
        mock_inv.create_sale_order.return_value = {
            "saleorder": {"salesorder_number": "SO-0003"},
        }

        mock_messaging = AsyncMock(spec=MessagingProvider)

        conv = _make_conversation()
        # No discount (Unknown segment) → rate stays 1000
        deps = _make_deps(
            conv,
            zoho_inventory=mock_inv,
            messaging_client=mock_messaging,
            crm_context={"Segment": "Unknown"},
        )
        ctx = _FakeRunContext(deps=deps)

        items = [QuotationItem(sku="TABLE-01", quantity=2)]
        result = await create_quotation(ctx, items)  # type: ignore[arg-type]

        # subtotal = 2000, vat = 100, grand = 2100
        # We verify the render function was called (the VAT is inside pdf_context)
        assert "SO-0003" in result
        mock_render.assert_called_once()

        # Inspect the pdf_context dict passed to render_quotation_html
        call_args = mock_render.call_args
        pdf_ctx = call_args[0][0]  # first positional arg
        assert pdf_ctx["subtotal"] == 2000.0
        assert pdf_ctx["vat_amount"] == 100.0
        assert pdf_ctx["grand_total"] == 2100.0
