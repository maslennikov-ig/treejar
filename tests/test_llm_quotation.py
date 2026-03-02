from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic_ai import RunContext

from src.llm.engine import QuotationItem, SalesDeps, create_quotation
from src.models.conversation import Conversation


@pytest.mark.asyncio
async def test_create_quotation_tool():
    # Setup mocks
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = [
        {
            "sku": "CHAIR-1",
            "item_id": "123",
            "rate": 150.0,
            "description": "A nice chair",
            "name": "Chair",
        }
    ]
    mock_inventory.create_sale_order.return_value = {
        "saleorder": {"salesorder_number": "SA-001", "status": "draft"}
    }

    mock_messaging = AsyncMock()
    mock_conversation = MagicMock(spec=Conversation)
    mock_conversation.phone = "+1234567890"
    mock_conversation.customer_name = "Test Customer"

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = mock_messaging
    deps.conversation = mock_conversation

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    items = [QuotationItem(sku="CHAIR-1", quantity=2)]

    # Patch generate_pdf at the definition module (lazy import inside function)
    from unittest.mock import AsyncMock as AM
    from unittest.mock import patch
    with patch("src.services.pdf.generator.generate_pdf", new_callable=AM) as mock_pdf, \
         patch("src.services.pdf.generator.render_quotation_html", return_value="<html>"):
        mock_pdf.return_value = b"pdf_data"
        result = await create_quotation(ctx, items)

    assert "Successfully generated quotation" in result
    assert "SA-001" in result

    # Verify Inventory calls
    mock_inventory.get_stock_bulk.assert_called_once_with(["CHAIR-1"])
    mock_inventory.create_sale_order.assert_called_once()
    _, kwargs = mock_inventory.create_sale_order.call_args
    assert kwargs["status"] == "draft"
    assert kwargs["items"][0]["item_id"] == "123"
    assert kwargs["items"][0]["quantity"] == 2

    # Verify PDF generation was called
    mock_pdf.assert_called_once()

    # Verify Messaging
    mock_messaging.send_media.assert_called_once_with(
        chat_id="+1234567890",
        url=None,
        caption="Here is your quotation: SA-001",
        content=b"pdf_data",
        content_type="application/pdf",
    )



@pytest.mark.asyncio
async def test_create_quotation_sku_not_found():
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = []  # SKU not found

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    items = [QuotationItem(sku="NON_EXISTENT", quantity=1)]

    result = await create_quotation(ctx, items)
    assert "Failed to create quotation" in result
    assert "NON_EXISTENT" in result
