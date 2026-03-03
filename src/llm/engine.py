from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.context import build_message_history
from src.llm.pii import mask_pii, unmask_pii
from src.llm.prompts import build_system_prompt
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.rag.pipeline import search_products
from src.schemas.common import SalesStage
from src.schemas.product import ProductSearchQuery

logger = logging.getLogger(__name__)


@dataclass
class SalesDeps:
    db: AsyncSession
    redis: Any
    conversation: Conversation
    embedding_engine: EmbeddingEngine
    zoho_inventory: ZohoInventoryClient
    zoho_crm: ZohoCRMClient | None
    messaging_client: MessagingProvider
    pii_map: dict[str, str]
    crm_context: dict[str, Any] | None = None


# Allowed transitions for the advance_stage tool
ALLOWED_TRANSITIONS = {
    SalesStage.GREETING: [SalesStage.QUALIFYING],
    SalesStage.QUALIFYING: [SalesStage.NEEDS_ANALYSIS],
    SalesStage.NEEDS_ANALYSIS: [SalesStage.SOLUTION, SalesStage.QUALIFYING],
    SalesStage.SOLUTION: [SalesStage.COMPANY_DETAILS, SalesStage.NEEDS_ANALYSIS],
    SalesStage.COMPANY_DETAILS: [SalesStage.QUOTING, SalesStage.SOLUTION],
    SalesStage.QUOTING: [SalesStage.CLOSING, SalesStage.SOLUTION],
    SalesStage.CLOSING: [],
}


@dataclass
class LLMResponse:
    text: str
    tokens_in: int | None
    tokens_out: int | None
    cost: float | None
    model: str


