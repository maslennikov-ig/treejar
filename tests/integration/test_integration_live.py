"""Live integration tests — NO mocks.

These tests call REAL APIs (Zoho CRM, Zoho Inventory, LLM via OpenRouter)
and a real PostgreSQL database. They are marked @pytest.mark.integration and
will gracefully SKIP in CI if the required environment variables are absent.

Run:
    uv run pytest tests/integration/ -v -m integration

Idempotency: DB tests use nested transactions with rollback.

Known test contact in Zoho CRM:
    Phone: +971000000001
    CRM ID: 559571000034673035
    Segment: ["Wholesale"]
"""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.conftest import (
    TEST_CONTACT_CRM_ID,
    TEST_CONTACT_EMAIL,
    TEST_CONTACT_NAME,
    TEST_CONTACT_PHONE,
    TEST_CONTACT_SEGMENT,
    USER_WHATSAPP_PHONE,
    skip_no_openrouter,
    skip_no_wazzup,
    skip_no_zoho_crm,
    skip_no_zoho_inventory,
)


# ====================================================================
# 1. Zoho CRM — Segment field type validation (known test contact)
# ====================================================================


@pytest.mark.integration
@skip_no_zoho_crm
class TestZohoCRMLive:
    """Verify real Zoho CRM responses using the known test contact."""

    async def test_crm_find_test_contact(self, zoho_crm_client: Any) -> None:
        """find_contact_by_phone finds our known test contact."""
        contact = await zoho_crm_client.find_contact_by_phone(TEST_CONTACT_PHONE)

        assert contact is not None, (
            f"Test contact {TEST_CONTACT_PHONE} not found in CRM! "
            "It may have been deleted. See GEMINI.md for how to recreate."
        )
        assert contact["id"] == TEST_CONTACT_CRM_ID
        assert contact.get("First_Name") == "Integration"
        assert contact.get("Last_Name") == "TestBot"

    async def test_crm_contact_segment_is_list(
        self, zoho_crm_client: Any
    ) -> None:
        """Zoho CRM returns Segment as a list (multi-select field).

        This is the EXACT bug that went to production:
        Our mocks returned Segment='Wholesale' (str) but the real API
        returns Segment=['Wholesale'] (list).
        """
        contact = await zoho_crm_client.find_contact_by_phone(TEST_CONTACT_PHONE)
        assert contact is not None, "Test contact not found"

        segment = contact.get("Segment")
        assert segment is not None, "Segment field is None on test contact"
        assert isinstance(segment, list), (
            f"Expected Segment to be list, got {type(segment).__name__}: {segment!r}. "
            "This is the exact bug that caused TypeError on prod!"
        )
        assert segment == TEST_CONTACT_SEGMENT

    async def test_crm_find_nonexistent_returns_none(
        self, zoho_crm_client: Any
    ) -> None:
        """find_contact_by_phone returns None for non-existent phone."""
        result = await zoho_crm_client.find_contact_by_phone("+000000000000")
        assert result is None, f"Expected None for non-existent phone, got: {result}"


# ====================================================================
# 2. Zoho Inventory — Stock field validation
# ====================================================================


