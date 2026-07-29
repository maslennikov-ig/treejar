from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from pydantic_ai import RunContext

from src.llm.engine import (
    QuotationItem,
    SalesDeps,
    _build_inventory_contact_payload,
    create_quotation,
    resolve_inventory_customer_id,
)
from src.models.conversation import Conversation


def _quote_metadata(
    *,
    name: str = "Test Customer",
    company: str = "Test Trading LLC",
    address: str = "Dubai Marina, Tower A",
    customer_type: str | None = None,
) -> dict[str, dict[str, str]]:
    details = {
        "name": name,
        "company": company,
        "email": "test@example.com",
        "phone": "+1234567890",
        "address": address,
    }
    if customer_type:
        details["customer_type"] = customer_type
    return {"quote_customer_details": details}


def test_inventory_contact_payload_preserves_delivery_address() -> None:
    payload = _build_inventory_contact_payload(
        phone="+971501234567",
        customer_name="Fatima Noor Test",
        customer_email="fatima@example.com",
        customer_company="Cedarline E2E 20260728",
        customer_address="Office 1204, Test Tower, Business Bay, Dubai, UAE",
    )

    assert payload["billing_address"]["address"] == (
        "Office 1204, Test Tower, Business Bay, Dubai, UAE"
    )
    assert payload["shipping_address"] == payload["billing_address"]


def _quotation_idempotency_context() -> tuple[MagicMock, AsyncMock, AsyncMock]:
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
    mock_inventory.create_sale_order.side_effect = [
        {
            "saleorder": {
                "salesorder_id": "so-123",
                "salesorder_number": "SA-001",
                "status": "draft",
            }
        },
        {
            "saleorder": {
                "salesorder_id": "so-124",
                "salesorder_number": "SA-002",
                "status": "draft",
            }
        },
        {
            "saleorder": {
                "salesorder_id": "so-125",
                "salesorder_number": "SA-003",
                "status": "draft",
            }
        },
    ]
    mock_inventory.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-001",
        "contact_type": "customer",
        "status": "active",
    }

    mock_messaging = AsyncMock()
    mock_messaging.send_media.side_effect = [
        "media-quotation-1",
        "media-quotation-2",
        "media-quotation-3",
    ]
    mock_conversation = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        language="en",
        escalation_status="none",
        metadata_=_quote_metadata(),
    )
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.messaging_client = mock_messaging
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = AsyncMock()
    deps.db = mock_db
    deps.zoho_crm = None
    deps.source_message_id = "provider-message-1"

    ctx = MagicMock(spec=RunContext)
    ctx.deps = deps
    return ctx, mock_inventory, mock_messaging


@pytest.mark.asyncio
async def test_create_quotation_reuses_effect_for_same_source_message() -> None:
    ctx, mock_inventory, mock_messaging = _quotation_idempotency_context()

    with (
        patch(
            "src.services.pdf.generator.generate_pdf",
            new_callable=AsyncMock,
            return_value=b"pdf_data",
        ),
        patch(
            "src.services.pdf.generator.render_quotation_html",
            return_value="<html>",
        ),
    ):
        first = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        retry = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "SA-001" in first
    assert "SA-001" in retry
    assert mock_inventory.create_sale_order.await_count == 1
    assert mock_messaging.send_media.await_count == 1


@pytest.mark.asyncio
async def test_create_quotation_creates_new_effect_for_distinct_source_message() -> (
    None
):
    ctx, mock_inventory, mock_messaging = _quotation_idempotency_context()

    with (
        patch(
            "src.services.pdf.generator.generate_pdf",
            new_callable=AsyncMock,
            return_value=b"pdf_data",
        ),
        patch(
            "src.services.pdf.generator.render_quotation_html",
            return_value="<html>",
        ),
    ):
        first = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        ctx.deps.source_message_id = "provider-message-2"
        second = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        ctx.deps.source_message_id = "provider-message-1"
        first_retry_after_second = await create_quotation(
            ctx, [QuotationItem(sku="CHAIR-1", quantity=1)]
        )

    assert "SA-001" in first
    assert "SA-002" in second
    assert "SA-001" in first_retry_after_second
    assert mock_inventory.create_sale_order.await_count == 2
    assert mock_messaging.send_media.await_count == 2


