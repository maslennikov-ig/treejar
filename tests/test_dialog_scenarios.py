"""Realistic multi-turn dialog quality tests for the AI Sales Bot.

Uses pydantic-ai's FunctionModel to control tool invocations and verify
that the full `sales_agent.run()` pipeline works correctly with mocked
external services but real tool function logic.

Scenarios:
  1. Happy Path: New customer asking about office chairs (GREETING → SOLUTION)
  2. Wholesale CRM: Known client with 15% discount applied via CRM context
  3. Quotation Flow: Customer requests a PDF quote for specific SKUs
  4. Escalation: Aggressive customer triggers manager notification
"""

from __future__ import annotations

from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.engine import SalesDeps, sales_agent
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conversation(
    stage: SalesStage = SalesStage.GREETING,
    phone: str = "+971501234567",
    customer_name: str | None = None,
    language: str = "en",
) -> Any:
    conv = MagicMock(spec=Conversation)
    conv.phone = phone
    conv.sales_stage = stage.value
    conv.language = language
    conv.customer_name = customer_name
    conv.escalation_status = "none"
    conv.zoho_contact_id = None
    conv.zoho_deal_id = None
    conv.id = "test-conv-id"
    return conv


def _mock_deps(
    conv: Any,
    *,
    crm_context: dict[str, Any] | None = None,
    zoho_inventory: Any = None,
    zoho_crm: Any = None,
    messaging_client: Any = None,
) -> SalesDeps:
    return SalesDeps(
        db=AsyncMock(spec=AsyncSession),
        redis=AsyncMock(spec=Redis),
        conversation=conv,
        embedding_engine=AsyncMock(spec=EmbeddingEngine),
        zoho_inventory=zoho_inventory or AsyncMock(spec=ZohoInventoryClient),
        zoho_crm=zoho_crm or AsyncMock(spec=ZohoCRMClient),
        messaging_client=messaging_client or AsyncMock(spec=MessagingProvider),
        pii_map={},
        crm_context=crm_context,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Happy Path — New customer asks about office chairs
# ---------------------------------------------------------------------------


class TestScenario1HappyPath:
    """Simulate a new customer who wants office chairs.

    Turn 1: Customer greets and asks about chairs → bot should call advance_stage
    Turn 2: Bot searches products → search_products tool called
    """

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    async def test_greeting_triggers_advance_stage(
        self, mock_prompt: AsyncMock
    ) -> None:
        """When user says hi and mentions a need, bot should advance to qualifying."""
        mock_prompt.return_value = "You are Noor, a B2B furniture consultant."

        tool_calls_made: list[str] = []

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            # First call: advance the stage
            if len(messages) == 1:
                tool_calls_made.append("advance_stage")
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "advance_stage",
                            {"next_stage": "qualifying"},
                        )
                    ]
                )
            # After tool return: respond with text
            return ModelResponse(
                parts=[
                    TextPart(
                        "Hello! Welcome to Treejar. I'd be happy to help you find "
                        "the right office chairs. Could you tell me a bit about your "
                        "company and how many seats you need?"
                    )
                ]
            )

        conv = _mock_conversation(SalesStage.GREETING)
        deps = _mock_deps(conv)

        with sales_agent.override(model=FunctionModel(model_fn)):
            result = await sales_agent.run(
                "Hi! I'm looking for office chairs for my team",
                deps=deps,
            )

        assert "advance_stage" in tool_calls_made
        assert conv.sales_stage == SalesStage.QUALIFYING.value
        assert "chair" in result.output.lower() or "help" in result.output.lower()

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch("src.llm.engine.rag_search_products", new_callable=AsyncMock)
    async def test_search_products_called_on_query(
        self,
        mock_search: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        """When user asks to see products, bot must call search_products tool."""
        mock_prompt.return_value = "You are Noor. STAGE: SOLUTION."

        from src.schemas.product import ProductSearchResult

        mock_search.return_value = ProductSearchResult(
            products=[], query_interpreted="ergonomic chairs", total_found=0
        )

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if len(messages) == 1:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "search_products",
                            {"query": "ergonomic chairs under 2000 AED"},
                        )
                    ]
                )
            return ModelResponse(
                parts=[
                    TextPart(
                        "I searched our catalog but couldn't find exact matches. "
                        "Let me check some alternatives for you."
                    )
                ]
            )

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv)

        with sales_agent.override(model=FunctionModel(model_fn)):
            result = await sales_agent.run(
                "Show me ergonomic chairs under 2000 AED",
                deps=deps,
            )

        mock_search.assert_awaited_once()
        assert "search" in result.output.lower() or "catalog" in result.output.lower()