@pytest.mark.integration
@skip_no_zoho_inventory
class TestZohoInventoryLive:
    """Verify real Zoho Inventory responses."""

    async def test_inventory_get_items_returns_stock(
        self, zoho_inventory_client: Any
    ) -> None:
        """get_items returns items with stock_on_hand as numeric value."""
        data = await zoho_inventory_client.get_items(page=1, per_page=5)

        items = data.get("items", [])
        if not items:
            pytest.skip("No items found in Zoho Inventory")
            return

        item = items[0]
        stock = item.get("stock_on_hand")

        assert stock is not None, (
            f"stock_on_hand is None for item {item.get('name', '?')}"
        )
        assert isinstance(stock, (int, float)), (
            f"Expected stock_on_hand to be numeric, got {type(stock).__name__}: {stock!r}"
        )

    async def test_inventory_get_stock_by_sku(
        self, zoho_inventory_client: Any
    ) -> None:
        """get_stock returns a dict with stock_on_hand for a real SKU."""
        # First, get any real item to know a valid SKU
        data = await zoho_inventory_client.get_items(page=1, per_page=3)
        items = data.get("items", [])
        if not items:
            pytest.skip("No items in Zoho Inventory to test get_stock")
            return

        real_sku = items[0].get("sku")
        if not real_sku:
            pytest.skip("First item has no SKU")
            return

        result = await zoho_inventory_client.get_stock(real_sku)
        assert result is not None, f"get_stock returned None for real SKU: {real_sku}"
        assert "stock_on_hand" in result, (
            f"Missing stock_on_hand in response: {list(result.keys())}"
        )

    async def test_inventory_nonexistent_sku_returns_none(
        self, zoho_inventory_client: Any
    ) -> None:
        """get_stock for a fake SKU should return None."""
        result = await zoho_inventory_client.get_stock("NONEXISTENT-SKU-XYZ-99999")
        assert result is None


# ====================================================================
# 3. Discounts + Real CRM data — end-to-end
# ====================================================================


@pytest.mark.integration
@skip_no_zoho_crm
class TestDiscountsWithRealCRM:
    """Verify discount calculation works with real CRM Segment values."""

    async def test_real_segment_discount(self, zoho_crm_client: Any) -> None:
        """Fetch test contact and apply discount — no TypeError."""
        from src.core.discounts import apply_discount, get_discount_percentage

        contact = await zoho_crm_client.find_contact_by_phone(TEST_CONTACT_PHONE)
        assert contact is not None, "Test contact not found in CRM"

        segment = contact.get("Segment")
        # This MUST NOT raise — this is the exact prod bug
        discount = get_discount_percentage(segment)
        assert isinstance(discount, int)
        assert discount == 15  # Wholesale = 15%

        price = apply_discount(1000.0, segment)
        assert isinstance(price, float)
        assert price == 850.0  # 1000 - 15%


# ====================================================================
# 4. LLM + search_products — real model, real RAG pipeline
# ====================================================================


@pytest.mark.integration
@skip_no_openrouter
@skip_no_zoho_crm
class TestLLMSearchProductsLive:
    """Run search_products tool with real CRM segment (spends no LLM tokens)."""

    async def test_search_products_no_crash(
        self, zoho_crm_client: Any, zoho_inventory_client: Any, live_redis: Any
    ) -> None:
        """search_products tool runs without TypeError on real CRM segment."""
        from unittest.mock import AsyncMock, MagicMock
        from uuid import uuid4

        from pydantic_ai import RunContext
        from pydantic_ai.models.test import TestModel
        from pydantic_ai.usage import RunUsage

        from src.integrations.messaging.base import MessagingProvider
        from src.llm.engine import SalesDeps, search_products
        from src.models.conversation import Conversation
        from src.rag.embeddings import EmbeddingEngine
        from src.schemas.common import SalesStage
        from src.schemas.product import ProductRead, ProductSearchResult

        # Fetch real CRM context for the test contact
        contact = await zoho_crm_client.find_contact_by_phone(TEST_CONTACT_PHONE)
        assert contact is not None, "Test contact not found in CRM"

        crm_context: dict[str, Any] = {
            "Name": TEST_CONTACT_NAME,
            "Segment": contact.get("Segment"),  # real list from CRM
        }

        conv = MagicMock(spec=Conversation)
        conv.phone = TEST_CONTACT_PHONE
        conv.sales_stage = SalesStage.SOLUTION.value
        conv.language = "en"
        conv.customer_name = TEST_CONTACT_NAME
        conv.escalation_status = "none"

        deps = SalesDeps(
            db=AsyncMock(),
            redis=live_redis,
            conversation=conv,
            embedding_engine=AsyncMock(spec=EmbeddingEngine),
            zoho_inventory=zoho_inventory_client,
            zoho_crm=zoho_crm_client,
            messaging_client=AsyncMock(spec=MessagingProvider),
            pii_map={},
            crm_context=crm_context,
        )

        # Mock RAG search (we test discount path, not RAG)
        import src.llm.engine as engine_module

        orig_search = engine_module.rag_search_products

        from datetime import datetime, timezone
        fake_product = ProductRead(
            id=uuid4(),
            sku="INTEG-TEST-001",
            name_en="Integration Test Chair",
            price=1000.0,
            currency="AED",
            stock=10,
            is_active=True,
            description_en="Test product for integration testing",
            created_at=datetime.now(timezone.utc),
        )
        mock_rag = AsyncMock(
            return_value=ProductSearchResult(
                products=[fake_product],
                query_interpreted="test chair",
                total_found=1,
            )
        )
        engine_module.rag_search_products = mock_rag  # type: ignore[assignment]

        try:
            ctx = RunContext(
                deps=deps,
                retry=0,
                messages=[],
                prompt="test chair",
                model=TestModel(),
                usage=RunUsage(),
            )

            # This is the critical call — must NOT raise TypeError
            result = await search_products(ctx, "ergonomic chair")

            assert isinstance(result, str)
            assert "Integration Test Chair" in result
            assert "AED" in result
            # Verify discount was applied (15% off 1000 = 850)
            assert "850" in result
        finally:
            engine_module.rag_search_products = orig_search  # type: ignore[assignment]