@pytest.mark.asyncio
async def test_create_quotation_does_not_reuse_legacy_effect_for_real_message() -> None:
    ctx, mock_inventory, mock_messaging = _quotation_idempotency_context()
    ctx.deps.conversation.metadata_["quotation_effect"] = {
        "version": 1,
        "fingerprint": (
            "65b4286aac5084606f30974cbabc9944c0c20c72b1e7d42233fcd4b8955ff460"
        ),
        "customer_id": "inventory-contact-001",
        "sale_order_id": "so-legacy",
        "sale_order_number": "SA-LEGACY",
        "status": "pdf_sent",
    }

    with (
        patch(
            "src.services.pdf.generator.generate_pdf",
            new_callable=AsyncMock,
            return_value=b"pdf_data",
        ),
        patch(
            "src.services.pdf.generator.render_quotation_html",
            return_value="<html>",
        ),
    ):
        result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "SA-001" in result
    assert "SA-LEGACY" not in result
    assert mock_inventory.create_sale_order.await_count == 1
    assert mock_messaging.send_media.await_count == 1


@pytest.mark.asyncio
async def test_create_quotation_retry_after_lost_response_sends_pdf_once() -> None:
    ctx, mock_inventory, mock_messaging = _quotation_idempotency_context()
    mock_inventory.get_sale_order.return_value = {
        "saleorder": {
            "salesorder_id": "so-123",
            "salesorder_number": "SA-001",
            "status": "draft",
        }
    }
    mock_messaging.send_media.side_effect = TimeoutError("provider response lost")
    customer_visible_dispatches: set[str] = set()
    dispatch_attempts: list[str] = []

    async def audited_send_side_effect(
        db: AsyncMock,
        **kwargs: object,
    ) -> SimpleNamespace:
        effect = ctx.deps.conversation.metadata_["quotation_effect"]
        assert effect["status"] == "pdf_sending"
        assert db.commit.await_count >= 1
        crm_message_id = str(kwargs["crm_message_id"])
        dispatch_attempts.append(crm_message_id)
        if crm_message_id not in customer_visible_dispatches:
            customer_visible_dispatches.add(crm_message_id)
            raise TimeoutError("provider accepted PDF but response was lost")
        if len(dispatch_attempts) == 2:
            request = httpx.Request("POST", "https://api.wazzup24.com/v3/message")
            response = httpx.Response(
                400,
                json={"error": "repeatedCrmMessageId"},
                request=request,
            )
            raise httpx.HTTPStatusError(
                "duplicate provider operation",
                request=request,
                response=response,
            )
        return SimpleNamespace(
            media=SimpleNamespace(provider_message_id="provider-pdf-1"),
            skipped=True,
        )

    with (
        patch(
            "src.services.pdf.generator.generate_pdf",
            new_callable=AsyncMock,
            return_value=b"pdf_data",
        ),
        patch(
            "src.services.pdf.generator.render_quotation_html",
            return_value="<html>",
        ),
        patch(
            "src.services.outbound_audit.send_wazzup_media_with_audit",
            new_callable=AsyncMock,
            side_effect=audited_send_side_effect,
        ),
        patch(
            "src.integrations.notifications.escalation.notify_manager_escalation",
            new_callable=AsyncMock,
        ),
    ):
        first = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])
        retry = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "SA-001" not in first
    assert "SA-001" in retry
    assert len(customer_visible_dispatches) == 1
    assert len(dispatch_attempts) == 3
    assert len(set(dispatch_attempts)) == 1
    assert "provider-message-1" not in dispatch_attempts[0]
    assert mock_inventory.create_sale_order.await_count == 1
    assert ctx.deps.conversation.metadata_["quotation_effect"]["status"] == "pdf_sent"
    mock_messaging.send_media.assert_not_awaited()


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
        "saleorder": {
            "salesorder_id": "so-123",
            "salesorder_number": "SA-001",
            "status": "draft",
        }
    }
    mock_inventory.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-001",
        "contact_type": "customer",
        "status": "active",
    }

    mock_messaging = AsyncMock()
    mock_messaging.send_media.return_value = "media-quotation-1"
    mock_conversation = MagicMock(spec=Conversation)
    mock_conversation.id = "00000000-0000-0000-0000-000000000001"
    mock_conversation.phone = "+1234567890"
    mock_conversation.customer_name = "Test Customer"
    mock_conversation.metadata_ = _quote_metadata()

    # Redis must be AsyncMock (not MagicMock) for setex to be awaitable
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(
        sku="CHAIR-1",
        price=150.0,
        currency="AED",
        image_url="https://cdn.treejar.test/chair-1.jpg",
    )
    mock_db.execute.return_value = execute_result

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

    mock_http_client = AsyncMock()
    mock_http_response = MagicMock()
    mock_http_response.content = b"catalog-image-bytes"
    mock_http_response.headers = {"content-type": "image/jpeg"}
    mock_http_response.raise_for_status = MagicMock()
    mock_http_client.get.return_value = mock_http_response
    mock_http_client_cm = MagicMock()
    mock_http_client_cm.__aenter__ = AsyncMock(return_value=mock_http_client)
    mock_http_client_cm.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "src.services.pdf.generator.generate_pdf", new_callable=AsyncMock
        ) as mock_pdf,
        patch(
            "src.services.pdf.generator.render_quotation_html", return_value="<html>"
        ) as mock_render,
        patch("src.llm.engine.httpx.AsyncClient", return_value=mock_http_client_cm),
    ):
        mock_pdf.return_value = b"pdf_data"
        result = await create_quotation(ctx, items)
        repeated_result = await create_quotation(ctx, items)

    assert "SA-001" in result
    assert "SA-001" in repeated_result

    # Verify Inventory calls
    assert mock_inventory.get_stock_bulk.await_count == 2
    mock_inventory.get_stock_bulk.assert_awaited_with(["CHAIR-1"])
    mock_inventory.create_sale_order.assert_called_once()
    _, kwargs = mock_inventory.create_sale_order.call_args
    assert kwargs["customer_id"] == "inventory-contact-001"
    assert kwargs["status"] == "draft"
    assert kwargs["items"][0]["item_id"] == "123"
    assert kwargs["items"][0]["quantity"] == 2

    mock_inventory.get_item_image.assert_not_awaited()
    mock_http_client.get.assert_awaited_once_with(
        "https://cdn.treejar.test/chair-1.jpg"
    )
    render_context = mock_render.call_args.args[0]
    assert render_context["items"][0]["image_url"].startswith("data:image/jpeg;base64,")
    assert mock_conversation.metadata_["zoho_sale_order_id"] == "so-123"
    assert mock_conversation.metadata_["zoho_sale_order_number"] == "SA-001"
    assert mock_conversation.metadata_["quotation_effect"]["version"] == 2
    assert mock_conversation.metadata_["quotation_effect"]["status"] == "pdf_sent"
    proposal_state = mock_conversation.metadata_["proposal_followup"]
    assert proposal_state["kp_message_id"] == "media-quotation-1"
    assert proposal_state["kp_read"] is False
    assert set(proposal_state["steps"]) == {"1", "2", "3"}

    # Verify PDF generation was called
    mock_pdf.assert_called_once()

    mock_redis.setex.assert_not_awaited()
    mock_notify.assert_not_awaited()
    mock_messaging.send_media.assert_awaited_once()
    assert mock_messaging.send_media.await_args.kwargs["chat_id"] == "+1234567890"
    assert mock_messaging.send_media.await_args.kwargs["content"] == b"pdf_data"
    assert (
        mock_messaging.send_media.await_args.kwargs["content_type"] == "application/pdf"
    )
    assert (
        mock_messaging.send_media.await_args.kwargs["caption"]
        == "Your Treejar quotation: SA-001"
    )


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_skips_pdf_image_when_catalog_image_missing(
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
    mock_inventory.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-001",
        "contact_type": "customer",
        "status": "active",
    }

    mock_conversation = MagicMock(spec=Conversation)
    mock_conversation.id = "00000000-0000-0000-0000-000000000001"
    mock_conversation.phone = "+1234567890"
    mock_conversation.customer_name = "Test Customer"
    mock_conversation.metadata_ = _quote_metadata()

    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()

    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(
        sku="CHAIR-1",
        price=150.0,
        currency="AED",
        image_url=None,
    )
    mock_db.execute.return_value = execute_result

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    mock_messaging = AsyncMock()
    deps.messaging_client = mock_messaging
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
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

    with (
        patch(
            "src.services.pdf.generator.generate_pdf", new_callable=AsyncMock
        ) as mock_pdf,
        patch(
            "src.services.pdf.generator.render_quotation_html", return_value="<html>"
        ) as mock_render,
    ):
        mock_pdf.return_value = b"pdf_data"
        result = await create_quotation(ctx, [QuotationItem(sku="CHAIR-1", quantity=1)])

    assert "SA-001" in result
    mock_inventory.get_item_image.assert_not_awaited()
    render_context = mock_render.call_args.args[0]
    assert render_context["items"][0]["image_url"] is None
    mock_notify.assert_not_awaited()
    mock_redis.setex.assert_not_awaited()
    mock_messaging.send_media.assert_awaited_once()


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_preserves_real_sale_order_identifiers_from_flat_response(
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
        "salesorder_id": "so-flat-123",
        "salesorder_number": "SA-REAL-001",
        "status": "draft",
    }
    mock_inventory.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-001",
        "contact_type": "customer",
        "status": "active",
    }

    mock_conversation = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        language="ar-AE",
        metadata_=_quote_metadata(),
    )
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    mock_messaging = AsyncMock()
    deps.messaging_client = mock_messaging
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = {
        "id": "crm-contact-001",
        "First_Name": "Test",
        "Last_Name": "Customer",
        "Email": "test@example.com",
        "Account_Name": {"name": "Treejar Trading"},
    }

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

    assert "SA-REAL-001" in result
    assert mock_conversation.metadata_["zoho_sale_order_id"] == "so-flat-123"
    assert mock_conversation.metadata_["zoho_sale_order_number"] == "SA-REAL-001"
    assert mock_conversation.metadata_["proposal_followup"]["kp_read"] is False
    assert mock_db.flush.await_count >= 2

    mock_redis.setex.assert_not_awaited()
    mock_notify.assert_not_awaited()
    mock_messaging.send_media.assert_awaited_once()
    assert (
        mock_messaging.send_media.await_args.kwargs["caption"]
        == "عرض السعر من Treejar: SA-REAL-001"
    )


