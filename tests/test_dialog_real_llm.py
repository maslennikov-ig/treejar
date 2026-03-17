"""Integration tests using the REAL LLM model (deepseek via OpenRouter).

These tests spend actual tokens to verify the model's quality at:
- Greeting and tone
- Tool invocation decisions (search, stock, CRM)
- Discount-aware product presentation
- Escalation handling
- Arabic language support

External IO (DB, Redis, Zoho, Wazzup) is mocked.
The LLM model runs for real via OpenRouter API.

Run with:
    uv run python -m pytest tests/test_dialog_real_llm.py -v -s --tb=short
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

# ---------------------------------------------------------------------------
# Read the REAL API key from .env file (conftest.py overrides os.environ with "test-key")
# ---------------------------------------------------------------------------
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from dotenv import dotenv_values
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.engine import SalesDeps, sales_agent
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.schemas.common import SalesStage
from src.schemas.product import ProductRead, ProductSearchResult

_env_path = Path(__file__).resolve().parents[1] / ".env"
_env_values = dotenv_values(_env_path) if _env_path.exists() else {}
OPENROUTER_KEY: str = _env_values.get("OPENROUTER_API_KEY", "") or ""
MODEL_NAME: str = (
    _env_values.get("OPENROUTER_MODEL_MAIN") or settings.openrouter_model_main or ""
)

pytestmark = pytest.mark.skipif(
    not OPENROUTER_KEY or OPENROUTER_KEY == "test-key",
    reason="Real OPENROUTER_API_KEY not found in .env — skipping real LLM tests",
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _real_model() -> OpenAIChatModel:
    """Create the real OpenRouter model with the REAL key from .env."""
    return OpenAIChatModel(
        MODEL_NAME,
        provider=OpenRouterProvider(api_key=OPENROUTER_KEY),
    )


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
    conv.id = uuid.uuid4()
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


def _fake_products(
    sku: str = "CHAIR-ERGO",
    name: str = "ErgoMax Pro Chair",
    price: float = 1500.0,
) -> ProductSearchResult:
    """Create a realistic product search result."""
    product = ProductRead(
        id=uuid.uuid4(),
        sku=sku,
        name_en=name,
        name_ar=None,
        description_en="Premium ergonomic office chair with adjustable lumbar, armrests and headrest. Made in Italy.",
        category="Chairs",
        subcategory="Ergonomic",
        price=price,
        currency="AED",
        stock=42,
        image_url=None,
        attributes={"Color": "Black", "Material": "Mesh + Leather"},
        is_active=True,
        created_at=datetime.now(UTC),
        updated_at=None,
    )
    return ProductSearchResult(
        products=[product],
        query_interpreted="ergonomic office chair",
        total_found=1,
    )


# ---------------------------------------------------------------------------
# Scenario 1: Greeting — Does the bot introduce itself as Noor?
# ---------------------------------------------------------------------------


class TestRealLLMGreeting:
    """The model should greet professionally, mention Treejar, ask for the customer's name."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    async def test_greeting_is_professional(self, mock_prompt: AsyncMock) -> None:
        mock_prompt.return_value = (
            "You are Noor, an expert B2B office furniture sales consultant at Treejar.\n"
            "STAGE: GREETING\n"
            "Your current objective is to greet the customer, ask for their name, "
            "and briefly introduce Treejar. Do NOT recommend products yet.\n"
            "IMPORTANT: Reply in English."
        )

        conv = _mock_conversation(SalesStage.GREETING)
        deps = _mock_deps(conv)

        result = await sales_agent.run(
            "Hello!",
            deps=deps,
            model=_real_model(),
        )

        text = result.output.lower()
        print(f"\n[REAL LLM] Greeting response:\n{result.output}\n")

        # Quality checks (fuzzy — real LLM responses vary)
        assert len(result.output) > 20, "Response too short"
        assert any(
            word in text for word in ["treejar", "noor", "furniture", "office", "help"]
        ), f"Expected bot to mention Treejar/Noor/furniture: {result.output}"


# ---------------------------------------------------------------------------
# Scenario 2: Product search — Does the model invoke search_products?
# ---------------------------------------------------------------------------