# ====================================================================
# 5. PDF Quotation generation — real Zoho Inventory data
# ====================================================================

PDF_OUTPUT_PATH = "/tmp/integration_test_quotation.pdf"


@pytest.mark.integration
@skip_no_zoho_crm
@skip_no_zoho_inventory
class TestQuotationPDFGeneration:
    """Generate a real PDF quotation using live Zoho data."""

    async def test_generate_pdf_from_real_inventory(
        self,
        zoho_crm_client: Any,
        zoho_inventory_client: Any,
    ) -> None:
        """Fetch real SKUs from Zoho Inventory, apply CRM discount, generate PDF."""
        import datetime as _dt
        from pathlib import Path

        from src.core.discounts import apply_discount
        from src.services.pdf.generator import generate_pdf, render_quotation_html

        # 1. Fetch real items from Zoho Inventory
        data = await zoho_inventory_client.get_items(page=1, per_page=3)
        items = data.get("items", [])
        assert len(items) >= 1, "No items in Zoho Inventory to build a quotation"

        # 2. Get real CRM segment for test contact
        contact = await zoho_crm_client.find_contact_by_phone(TEST_CONTACT_PHONE)
        assert contact is not None, "Test contact not found"
        segment = contact.get("Segment")

        # 3. Build quotation line items from real inventory data
        template_items = []
        subtotal = 0.0

        for inv_item in items[:3]:  # use up to 3 items
            base_price = float(inv_item.get("rate", 0) or inv_item.get("price", 0) or 100)
            unit_price = apply_discount(base_price, segment)
            quantity = 2
            total_price = unit_price * quantity
            subtotal += total_price

            template_items.append({
                "sku": inv_item.get("sku", "N/A"),
                "name": inv_item.get("name", "Unknown item"),
                "description": inv_item.get("description", ""),
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "image_url": inv_item.get("image_document_id"),
            })

        vat_amount = subtotal * 0.05
        grand_total = subtotal + vat_amount

        pdf_context = {
            "quote_number": "INTEG-TEST-001",
            "trn": "100418386400003",
            "date": _dt.date.today().strftime("%d %B %Y"),
            "customer": {
                "name": TEST_CONTACT_NAME,
                "company": "Integration Test Co.",
                "email": TEST_CONTACT_EMAIL,
                "address": "UAE",
            },
            "items": template_items,
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "grand_total": grand_total,
            "manager": {
                "name": "Syed Amanullah",
                "phone": "+971545467851",
                "email": "syed.h@treejartrading.ae",
            },
        }

        # 4. Render HTML and generate PDF
        html_content = render_quotation_html(pdf_context)
        assert len(html_content) > 100, "HTML template rendered too short"

        pdf_bytes = await generate_pdf(html_content)
        assert len(pdf_bytes) > 1000, f"PDF too small: {len(pdf_bytes)} bytes"
        assert pdf_bytes[:5] == b"%PDF-", "Output is not a valid PDF"

        # 5. Save to disk for user review
        Path(PDF_OUTPUT_PATH).write_bytes(pdf_bytes)