# ---------------------------------------------------------------------------
# Scenario 2: Wholesale CRM client — discount applied
# ---------------------------------------------------------------------------


class TestScenario2WholesaleDiscount:
    """Known Wholesale client gets 15% discount on product prices."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch("src.llm.engine.rag_search_products", new_callable=AsyncMock)
    async def test_wholesale_segment_gets_discounted_price(
        self,
        mock_search: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        """Wholesale segment prices should reflect 15% discount in tool output."""
        mock_prompt.return_value = "You are Noor. STAGE: SOLUTION."

        import uuid
        from datetime import datetime

        from src.schemas.product import ProductRead, ProductSearchResult

        product = ProductRead(
            id=uuid.uuid4(),
            sku="RDESK-01",
            name_en="Executive Reception Desk",
            name_ar=None,
            description_en="A large premium reception desk",
            category="Desks",
            subcategory=None,
            price=5000.0,
            currency="AED",
            stock=25,
            image_url=None,
            attributes=None,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=None,
        )
        mock_search.return_value = ProductSearchResult(
            products=[product],
            query_interpreted="reception desks",
            total_found=1,
        )

        tool_outputs: list[str] = []

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if len(messages) == 1:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "search_products",
                            {"query": "reception desks"},
                        )
                    ]
                )
            # Capture the tool return to verify discount
            last_msg = messages[-1]
            for part in last_msg.parts:
                if hasattr(part, "content") and isinstance(part.content, str):
                    tool_outputs.append(part.content)

            return ModelResponse(
                parts=[
                    TextPart(
                        "I found the Executive Reception Desk at a special "
                        "wholesale price. Would you like a formal quotation?"
                    )
                ]
            )

        conv = _mock_conversation(SalesStage.SOLUTION, customer_name="Ahmed")
        deps = _mock_deps(conv, crm_context={"Name": "Ahmed", "Segment": "Wholesale"})

        with sales_agent.override(model=FunctionModel(model_fn)):
            _result = await sales_agent.run(
                "I need 50 reception desks for our hotels",
                deps=deps,
            )

        # 5000 * 0.85 = 4250.00
        assert any("4250.00" in output for output in tool_outputs), (
            f"Expected discounted price 4250.00 in tool outputs: {tool_outputs}"
        )


# ---------------------------------------------------------------------------
# Scenario 3: Quotation Flow — Customer asks for a PDF quote
# ---------------------------------------------------------------------------


class TestScenario3QuotationFlow:
    """Customer confirms items and requests a quotation PDF."""

    @pytest.mark.asyncio
    @patch(
        "src.integrations.notifications.escalation.notify_manager_escalation",
        new_callable=AsyncMock,
    )
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch(
        "src.services.pdf.generator.render_quotation_html",
        return_value="<html>QUOTE</html>",
    )
    @patch("src.services.pdf.generator.generate_pdf", new_callable=AsyncMock)
    async def test_quotation_generates_and_sends_pdf(
        self,
        mock_gen_pdf: AsyncMock,
        mock_render: AsyncMock,
        mock_prompt: AsyncMock,
        mock_notify: AsyncMock,
    ) -> None:
        """When customer asks for a quote, bot should call create_quotation and send PDF."""
        mock_prompt.return_value = "You are Noor. STAGE: QUOTING."
        mock_gen_pdf.return_value = b"%PDF-fake-content"

        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock_bulk.return_value = [
            {
                "sku": "CHAIR-01",
                "item_id": "zoho_001",
                "rate": 800.0,
                "name": "Executive Chair",
                "description": "Premium ergonomic chair",
                "image_document_id": None,
            },
        ]
        mock_inv.create_sale_order.return_value = {
            "saleorder": {"salesorder_number": "SO-TEST-001"},
        }

        mock_messaging = AsyncMock(spec=MessagingProvider)

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if len(messages) == 1:
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "create_quotation",
                            {"items": [{"sku": "CHAIR-01", "quantity": 3}]},
                        )
                    ]
                )
            return ModelResponse(
                parts=[
                    TextPart(
                        "I've generated your quotation SO-TEST-001 and sent it "
                        "to your WhatsApp. Please check!"
                    )
                ]
            )

        conv = _mock_conversation(
            SalesStage.QUOTING, customer_name="Sarah", phone="+971509876543"
        )

        # Redis must be AsyncMock for setex/get (not MagicMock from spec=Redis)
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()

        deps = _mock_deps(
            conv,
            zoho_inventory=mock_inv,
            messaging_client=mock_messaging,
            crm_context={"Segment": "Unknown"},
        )
        deps.redis = mock_redis

        with sales_agent.override(model=FunctionModel(model_fn)):
            result = await sales_agent.run(
                "Can you send me a quote for 3 CHAIR-01?",
                deps=deps,
            )

        # Verify PDF pipeline
        mock_inv.get_stock_bulk.assert_awaited_once()
        mock_inv.create_sale_order.assert_awaited_once()
        mock_gen_pdf.assert_awaited_once()
        # New flow: PDF stored in Redis + escalation, not direct send_media
        mock_redis.setex.assert_awaited()
        mock_notify.assert_awaited_once()

        assert "SO-TEST-001" in result.output


# ---------------------------------------------------------------------------
# Scenario 4: Escalation — Angry customer triggers manager notification
# ---------------------------------------------------------------------------


class TestScenario4Escalation:
    """Customer message that warrants escalation should trigger the tool."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch(
        "src.integrations.notifications.escalation.notify_manager_escalation",
        new_callable=AsyncMock,
    )
    async def test_escalation_via_tool(
        self,
        mock_notify: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        """When agent calls escalate_to_manager tool, manager is notified."""
        mock_prompt.return_value = "You are Noor. STAGE: SOLUTION."

        tool_calls_made: list[str] = []

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            if len(messages) == 1:
                tool_calls_made.append("escalate_to_manager")
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "escalate_to_manager",
                            {
                                "reason": "Customer demanded to speak with manager",
                                "escalation_type": "human_requested",
                            },
                        )
                    ]
                )
            return ModelResponse(
                parts=[
                    TextPart(
                        "I completely understand your frustration, and I apologize. "
                        "I've notified our manager who will review this conversation "
                        "and reach out to you shortly."
                    )
                ]
            )

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv)
        deps.recent_history = ["user: Let me speak to your manager NOW!"]

        with sales_agent.override(model=FunctionModel(model_fn)):
            result = await sales_agent.run(
                "This is ridiculous! Let me speak to your manager NOW!",
                deps=deps,
            )

        # Tool was called
        assert "escalate_to_manager" in tool_calls_made

        # notify_manager_escalation was triggered
        mock_notify.assert_awaited_once()
        call_kwargs = mock_notify.call_args
        assert call_kwargs.kwargs["escalation_type"].value == "human_requested"

        # Bot response is empathetic and mentions escalation
        assert "manager" in result.output.lower()
        assert (
            "understand" in result.output.lower()
            or "apologize" in result.output.lower()
        )