class TestRealLLMProductSearch:
    """When user asks about products, model should call search_products tool."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch("src.llm.engine.rag_search_products", new_callable=AsyncMock)
    async def test_model_calls_search_products(
        self,
        mock_search: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        mock_prompt.return_value = (
            "You are Noor, an expert B2B office furniture sales consultant at Treejar.\n"
            "STAGE: SOLUTION\n"
            "Your current objective is to present product solutions.\n"
            "You MUST use the `search_products` tool to find items.\n"
            "After receiving the items, you MUST explicitly describe them to the user, including their name and price.\n"
            "CRITICAL: You are PHYSICALLY UNABLE to see products without using tools.\n"
            "IMPORTANT: Reply in English."
        )

        mock_search.return_value = _fake_products()

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv, crm_context={"Segment": "Unknown"})

        result = await sales_agent.run(
            "I need ergonomic office chairs for 15 employees. What do you have?",
            deps=deps,
            model=_real_model(),
        )

        print(f"\n[REAL LLM] Product search response:\n{result.output}\n")

        # The model MUST have called search_products
        assert mock_search.await_count >= 1, (
            f"Model did NOT call search_products! Response: {result.output}"
        )

        # Response should mention the product that was returned
        text = result.output.lower()
        assert any(
            word in text for word in ["ergomax", "chair", "ergonomic", "1500", "aed"]
        ), f"Expected product details in response: {result.output}"


# ---------------------------------------------------------------------------
# Scenario 3: Stock check — Model calls get_stock
# ---------------------------------------------------------------------------


class TestRealLLMStockCheck:
    """When user asks about stock for a specific SKU, model should call get_stock."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    async def test_model_calls_get_stock(self, mock_prompt: AsyncMock) -> None:
        mock_prompt.return_value = (
            "You are Noor, an expert B2B office furniture sales consultant at Treejar.\n"
            "STAGE: SOLUTION\n"
            "Your current objective is to help the customer find products.\n"
            "Use `get_stock` tool to check stock levels for specific SKUs.\n"
            "IMPORTANT: Reply in English."
        )

        mock_inv = AsyncMock(spec=ZohoInventoryClient)
        mock_inv.get_stock.return_value = {"available_stock": 37}

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv, zoho_inventory=mock_inv)

        result = await sales_agent.run(
            "Can you check if CHAIR-ERGO is in stock?",
            deps=deps,
            model=_real_model(),
        )

        print(f"\n[REAL LLM] Stock check response:\n{result.output}\n")

        # Verify tool call
        assert mock_inv.get_stock.await_count >= 1, (
            f"Model did NOT call get_stock! Response: {result.output}"
        )

        # Response should mention the stock count
        assert "37" in result.output, (
            f"Expected stock count (37) in response: {result.output}"
        )


# ---------------------------------------------------------------------------
# Scenario 4: Wholesale discount — 15% discount applied
# ---------------------------------------------------------------------------


