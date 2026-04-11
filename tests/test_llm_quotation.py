from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import RunContext

from src.llm.engine import (
    QuotationItem,
    SalesDeps,
    create_quotation,
    resolve_inventory_customer_id,
)
from src.models.conversation import Conversation


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_tool(mock_notify: AsyncMock) -> None:
    # Setup mocks
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = [
        {
            "sku": "CHAIR-1",
            "item_id": "123",
            "rate": 150.0,
            "stock_on_hand": 25,
            "description": "A nice chair",
            "name": "Chair",
        }
    ]
    mock_inventory.create_sale_order.return_value = {
        "saleorder": {"salesorder_number": "SA-001", "status": "draft"}
    }
    mock_inventory.get_item_image.return_value = (b"img-bytes", "image/jpeg")
    mock_inventory.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-001",
        "contact_type": "customer",
        "status": "active",
    }

    mock_messaging = AsyncMock()
    mock_conversation = MagicMock(spec=Conversation)
    mock_conversation.phone = "+1234567890"
    mock_conversation.customer_name = "Test Customer"

    # Redis must be AsyncMock (not MagicMock) for setex to be awaitable
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = mock_messaging
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    # Provide a zoho_crm mock so CRM lookup works (returns no contact → uses conversation data)
    mock_crm = AsyncMock()
    mock_crm.find_contact_by_phone.return_value = {
        "id": "crm-contact-001",
        "First_Name": "Test",
        "Last_Name": "Customer",
        "Email": "test@example.com",
        "Account_Name": {"name": "Treejar Trading"},
    }
    deps.zoho_crm = mock_crm

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    items = [QuotationItem(sku="CHAIR-1", quantity=2)]

    # Patch generate_pdf at the definition module (lazy import inside function)
    with (
        patch(
            "src.services.pdf.generator.generate_pdf", new_callable=AsyncMock
        ) as mock_pdf,
        patch(
            "src.services.pdf.generator.render_quotation_html", return_value="<html>"
        ) as mock_render,
    ):
        mock_pdf.return_value = b"pdf_data"
        result = await create_quotation(ctx, items)

    assert "SA-001" in result

    # Verify Inventory calls
    mock_inventory.get_stock_bulk.assert_called_once_with(["CHAIR-1"])
    mock_inventory.create_sale_order.assert_called_once()
    _, kwargs = mock_inventory.create_sale_order.call_args
    assert kwargs["customer_id"] == "inventory-contact-001"
    assert kwargs["status"] == "draft"
    assert kwargs["items"][0]["item_id"] == "123"
    assert kwargs["items"][0]["quantity"] == 2

    mock_inventory.get_item_image.assert_awaited_once_with("123")
    render_context = mock_render.call_args.args[0]
    assert render_context["items"][0]["image_url"].startswith("data:image/jpeg;base64,")

    # Verify PDF generation was called
    mock_pdf.assert_called_once()

    # New flow: PDF stored in Redis + escalation notification
    mock_redis.setex.assert_awaited()
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_quotation_sku_not_found() -> None:
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = []  # SKU not found
    mock_inventory.get_stock.return_value = None

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    deps.db.execute.return_value = execute_result
    deps.catalog_mismatch_alerted = False

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    items = [QuotationItem(sku="NON_EXISTENT", quantity=1)]

    result = await create_quotation(ctx, items)
    assert "Failed to create quotation" in result
    assert "NON_EXISTENT" in result


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_without_company_email_uses_temp_customer(
    mock_notify: AsyncMock,
) -> None:
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = [
        {
            "sku": "CHAIR-1",
            "item_id": "123",
            "rate": 150.0,
            "stock_on_hand": 25,
            "description": "A nice chair",
            "name": "Chair",
        }
    ]
    mock_inventory.create_sale_order.return_value = {
        "saleorder": {"salesorder_number": "SA-001", "status": "draft"}
    }
    mock_inventory.find_customer_by_phone.return_value = None
    mock_inventory.create_contact.return_value = {
        "contact_id": "inventory-contact-created",
        "contact_type": "customer",
        "status": "active",
    }

    mock_conversation = SimpleNamespace(
        id="conv-1",
        phone="+1234567890",
        customer_name=None,
        metadata_={},
    )
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = AsyncMock()
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = None
    deps.catalog_mismatch_alerted = False

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    with (
        patch(
            "src.services.pdf.generator.generate_pdf", new_callable=AsyncMock
        ) as mock_pdf,
        patch(
            "src.services.pdf.generator.render_quotation_html", return_value="<html>"
        ),
    ):
        mock_pdf.return_value = b"pdf_data"
        result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "SA-001" in result
    _, kwargs = mock_inventory.create_sale_order.call_args
    assert kwargs["customer_id"] == "inventory-contact-created"
    mock_inventory.create_contact.assert_awaited_once()
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_inventory_contact_creation_failure_fails_closed(
    mock_notify: AsyncMock,
) -> None:
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = [
        {
            "sku": "CHAIR-1",
            "item_id": "123",
            "rate": 150.0,
            "stock_on_hand": 25,
            "description": "A nice chair",
            "name": "Chair",
        }
    ]
    mock_inventory.find_customer_by_phone.return_value = None
    mock_inventory.create_contact.side_effect = RuntimeError("inventory create failed")

    mock_conversation = SimpleNamespace(
        id="conv-1",
        phone="+1234567890",
        customer_name=None,
        escalation_status="none",
        metadata_={},
    )
    mock_redis = AsyncMock()
    mock_db = AsyncMock()

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = AsyncMock()
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = {"id": "crm-contact-001"}
    deps.recent_history = ["user: exact quote for CHAIR-1"]
    deps.catalog_mismatch_alerted = False

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "couldn't finalize the exact quotation automatically" in result.lower()
    mock_inventory.create_sale_order.assert_not_called()
    mock_notify.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_inventory_customer_id_recovers_from_duplicate_name_conflict() -> (
    None
):
    duplicate_response = httpx.Response(
        400,
        json={
            "code": 3062,
            "message": 'The customer "None Игорь" already exists. Please specify a different name.',
        },
        request=httpx.Request("POST", "https://example.com/contacts"),
    )

    mock_inventory = AsyncMock()
    mock_inventory.find_customer_by_phone.return_value = None
    mock_inventory.find_customer_by_email.return_value = None
    mock_inventory.find_customer_by_name.return_value = {
        "contact_id": "existing-inventory-contact",
        "contact_type": "customer",
        "status": "active",
    }
    mock_inventory.create_contact.side_effect = httpx.HTTPStatusError(
        "duplicate name",
        request=duplicate_response.request,
        response=duplicate_response,
    )

    result = await resolve_inventory_customer_id(
        phone="+79262810921",
        customer_name="None Игорь",
        customer_email="",
        customer_company="None Игорь",
        zoho_inventory=mock_inventory,
    )

    assert result == "existing-inventory-contact"


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_catalog_mismatch_notifies_and_aborts(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
) -> None:
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = []
    mock_inventory.get_stock.return_value = None

    mock_conversation = SimpleNamespace(
        id="conv-1",
        phone="+1234567890",
        customer_name=None,
        metadata_={},
    )
    mock_redis = AsyncMock()
    mock_db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(
        sku="CHAIR-1",
        name_en="Treejar Chair",
        attributes={"treejar_slug": "treejar-chair"},
        zoho_item_id=None,
    )
    mock_db.execute.return_value = execute_result

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = AsyncMock()
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = None
    deps.recent_history = ["user: exact quote for CHAIR-1"]
    deps.catalog_mismatch_alerted = False

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "couldn't confirm exact price and availability" in result.lower()
    mock_notify_mismatch.assert_awaited_once()
    mock_notify_manager.assert_awaited_once()
    mock_inventory.create_sale_order.assert_not_called()