@pytest.mark.asyncio
@patch(
    "src.integrations.notifications.escalation.notify_manager_escalation",
    new_callable=AsyncMock,
)
async def test_create_quotation_keeps_draft_only_when_sale_order_number_missing(
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
        "salesorder": {"salesorder_id": "so-nonumber-123", "status": "draft"}
    }
    mock_inventory.find_customer_by_phone.return_value = {
        "contact_id": "inventory-contact-001",
        "contact_type": "customer",
        "status": "active",
    }

    mock_conversation = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        metadata_=_quote_metadata(),
    )
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = execute_result

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    mock_messaging = AsyncMock()
    deps.messaging_client = mock_messaging
    deps.conversation = mock_conversation
    deps.crm_context = None
    deps.redis = mock_redis
    deps.db = mock_db
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = {
        "id": "crm-contact-001",
        "First_Name": "Test",
        "Last_Name": "Customer",
        "Email": "test@example.com",
        "Account_Name": {"name": "Treejar Trading"},
    }

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

    assert "Quotation DRAFT" in result
    assert mock_conversation.metadata_["zoho_sale_order_id"] == "so-nonumber-123"
    assert "zoho_sale_order_number" not in mock_conversation.metadata_

    mock_redis.setex.assert_not_awaited()
    mock_notify.assert_not_awaited()
    mock_messaging.send_media.assert_awaited_once()
    assert (
        mock_messaging.send_media.await_args.kwargs["caption"]
        == "Your Treejar quotation: DRAFT"
    )