# ---------------------------------------------------------------------------
# Scenario 5: Multi-tool chaining — Search → Stock check in one conversation
# ---------------------------------------------------------------------------


class TestScenario5MultiToolChaining:
    """Customer searches products then checks stock for a specific SKU."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch("src.llm.engine.rag_search_products", new_callable=AsyncMock)
    async def test_search_then_stock_check(
        self,
        mock_search: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        """Two tools called in sequence: search_products then get_stock."""
        mock_prompt.return_value = "You are Noor. STAGE: SOLUTION."

        import uuid
        from datetime import datetime

        from src.schemas.product import ProductRead, ProductSearchResult

        product = ProductRead(
            id=uuid.uuid4(),
            sku="ERGO-PRO",
            name_en="ErgoMax Pro Chair",
            name_ar=None,
            description_en="Premium ergonomic chair with lumbar support",
            category="Chairs",
            subcategory=None,
            price=1500.0,
            currency="AED",
            stock=42,
            image_url=None,
            attributes=None,
            is_active=True,
            created_at=datetime.now(UTC),
            updated_at=None,
        )
        mock_search.return_value = ProductSearchResult(
            products=[product],
            query_interpreted="ergonomic chairs",
            total_found=1,
        )

        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock.return_value = {"stock_on_hand": 42}

        call_count = 0

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            nonlocal call_count
            call_count += 1

            if call_count == 1:
                # First: search products
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "search_products",
                            {"query": "ergonomic chairs"},
                        )
                    ]
                )
            elif call_count == 2:
                # Second: check stock for the found product
                return ModelResponse(
                    parts=[ToolCallPart("get_stock", {"sku": "ERGO-PRO"})]
                )
            else:
                # Final: text response
                return ModelResponse(
                    parts=[
                        TextPart(
                            "Great news! The ErgoMax Pro Chair is available — "
                            "we have 42 units in stock. It's priced at 1,500 AED. "
                            "Would you like to proceed with a quotation?"
                        )
                    ]
                )

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv, zoho_inventory=mock_inv)

        with sales_agent.override(model=FunctionModel(model_fn)):
            result = await sales_agent.run(
                "Show me ergonomic chairs and check what's available",
                deps=deps,
            )

        # Both tools were called
        mock_search.assert_awaited_once()
        mock_inv.get_stock.assert_awaited_once_with("ERGO-PRO")
        assert "42" in result.output
        assert call_count == 3


# ---------------------------------------------------------------------------
# Scenario 6: Product-search cap — one retry allowed, third call removed
# ---------------------------------------------------------------------------


class TestScenario6ProductSearchCap:
    """Product search can retry once, then must continue without a third search."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch("src.llm.engine.rag_search_products", new_callable=AsyncMock)
    async def test_search_products_removed_after_second_empty_result(
        self,
        mock_search: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        mock_prompt.return_value = "You are Noor. STAGE: SOLUTION."

        from src.schemas.product import ProductSearchResult

        mock_search.return_value = ProductSearchResult(
            products=[],
            query_interpreted="acoustic pods",
            total_found=0,
        )

        tool_names_by_step: list[set[str]] = []
        model_calls = 0

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            nonlocal model_calls
            model_calls += 1
            tool_names = {tool.name for tool in info.function_tools}
            tool_names_by_step.append(tool_names)

            if model_calls == 1:
                assert "search_products" in tool_names
                return ModelResponse(
                    parts=[ToolCallPart("search_products", {"query": "acoustic pods"})]
                )

            if model_calls == 2:
                assert "search_products" in tool_names
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "search_products",
                            {"query": "phone booth acoustic office pod"},
                        )
                    ]
                )

            assert "search_products" not in tool_names
            return ModelResponse(
                parts=[
                    TextPart(
                        "I couldn't find an exact match in our catalog. "
                        "The closest fit is an acoustic privacy booth for calls "
                        "and one-person focus use."
                    )
                ]
            )

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv)

        with sales_agent.override(model=FunctionModel(model_fn)):
            result = await sales_agent.run(
                "Tell me about your acoustic pods",
                deps=deps,
            )

        assert mock_search.await_count == 2
        assert model_calls == 3
        assert "search_products" in tool_names_by_step[0]
        assert "search_products" in tool_names_by_step[1]
        assert "search_products" not in tool_names_by_step[2]
        assert "acoustic privacy booth" in result.output.lower()