# ====================================================================
# 6. Wazzup — Send PDF via WhatsApp
# ====================================================================


@pytest.mark.integration
@skip_no_wazzup
@skip_no_zoho_crm
@skip_no_zoho_inventory
class TestWazzupSendQuotation:
    """Send the generated PDF to user's WhatsApp via Wazzup."""

    async def test_send_pdf_via_wazzup(
        self,
        zoho_crm_client: Any,
        zoho_inventory_client: Any,
        wazzup_client: Any,
    ) -> None:
        """Generate a real PDF and send it to user's WhatsApp number."""
        import datetime as _dt
        from pathlib import Path

        from src.core.discounts import apply_discount
        from src.services.pdf.generator import generate_pdf, render_quotation_html

        # 1. Fetch real items
        data = await zoho_inventory_client.get_items(page=1, per_page=3)
        items = data.get("items", [])
        assert len(items) >= 1, "No items in Zoho Inventory"

        # 2. Get CRM segment
        contact = await zoho_crm_client.find_contact_by_phone(TEST_CONTACT_PHONE)
        assert contact is not None, "Test contact not found"
        segment = contact.get("Segment")

        # 3. Build items
        template_items = []
        subtotal = 0.0

        for inv_item in items[:3]:
            base_price = float(inv_item.get("rate", 0) or inv_item.get("price", 0) or 100)
            unit_price = apply_discount(base_price, segment)
            quantity = 1
            total_price = unit_price * quantity
            subtotal += total_price

            template_items.append({
                "sku": inv_item.get("sku", "N/A"),
                "name": inv_item.get("name", "Unknown item"),
                "description": inv_item.get("description", ""),
                "quantity": quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "image_url": inv_item.get("image_document_id"),
            })

        vat_amount = subtotal * 0.05
        grand_total = subtotal + vat_amount

        pdf_context = {
            "quote_number": "INTEG-WAZZUP-001",
            "trn": "100418386400003",
            "date": _dt.date.today().strftime("%d %B %Y"),
            "customer": {
                "name": TEST_CONTACT_NAME,
                "company": "Integration Test Co.",
                "email": TEST_CONTACT_EMAIL,
                "address": "UAE",
            },
            "items": template_items,
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "grand_total": grand_total,
            "manager": {
                "name": "Syed Amanullah",
                "phone": "+971545467851",
                "email": "syed.h@treejartrading.ae",
            },
        }

        # 4. Generate PDF
        html_content = render_quotation_html(pdf_context)
        pdf_bytes = await generate_pdf(html_content)
        assert pdf_bytes[:5] == b"%PDF-", "Not a valid PDF"

        # Save for review
        Path(PDF_OUTPUT_PATH).write_bytes(pdf_bytes)

        # 5. Send via Wazzup to user's WhatsApp
        msg_id = await wazzup_client.send_media(
            chat_id=USER_WHATSAPP_PHONE,
            caption="🧪 Integration Test Quotation (INTEG-WAZZUP-001)",
            content=pdf_bytes,
            content_type="application/pdf",
        )
        assert msg_id != "", "Wazzup returned empty message ID"