@pytest.mark.asyncio
@patch("src.services.notifications.notify_catalog_mismatch", new_callable=AsyncMock)
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_malformed_inventory_payload_fails_closed(
    mock_notify_manager: AsyncMock,
    mock_notify_mismatch: AsyncMock,
) -> None:
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = []
    mock_inventory.get_item.return_value = "bad-get-item-payload"
    mock_inventory.get_stock.return_value = {"sku": "CHAIR-1", "rate": "oops"}

    mock_conversation = SimpleNamespace(
        id="conv-1",
        phone="+1234567890",
        customer_name=None,
        metadata_={},
    )
    mock_redis = AsyncMock()
    mock_db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(
        sku="CHAIR-1",
        name_en="Treejar Chair",
        attributes={"treejar_slug": "treejar-chair"},
        zoho_item_id="zoho-item-123",
    )
    mock_db.execute.return_value = execute_result

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = AsyncMock()
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = None
    deps.recent_history = ["user: exact quote for CHAIR-1"]
    deps.catalog_mismatch_alerted = False

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps

    result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "couldn't confirm exact price and availability" in result.lower()
    assert deps.catalog_mismatch_alerted is True
    mock_notify_mismatch.assert_awaited_once()
    mock_notify_manager.assert_awaited_once()
    mock_inventory.create_sale_order.assert_not_called()