@pytest.mark.asyncio
async def test_create_quotation_sku_not_found() -> None:
    mock_inventory = AsyncMock()
    mock_inventory.get_stock_bulk.return_value = []  # SKU not found
    mock_inventory.get_stock.return_value = None

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    deps.conversation = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        metadata_=_quote_metadata(),
    )
    deps.crm_context = None
    deps.zoho_crm = AsyncMock()
    deps.zoho_crm.find_contact_by_phone.return_value = None
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
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        metadata_=_quote_metadata(company="", customer_type="individual"),
    )
    mock_redis = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_db = AsyncMock()
    mock_db.flush = AsyncMock()

    deps = MagicMock(spec=SalesDeps)
    deps.zoho_inventory = mock_inventory
    mock_messaging = AsyncMock()
    deps.messaging_client = mock_messaging
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
    mock_notify.assert_not_awaited()
    mock_messaging.send_media.assert_awaited_once()


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
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        escalation_status="none",
        metadata_=_quote_metadata(),
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
async def test_resolve_inventory_customer_id_strips_synthetic_suffix_for_zoho() -> None:
    mock_inventory = AsyncMock()
    mock_inventory.find_customer_by_phone.return_value = None
    mock_inventory.find_customer_by_email.return_value = None
    mock_inventory.create_contact.return_value = {
        "contact_id": "created-inventory-contact",
        "contact_type": "customer",
        "status": "active",
    }

    result = await resolve_inventory_customer_id(
        phone="+15550001111#tj-8ma2-salesorder-mixed-20260526-200552",
        customer_name="Lilia",
        customer_email="Lfdsf@kfsl.ru",
        customer_company="LLD",
        zoho_inventory=mock_inventory,
    )

    assert result == "created-inventory-contact"
    mock_inventory.find_customer_by_phone.assert_awaited_once_with("+15550001111")
    payload = mock_inventory.create_contact.await_args.args[0]
    assert payload["contact_persons"][0]["phone"] == "+15550001111"
    assert payload["contact_persons"][0]["mobile"] == "+15550001111"


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
        phone="+15550001111",
        customer_name="None Игорь",
        customer_email="",
        customer_company="None Игорь",
        zoho_inventory=mock_inventory,
    )

    assert result == "existing-inventory-contact"