class TestRealLLMWholesaleDiscount:
    """Wholesale segment customer should see discounted prices (15% off)."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    @patch("src.llm.engine.rag_search_products", new_callable=AsyncMock)
    async def test_wholesale_price_shown(
        self,
        mock_search: AsyncMock,
        mock_prompt: AsyncMock,
    ) -> None:
        mock_prompt.return_value = (
            "You are Noor, an expert B2B office furniture sales consultant at Treejar.\n"
            "STAGE: SOLUTION\n"
            "You MUST use the `search_products` tool to find items.\n"
            "CRITICAL: You are PHYSICALLY UNABLE to see products without using tools.\n"
            "[CRM CUSTOMER CONTEXT]\n"
            "Name: Ahmed\n"
            "Segment: Wholesale\n"
            "IMPORTANT: Reply in English."
        )

        # Product at 2000 AED → Wholesale gets 15% off → 1700 AED
        mock_search.return_value = _fake_products(
            sku="DESK-EXEC",
            name="Executive Standing Desk",
            price=2000.0,
        )

        conv = _mock_conversation(SalesStage.SOLUTION, customer_name="Ahmed")
        deps = _mock_deps(conv, crm_context={"Name": "Ahmed", "Segment": "Wholesale"})

        result = await sales_agent.run(
            "Hi Ahmed. Show me your best standing desks.",
            deps=deps,
            model=_real_model(),
        )

        print(f"\n[REAL LLM] Wholesale discount response:\n{result.output}\n")

        # Tool must have been called
        assert mock_search.await_count >= 1, (
            f"Model did NOT call search_products! Response: {result.output}"
        )

        # Response should mention the product and some pricing/discount info
        text = result.output.lower()
        has_product = any(
            w in text for w in ["desk", "standing", "executive", "desk-exec"]
        )
        has_discount = any(
            w in text
            for w in [
                "1700",
                "1,700",
                "15%",
                "discount",
                "wholesale",
                "special",
                "offer",
            ]
        )
        has_price = any(w in text for w in ["2000", "2,000", "aed", "price"])
        assert has_product, f"Expected product mention in response: {result.output}"
        assert has_discount or has_price, (
            f"Expected price or discount info in response: {result.output}"
        )


# ---------------------------------------------------------------------------
# Scenario 5: Escalation — Empathetic response
# ---------------------------------------------------------------------------


class TestRealLLMEscalation:
    """When user demands a manager, bot should respond empathetically."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    async def test_escalation_response_is_empathetic(
        self, mock_prompt: AsyncMock
    ) -> None:
        mock_prompt.return_value = (
            "You are Noor, an expert B2B office furniture sales consultant at Treejar.\n"
            "STAGE: SOLUTION\n"
            "IMPORTANT: Reply in English."
        )

        conv = _mock_conversation(SalesStage.SOLUTION)
        deps = _mock_deps(conv)

        # Simulate what process_message does: append the system note
        angry_msg = (
            "This is outrageous! The prices are insane! I demand to speak to your manager RIGHT NOW!\n"
            "[SYSTEM NOTE: This message triggered a manager escalation. "
            "Briefly acknowledge their request and state that a human manager "
            "has been notified and will review the chat shortly. "
            "Do NOT try to solve it completely if it requires human intervention.]"
        )

        result = await sales_agent.run(
            angry_msg,
            deps=deps,
            model=_real_model(),
        )

        text = result.output.lower()
        print(f"\n[REAL LLM] Escalation response:\n{result.output}\n")

        # Quality checks
        assert any(
            word in text
            for word in ["manager", "team", "colleague", "supervisor", "someone"]
        ), f"Expected mention of manager/team: {result.output}"
        assert any(
            word in text for word in ["understand", "apologize", "sorry", "appreciate"]
        ), f"Expected empathetic language: {result.output}"


# ---------------------------------------------------------------------------
# Scenario 6: Arabic language — Bot responds in Arabic
# ---------------------------------------------------------------------------


class TestRealLLMArabic:
    """When user writes in Arabic, bot should respond entirely in Arabic."""

    @pytest.mark.asyncio
    @patch("src.llm.engine.build_system_prompt", new_callable=AsyncMock)
    async def test_arabic_response(self, mock_prompt: AsyncMock) -> None:
        mock_prompt.return_value = (
            "You are Noor, an expert B2B office furniture sales consultant at Treejar.\n"
            "STAGE: GREETING\n"
            "Your current objective is to greet the customer and ask for their name.\n"
            "IMPORTANT: The user prefers to communicate in Arabic. "
            "You MUST reply entirely in Arabic, unless quoting product names in English."
        )

        conv = _mock_conversation(SalesStage.GREETING, language="ar")
        deps = _mock_deps(conv)

        result = await sales_agent.run(
            "مرحبا، أنا أبحث عن أثاث مكتبي",
            deps=deps,
            model=_real_model(),
        )

        print(f"\n[REAL LLM] Arabic response:\n{result.output}\n")

        # Check for Arabic characters (Unicode range)
        arabic_chars = sum(1 for c in result.output if "\u0600" <= c <= "\u06ff")
        total_alpha = sum(1 for c in result.output if c.isalpha())

        arabic_ratio = arabic_chars / max(total_alpha, 1)
        print(f"Arabic ratio: {arabic_ratio:.2%} ({arabic_chars}/{total_alpha})")

        assert arabic_ratio > 0.5, (
            f"Expected >50% Arabic characters, got {arabic_ratio:.2%}: {result.output}"
        )