# Initialize model with OpenRouter provider
model = OpenAIChatModel(
    settings.openrouter_model_main,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

# Initialize Agent
sales_agent = Agent(
    model=model,
    deps_type=SalesDeps,
    retries=2,
)


@sales_agent.system_prompt
async def inject_system_prompt(ctx: RunContext[SalesDeps]) -> str:
    """Dynamically inject the system prompt based on current stage and language."""
    base_prompt = await build_system_prompt(
        db=ctx.deps.db,
        redis=ctx.deps.redis,
        stage=ctx.deps.conversation.sales_stage,
        language=ctx.deps.conversation.language,
    )

    if ctx.deps.crm_context:
        profile_str = "\n".join(f"{k}: {v}" for k, v in ctx.deps.crm_context.items())
        base_prompt += f"\n\n[CRM CUSTOMER CONTEXT]\n{profile_str}\n"

    return base_prompt


@sales_agent.tool
async def perform_search_products(ctx: RunContext[SalesDeps], query: str) -> str:
    """Search for products in the Treejar catalog based on the customer's query.
    Call this whenever a customer asks for recommendations, prices, or product features.

    Args:
        query: What the customer is looking for (e.g. "ergonomic chair under $500")
    """
    logger.info(f"LLM Tool called: search_products(query={query!r})")
    search_query = ProductSearchQuery(query=query, limit=3)

    results = await search_products(
        db=ctx.deps.db,
        query=search_query,
        embedding_engine=ctx.deps.embedding_engine,
    )

    if not results.products:
        return "No products found matching the query."

    from src.core.discounts import apply_discount
    segment = ctx.deps.crm_context.get("Segment", "Unknown") if ctx.deps.crm_context else "Unknown"

    formatted_results = []
    for r in results.products:
        discounted_price = apply_discount(float(r.price), segment)
        desc = f"Name: {r.name_en}\nSKU: {r.sku}\nPrice: {discounted_price:.2f} {r.currency} (Your segment price)\nDescription: {r.description_en}"
        formatted_results.append(desc)

    return "\n---\n".join(formatted_results)


@sales_agent.tool
async def get_stock(ctx: RunContext[SalesDeps], sku: str) -> str:
    """Check current stock level for a specific product SKU.

    Args:
        sku: The exact SKU identifier of the product.
    """
    logger.info(f"LLM Tool called: get_stock(sku={sku!r})")
    stock_info = await ctx.deps.zoho_inventory.get_stock(sku)

    if not stock_info:
        return f"Product with SKU {sku} not found in inventory."

    available = stock_info.get("available_stock", 0)
    return f"Stock for {sku}: {available} items available."


@sales_agent.tool
async def advance_stage(ctx: RunContext[SalesDeps], next_stage: SalesStage) -> str:
    """Advance the sales conversation to the next stage when the current objective is met.

    Args:
        next_stage: The target SalesStage to transition to.
    """
    current_stage = SalesStage(ctx.deps.conversation.sales_stage)
    logger.info(f"LLM Tool called: advance_stage({current_stage} -> {next_stage})")

    allowed_next = ALLOWED_TRANSITIONS.get(current_stage, [])

    if next_stage not in allowed_next:
        return f"Cannot transition directly from {current_stage} to {next_stage}. Allowed transitions: {[s.value for s in allowed_next]}"

    ctx.deps.conversation.sales_stage = next_stage.value
    # Note: caller is responsible for committing the DB transaction.
    return f"Successfully advanced to stage {next_stage.value}. New system instructions will apply on the next turn."


@sales_agent.tool
async def lookup_customer(ctx: RunContext[SalesDeps], phone: str) -> str:
    """Check if the customer's phone number already exists in the CRM system.
    Call this when clarifying customer details or preparing to create a deal.

    Args:
        phone: The customer's phone number in international format (e.g. +971501234567).
    """
    logger.info(f"LLM Tool called: lookup_customer(phone={phone!r})")
    if not ctx.deps.zoho_crm:
        return "CRM Client is not available in the current context."

    contact = await ctx.deps.zoho_crm.find_contact_by_phone(phone)
    if not contact:
        return f"Customer with phone {phone} was NOT found in the CRM."

    name = f"{contact.get('First_Name', '')} {contact.get('Last_Name', '')}".strip()
    return f"Customer FOUND in CRM.\nName: {name}\nEmail: {contact.get('Email', 'N/A')}\nSegment: {contact.get('Segment', 'N/A')}"


@sales_agent.tool
async def create_deal(ctx: RunContext[SalesDeps], title: str, amount: float | None = None) -> str:
    """Create a new Deal (Opportunity) in the CRM system for this customer.
    Call this when the customer has shown clear interest in purchasing and you are entering the Next Steps or Quoting phase.

    Args:
        title: A short, descriptive name for the deal (e.g. "Office Chairs for 10 people").
        amount: Estimated total value of the deal in AED, if known.
    """
    logger.info(f"LLM Tool called: create_deal(title={title!r}, amount={amount})")

    if not ctx.deps.zoho_crm:
        return "CRM Client is not available in the current context."

    # Look up the contact's CRM ID first, since we need to link it
    phone = ctx.deps.conversation.phone
    contact = await ctx.deps.zoho_crm.find_contact_by_phone(phone)

    if not contact:
        # We must create the contact first
        logger.info("Contact not found, creating before deal formulation.")
        new_contact_data = {
            "Phone": phone,
            "Last_Name": ctx.deps.conversation.customer_name or "Unknown Client",
            "Lead_Source": "Chatbot"
        }
        resp = await ctx.deps.zoho_crm.create_contact(new_contact_data)
        if "details" not in resp or "id" not in resp["details"]:
            return "Failed to create customer in CRM. Cannot create deal."
        contact_id = resp["details"]["id"]
    else:
        contact_id = contact["id"]

    # Create the deal
    deal_data: dict[str, Any] = {
        "Deal_Name": title,
        "Contact_Name": {"id": contact_id},
        "Stage": "New Lead",
        "Pipeline": "Standard (Standard)",
    }
    if amount is not None:
        deal_data["Amount"] = amount

    deal_resp = await ctx.deps.zoho_crm.create_deal(deal_data)

    if "details" in deal_resp and "id" in deal_resp["details"]:
        deal_id = deal_resp['details']['id']
        return f"Successfully created Deal in CRM. Deal ID: {deal_id}, Stage: 'New Lead'."

    return "Failed to create deal. CRM response pattern unexpected."


@dataclass
class QuotationItem:
    sku: str
    quantity: int

@sales_agent.tool
async def create_quotation(
    ctx: RunContext[SalesDeps],
    items: list[QuotationItem],
) -> str:
    """Generate a formal PDF quotation for the customer, save it to Zoho Inventory as a draft, and send it via WhatsApp.
    Call this when the customer has explicitly asked for a quote and confirmed the items and quantities.
    Make sure you have their name, company name (if applicable), and email addressed.

    Args:
        items: List of the SKUs and quantities to include in the quote.
    """
    logger.info(f"LLM Tool called: create_quotation(items={items})")

    # Needs to fetch item details from Zoho Inventory
    skus_to_fetch = [item.sku for item in items]
    stock_details = await ctx.deps.zoho_inventory.get_stock_bulk(skus_to_fetch)
    stock_map = {item["sku"]: item for item in stock_details}

    zoho_line_items = []
    template_items = []
    subtotal = 0.0

    from src.core.discounts import apply_discount
    segment = ctx.deps.crm_context.get("Segment", "Unknown") if ctx.deps.crm_context else "Unknown"

    for item in items:
        if item.sku not in stock_map:
            return f"Failed to create quotation: SKU {item.sku} not found."

        zoho_item = stock_map[item.sku]
        base_price = float(zoho_item.get("rate", 0.0))
        unit_price = apply_discount(base_price, segment)
        total_price = unit_price * item.quantity
        subtotal += total_price

        # Zoho Inventory Draft Order Line Item
        zoho_line_items.append({
            "item_id": zoho_item["item_id"],
            "quantity": item.quantity,
            "rate": unit_price,
            "description": zoho_item.get("description", ""),
        })

        # Template Data formatting
        template_items.append({
            "sku": item.sku,
            "name": zoho_item.get("name", ""),
            "description": zoho_item.get("description", ""),
            "quantity": item.quantity,
            "unit_price": unit_price,
            "total_price": total_price,
            # Weasyprint can load URLs directly if they are public.
            "image_url": zoho_item.get("image_document_id")  # Assuming Zoho structure has an image URL or ID
        })

    # Fake missing data (In production, load CRM contact link)
    customer_id = "temp_draft_customer_id"  # Usually we'd map this via Zoho CRM contact

    # Create Draft Order in Zoho
    try:
        draft_resp = await ctx.deps.zoho_inventory.create_sale_order(
            customer_id=customer_id,
            items=zoho_line_items,
            status="draft"
        )
        quote_number = draft_resp.get("saleorder", {}).get("salesorder_number", "DRAFT")
    except Exception as e:
        logger.error(f"Failed to create draft sale order: {e}")
        return "Failed to create draft sale order in Zoho Inventory."

    # Generate PDF context
    vat_amount = subtotal * 0.05
    grand_total = subtotal + vat_amount

    pdf_context = {
        "quote_number": quote_number,
        "trn": "100418386400003",
        "date": "Today",
        "customer": {
            "name": ctx.deps.conversation.customer_name or "Valued Customer",
            "company": "Company Name",
            "email": "customer@example.com",
            "address": "UAE"
        },
        "items": template_items,
        "subtotal": subtotal,
        "vat_amount": vat_amount,
        "grand_total": grand_total,
        "manager": {
            "name": "Syed Amanullah",
            "phone": "+971545467851",
            "email": "syed.h@treejartrading.ae"
        }
    }

    # Import pdf generator (delay import to avoid circular dependency or import overhead if not used)
    from src.services.pdf.generator import generate_pdf, render_quotation_html
    html_content = render_quotation_html(pdf_context)
    pdf_bytes = await generate_pdf(html_content)

    # Send via Messaging Provider
    chat_id = ctx.deps.conversation.phone
    try:
        await ctx.deps.messaging_client.send_media(
            chat_id=chat_id,
            url=None,
            caption=f"Here is your quotation: {quote_number}",
            content=pdf_bytes,
            content_type="application/pdf"
        )
    except Exception as e:
        logger.error(f"Failed to send PDF via Wazzup: {e}")
        return "Generated quotation but failed to send it via WhatsApp."

    return f"Successfully generated quotation {quote_number} and sent it to the customer via WhatsApp."


async def process_message(
    conversation_id: UUID,
    combined_text: str,
    db: AsyncSession,
    redis: Any,
    embedding_engine: EmbeddingEngine,
    zoho_client: ZohoInventoryClient,
    messaging_client: MessagingProvider,
    crm_client: ZohoCRMClient | None = None,
) -> LLMResponse:
    """Process an incoming message through the PydanticAI agent.

    1. Loads conversation
    2. Masks PII
    3. Builds message history
    4. Runs LLM agent
    5. Unmasks PII in response
    """
    # Load conversation (already loaded by caller typically, but we fetch to be safe/fresh)
    conv = await db.get(Conversation, conversation_id)
    if not conv:
        raise ValueError(f"Conversation {conversation_id} not found")

    from src.core.cache import get_cached_crm_profile, set_cached_crm_profile

    # Fetch CRM Profile for context enrichment
    crm_context = None
    if crm_client and conv.phone:
        crm_context = await get_cached_crm_profile(redis, conv.phone)
        if not crm_context:
            contact = await crm_client.find_contact_by_phone(conv.phone)
            if contact:
                name = f"{contact.get('First_Name', '')} {contact.get('Last_Name', '')}".strip()
                crm_context = {"Name": name, "Segment": contact.get("Segment", "Unknown")}
                await set_cached_crm_profile(redis, conv.phone, crm_context)
            else:
                crm_context = {"Segment": "Unknown"}

    # Optional shared dict for PII placeholders across history
    pii_map: dict[str, str] = {}

    # Process history (also populates pii_map with past messages' PII)
    history = await build_message_history(db, conversation_id, pii_map)

    # Mask current incoming text
    masked_text, new_piis = mask_pii(combined_text)
    pii_map.update(new_piis)

    # Evaluate escalation triggers (Task 6)
    from src.core.escalation import evaluate_escalation_triggers
    from src.schemas.common import EscalationStatus

    # Only evaluate if not already escalated
    if conv.escalation_status == EscalationStatus.NONE.value:
        escalation_eval = await evaluate_escalation_triggers(masked_text)
        if escalation_eval.should_escalate and escalation_eval.reason:
            from src.integrations.notifications.escalation import (
                notify_manager_escalation,
            )

            # Get last 5 messages for context
            recent_context = "\n".join(
                [f"{getattr(msg, 'role', 'unknown')}: {getattr(msg, 'content', '')}" for msg in history[-5:]] + [f"user: {masked_text}"]
            )

            await notify_manager_escalation(conv, escalation_eval.reason, [recent_context], db)

            # Instead of returning immediately, we proceed but inject a system note
            # so the LLM responds politely indicating a human will follow up.
            masked_text += "\n[SYSTEM NOTE: This message triggered a manager escalation. Briefly acknowledge their request and state that a human manager has been notified and will review the chat shortly. Do NOT try to solve it completely if it requires human intervention.]"

    deps = SalesDeps(
        db=db,
        redis=redis,
        conversation=conv,
        embedding_engine=embedding_engine,
        zoho_inventory=zoho_client,
        zoho_crm=crm_client,
        messaging_client=messaging_client,
        pii_map=pii_map,
        crm_context=crm_context,
    )

    try:
        from src.core.config import get_system_config
        db_model_main = await get_system_config(db, "openrouter_model_main", settings.openrouter_model_main)

        result = await sales_agent.run(
            user_prompt=masked_text,
            deps=deps,
            message_history=history,
            model=db_model_main,
        )

        # Unmask PII before sending back to user
        final_text = unmask_pii(result.output, pii_map)

        usage = result.usage()

        return LLMResponse(
            text=final_text,
            tokens_in=usage.input_tokens if usage else None,
            tokens_out=usage.output_tokens if usage else None,
            cost=None, # Usage cost tracking usually needs custom logic or litellm
            model=db_model_main,
        )

    except Exception:
        logger.exception("LLM generation failed")
        return LLMResponse(
            text="I apologize, but I am experiencing a temporary issue. Please try again in a moment.",
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            model=db_model_main if 'db_model_main' in locals() else settings.openrouter_model_main,
        )