@pytest.mark.asyncio
async def test_resolve_inventory_customer_id_reactivates_exact_inactive_duplicate() -> (
    None
):
    duplicate_response = httpx.Response(
        400,
        json={
            "code": 3062,
            "message": "The customer already exists.",
        },
        request=httpx.Request("POST", "https://example.com/contacts"),
    )
    inactive_contact = {
        "contact_id": "inactive-inventory-contact",
        "contact_name": "Example QA",
        "company_name": "Example QA",
        "contact_type": "customer",
        "status": "inactive",
        "billing_address": {"address": "Test Tower, Dubai, UAE"},
        "shipping_address": {"address": "Test Tower, Dubai, UAE"},
        "contact_persons": [
            {
                "first_name": "Test",
                "last_name": "Owner",
                "email": "owner@example.com",
                "phone": "+15550001111",
                "mobile": "+15550001111",
            }
        ],
    }
    active_contact = {
        **inactive_contact,
        "status": "active",
        "billing_address": {"address": "Test Tower, Dubai, UAE"},
        "shipping_address": {"address": "Test Tower, Dubai, UAE"},
        "contact_persons": [
            {
                "first_name": "Test",
                "last_name": "Owner",
                "email": "owner@example.com",
                "phone": "+15550001111",
                "mobile": "+15550001111",
            }
        ],
    }

    mock_inventory = AsyncMock()
    mock_inventory.find_customer_by_phone.return_value = None
    mock_inventory.find_customer_by_email.return_value = None
    mock_inventory.find_inactive_customer_by_email.return_value = inactive_contact
    mock_inventory.create_contact.side_effect = httpx.HTTPStatusError(
        "duplicate contact",
        request=duplicate_response.request,
        response=duplicate_response,
    )
    mock_inventory.get_contact.return_value = active_contact

    result = await resolve_inventory_customer_id(
        phone="+15550001111",
        customer_name="Test Owner",
        customer_email="owner@example.com",
        customer_company="Example QA",
        customer_address="Test Tower, Dubai, UAE",
        zoho_inventory=mock_inventory,
    )

    assert result == "inactive-inventory-contact"
    mock_inventory.find_inactive_customer_by_email.assert_awaited_once_with(
        "owner@example.com"
    )
    mock_inventory.activate_contact.assert_awaited_once_with(
        "inactive-inventory-contact"
    )
    mock_inventory.get_contact.assert_awaited_once_with("inactive-inventory-contact")


@pytest.mark.asyncio
async def test_resolve_inventory_customer_id_rejects_stale_reactivated_readback() -> (
    None
):
    duplicate_response = httpx.Response(
        400,
        json={"code": 3062, "message": "The customer already exists."},
        request=httpx.Request("POST", "https://example.com/contacts"),
    )
    mock_inventory = AsyncMock()
    mock_inventory.find_customer_by_phone.return_value = None
    mock_inventory.find_customer_by_email.return_value = None
    mock_inventory.find_inactive_customer_by_email.return_value = {
        "contact_id": "inactive-inventory-contact",
        "contact_type": "customer",
        "status": "inactive",
    }
    mock_inventory.create_contact.side_effect = httpx.HTTPStatusError(
        "duplicate contact",
        request=duplicate_response.request,
        response=duplicate_response,
    )
    mock_inventory.get_contact.return_value = {
        "contact_id": "inactive-inventory-contact",
        "contact_type": "customer",
        "status": "active",
        "company_name": "Example QA",
        "billing_address": {"address": "stale address"},
        "shipping_address": {"address": "stale address"},
        "contact_persons": [{"email": "owner@example.com"}],
    }

    result = await resolve_inventory_customer_id(
        phone="+15550001111",
        customer_name="Test Owner",
        customer_email="owner@example.com",
        customer_company="Example QA",
        customer_address="Test Tower, Dubai, UAE",
        zoho_inventory=mock_inventory,
    )

    assert result is None
    mock_inventory.activate_contact.assert_not_awaited()
    mock_inventory.get_contact.assert_not_awaited()


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
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        metadata_=_quote_metadata(),
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
        id="00000000-0000-0000-0000-000000000001",
        phone="+1234567890",
        customer_name="Test Customer",
        metadata_=_quote_metadata(),
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
