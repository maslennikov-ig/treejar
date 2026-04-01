from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import SkipValidation
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.context import build_message_history
from src.llm.order_status import format_order_status
from src.llm.pii import mask_pii, unmask_pii
from src.llm.prompts import build_system_prompt
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.rag.pipeline import search_products as rag_search_products
from src.schemas.common import Language, SalesStage
from src.schemas.product import ProductSearchQuery

logger = logging.getLogger(__name__)

__all__ = ["rag_search_products"]


@dataclass
class SalesDeps:
    db: SkipValidation[AsyncSession]
    redis: SkipValidation[Redis]
    conversation: SkipValidation[Conversation]
    embedding_engine: SkipValidation[EmbeddingEngine]
    zoho_inventory: SkipValidation[ZohoInventoryClient]
    zoho_crm: SkipValidation[ZohoCRMClient | None]
    messaging_client: SkipValidation[MessagingProvider]
    pii_map: dict[str, str]
    crm_context: dict[str, Any] | None = None
    user_query: str = ""
    faq_context: list[dict[str, str]] | None = None  # Cached FAQ search results
    recent_history: list[str] | None = None  # Last N messages for escalation context


# Allowed transitions for the advance_stage tool
ALLOWED_TRANSITIONS = {
    SalesStage.GREETING: [SalesStage.QUALIFYING],
    SalesStage.QUALIFYING: [SalesStage.NEEDS_ANALYSIS],
    SalesStage.NEEDS_ANALYSIS: [SalesStage.SOLUTION, SalesStage.QUALIFYING],
    SalesStage.SOLUTION: [SalesStage.COMPANY_DETAILS, SalesStage.NEEDS_ANALYSIS],
    SalesStage.COMPANY_DETAILS: [SalesStage.QUOTING, SalesStage.SOLUTION],
    SalesStage.QUOTING: [SalesStage.CLOSING, SalesStage.SOLUTION],
    SalesStage.CLOSING: [SalesStage.FEEDBACK],
    SalesStage.FEEDBACK: [],
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

    # RAG: inject cached knowledge base FAQ context
    if ctx.deps.faq_context:
        faq_block = "\n\n[KNOWLEDGE BASE (FAQ)]\n"
        for item in ctx.deps.faq_context:
            faq_block += f"Q: {item['title']}\nA: {item['content']}\n---\n"
        faq_block += (
            "Use the above FAQ entries when answering. "
            "If the answer is NOT in the FAQ, do NOT make up information.\n"
        )
        base_prompt += faq_block

    if ctx.deps.crm_context:
        profile_str = "\n".join(f"{k}: {v}" for k, v in ctx.deps.crm_context.items())
        base_prompt += f"\n\n[CRM CUSTOMER CONTEXT]\n{profile_str}\n"

    return base_prompt


# NOTE: Function name MUST match prompt references (prompts.py) exactly.
# PydanticAI derives tool name from function name.
@sales_agent.tool
async def search_products(ctx: RunContext[SalesDeps], query: str) -> str:
    """Search for products in the Treejar catalog based on the customer's query.
    Call this whenever a customer asks for recommendations, prices, or product features.

    Args:
        query: What the customer is looking for (e.g. "ergonomic chair under $500")
    """
    logger.info(f"LLM Tool called: search_products(query={query!r})")
    search_query = ProductSearchQuery(query=query, limit=3)

    results = await rag_search_products(
        db=ctx.deps.db,
        query=search_query,
        embedding_engine=ctx.deps.embedding_engine,
    )

    if not results.products:
        return "No products found matching the query."

    from src.core.discounts import apply_discount

    segment = (
        ctx.deps.crm_context.get("Segment", "Unknown")
        if ctx.deps.crm_context
        else "Unknown"
    )

    formatted_results = []
    send_tasks = []

    import asyncio

    async def _safe_send_media(url: str, caption: str) -> None:
        try:
            await ctx.deps.messaging_client.send_media(
                chat_id=ctx.deps.conversation.phone,
                url=url,
                caption=caption,
            )
        except Exception as e:
            logger.warning("Failed to send product image: %s", e, exc_info=True)

    for r in results.products:
        discounted_price = apply_discount(float(r.price), segment)
        desc = f"Name: {r.name_en}\nSKU: {r.sku}\nPrice: {discounted_price:.2f} {r.currency} (Your segment price)\nDescription: {r.description_en}"

        if r.image_url:
            desc += f"\nImage: {r.image_url}"
            send_tasks.append(
                _safe_send_media(
                    url=r.image_url,
                    caption=f"{r.name_en} — {discounted_price:.2f} {r.currency}"
                )
            )

        formatted_results.append(desc)

    if send_tasks:
        await asyncio.gather(*send_tasks)

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

    available = stock_info.get("stock_on_hand", 0)
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
async def update_language(ctx: RunContext[SalesDeps], language: Language) -> str:
    """Update the preferred language of the conversation based on the user's messages.
    Call this immediately if the user starts speaking a language different from the current setting.
    Supported languages: 'en', 'ar'.
    """
    logger.info(f"LLM Tool called: update_language(language={language.value})")
    ctx.deps.conversation.language = language.value
    return f"Language updated to {language.value}."


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
async def create_deal(
    ctx: RunContext[SalesDeps], title: str, amount: float | None = None
) -> str:
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
            "Lead_Source": "Chatbot",
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
        deal_id = deal_resp["details"]["id"]
        return (
            f"Successfully created Deal in CRM. Deal ID: {deal_id}, Stage: 'New Lead'."
        )

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

    segment = (
        ctx.deps.crm_context.get("Segment", "Unknown")
        if ctx.deps.crm_context
        else "Unknown"
    )

    for item in items:
        if item.sku not in stock_map:
            return f"Failed to create quotation: SKU {item.sku} not found."

        zoho_item = stock_map[item.sku]
        base_price = float(zoho_item.get("rate", 0.0))
        unit_price = apply_discount(base_price, segment)
        total_price = unit_price * item.quantity
        subtotal += total_price

        # Zoho Inventory Draft Order Line Item
        zoho_line_items.append(
            {
                "item_id": zoho_item["item_id"],
                "quantity": item.quantity,
                "rate": unit_price,
                "description": zoho_item.get("description", ""),
            }
        )

        # Template Data formatting
        template_items.append(
            {
                "sku": item.sku,
                "name": zoho_item.get("name", ""),
                "description": zoho_item.get("description", ""),
                "quantity": item.quantity,
                "unit_price": unit_price,
                "total_price": total_price,
                "image_url": None,  # Resolved below via authenticated download
                "_item_id": zoho_item.get("item_id"),  # For image fetch
                "_has_image": bool(zoho_item.get("image_document_id")),
            }
        )

    # --- Download product images and embed as base64 data URIs ---
    # Zoho image URLs require OAuth, so we download via the authenticated client
    # and embed them directly into the HTML for WeasyPrint.
    import asyncio
    import base64
    import json as json_mod

    sem = asyncio.Semaphore(3)  # limit concurrent image downloads

    async def _fetch_image(tpl_item: dict[str, Any]) -> None:
        if not tpl_item.get("_has_image") or not tpl_item.get("_item_id"):
            return
        async with sem:
            try:
                result = await ctx.deps.zoho_inventory.get_item_image(
                    str(tpl_item["_item_id"])
                )
                if result:
                    img_bytes, content_type = result
                    b64 = base64.b64encode(img_bytes).decode("ascii")
                    tpl_item["image_url"] = f"data:{content_type};base64,{b64}"
            except Exception as e:
                logger.warning("Failed to download image for %s: %s", tpl_item["sku"], e)

    await asyncio.gather(*[_fetch_image(ti) for ti in template_items])

    # Clean up internal keys before passing to template
    for ti in template_items:
        ti.pop("_item_id", None)
        ti.pop("_has_image", None)

    # Resolve customer data from CRM or conversation context
    # Priority: CRM contact > crm_context > conversation fields > fallback
    customer_name = ctx.deps.conversation.customer_name or "Valued Customer"
    customer_email = ""
    customer_company = ""
    zoho_customer_id = ""

    if ctx.deps.zoho_crm:
        contact = await ctx.deps.zoho_crm.find_contact_by_phone(
            ctx.deps.conversation.phone
        )
        if contact:
            crm_first = contact.get("First_Name", "")
            crm_last = contact.get("Last_Name", "")
            crm_full = f"{crm_first} {crm_last}".strip()
            if crm_full:
                customer_name = crm_full
            customer_email = contact.get("Email", "")
            customer_company = contact.get("Account_Name", "")
            zoho_customer_id = contact.get("id", "")
    elif ctx.deps.crm_context:
        customer_name = ctx.deps.crm_context.get("Name", customer_name)

    # For Zoho Inventory, use a placeholder if no real customer_id resolved.
    # The draft will still be created; the customer link can be updated manually.
    customer_id = zoho_customer_id or "temp_draft_customer_id"

    # Create Draft Order in Zoho
    try:
        draft_resp = await ctx.deps.zoho_inventory.create_sale_order(
            customer_id=customer_id, items=zoho_line_items, status="draft"
        )
        saleorder_data = draft_resp.get("saleorder", {})
        quote_number = saleorder_data.get("salesorder_number", "DRAFT")

        # Save sale order ID in conversation metadata for order status tracking (CR-1)
        sale_order_id = saleorder_data.get("salesorder_id", "")
        if sale_order_id:
            conv = ctx.deps.conversation
            metadata = dict(conv.metadata_ or {})
            metadata["zoho_sale_order_id"] = sale_order_id
            conv.metadata_ = metadata
            try:
                await ctx.deps.db.flush()
            except Exception as flush_err:
                logger.warning(
                    "Failed to persist sale_order_id in metadata: %s", flush_err
                )
    except Exception as e:
        logger.error("Failed to create draft sale order: %s", e)
        return "Failed to create draft sale order in Zoho Inventory."

    # Generate PDF context
    import datetime as _dt

    vat_amount = subtotal * 0.05
    grand_total = subtotal + vat_amount

    pdf_context = {
        "quote_number": quote_number,
        "trn": "100418386400003",
        "date": _dt.date.today().strftime("%d %B %Y"),
        "customer": {
            "name": customer_name,
            "company": customer_company,
            "email": customer_email,
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

    # Import pdf generator (delay import to avoid circular dependency or import overhead if not used)
    from src.services.pdf.generator import generate_pdf, render_quotation_html

    html_content = render_quotation_html(pdf_context)
    pdf_bytes = await generate_pdf(html_content)

    # Store PDF in Redis for manager review (instead of sending directly to client)
    conv_id_str = str(ctx.deps.conversation.id)
    pdf_filename = f"quotation_{quote_number}.pdf"
    try:
        await ctx.deps.redis.setex(
            f"quotation_pdf:{conv_id_str}", 86400, base64.b64encode(pdf_bytes),
        )
        await ctx.deps.redis.setex(
            f"quotation_meta:{conv_id_str}",
            86400,
            json_mod.dumps({"quote_number": quote_number, "filename": pdf_filename}),
        )
    except Exception as e:
        logger.error("Failed to store PDF in Redis: %s", e)
        return "Generated quotation but failed to save it for review."

    # Trigger manager escalation with PDF attachment
    from src.integrations.notifications.escalation import notify_manager_escalation
    from src.schemas.common import EscalationType

    recent_context = f"Customer confirmed order. Quotation {quote_number} generated."
    try:
        await notify_manager_escalation(
            conversation=ctx.deps.conversation,
            reason=f"Order quotation {quote_number} requires manager approval",
            recent_messages=[recent_context],
            db=ctx.deps.db,
            escalation_type=EscalationType.ORDER_CONFIRMATION,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )
    except Exception as e:
        logger.error("Failed to send escalation with PDF: %s", e)

    return (
        f"Quotation {quote_number} has been prepared and sent to the manager for review. "
        "The customer will receive the quotation once the manager approves it."
    )


@sales_agent.tool
async def recommend_products(
    ctx: RunContext[SalesDeps],
    product_id: str | None = None,
    category: str | None = None,
    recommendation_type: str = "similar",
) -> str:
    """Get product recommendations for the customer.
    Use 'similar' type when a customer is looking at a specific product.
    Use 'cross_sell' type to suggest complementary items based on category.

    Args:
        product_id: UUID of the source product (required for 'similar' type).
        category: Product category (required for 'cross_sell' type).
        recommendation_type: Either 'similar' or 'cross_sell'.
    """
    logger.info(
        "LLM Tool called: recommend_products(product_id=%s, category=%s, type=%s)",
        product_id,
        category,
        recommendation_type,
    )
    from src.services.recommendations import get_cross_sell, get_similar_products

    if recommendation_type == "similar" and product_id:
        from uuid import UUID as UUIDType

        try:
            pid = UUIDType(product_id)
        except ValueError:
            return f"Invalid product ID format: {product_id}"

        items = await get_similar_products(ctx.deps.db, pid, limit=5)
        if not items:
            return "No similar products found."

        lines = ["Also recommended (similar products):"]
        for item in items:
            sim = (
                f" ({item.similarity_score:.0%} match)" if item.similarity_score else ""
            )
            lines.append(f"- {item.name}: {item.price:.2f} AED{sim}")
        return "\n".join(lines)

    elif recommendation_type == "cross_sell" and category:
        items = await get_cross_sell(ctx.deps.db, category, limit=3)
        if not items:
            return f"No cross-sell items found for category '{category}'."

        lines = ["You might also need:"]
        for item in items:
            lines.append(
                f"- {item.name}: {item.price:.2f} AED (in stock: {item.stock})"
            )
        return "\n".join(lines)

    return (
        "Please specify either product_id (for similar) or category (for cross_sell)."
    )


@sales_agent.tool
async def generate_referral_code(ctx: RunContext[SalesDeps]) -> str:
    """Generate a referral code for the current customer.
    The customer can share this code with friends for a discount.
    Call this when the customer asks about referral programs or sharing deals.
    """
    logger.info("LLM Tool called: generate_referral_code()")
    from src.services.referrals import generate_code

    phone = ctx.deps.conversation.phone
    result = await generate_code(ctx.deps.db, phone)

    if result.success:
        return result.message
    return f"Could not generate referral code: {result.message}"


@sales_agent.tool
async def apply_referral_code(ctx: RunContext[SalesDeps], code: str) -> str:
    """Apply a referral code provided by the customer.
    This gives them a discount on their purchase.

    Args:
        code: The referral code to apply (format: NOOR-XXXXX).
    """
    logger.info("LLM Tool called: apply_referral_code(code=%r)", code)
    from src.services.referrals import apply_code

    phone = ctx.deps.conversation.phone
    result = await apply_code(ctx.deps.db, code, phone)

    if result.success:
        return result.message
    return f"Referral code issue: {result.message}"


@sales_agent.tool
async def save_feedback(
    ctx: RunContext[SalesDeps],
    rating_overall: int,
    rating_delivery: int,
    recommend: bool,
    comment: str | None = None,
) -> str:
    """Save the customer's post-delivery feedback after collecting all ratings.
    Call this after the customer has provided their overall rating, delivery rating,
    recommendation, and optional comment.

    Args:
        rating_overall: Customer's overall satisfaction rating (1-5, where 5 is best).
        rating_delivery: Customer's delivery experience rating (1-5, where 5 is best).
        recommend: Whether the customer would recommend Treejar to others.
        comment: Optional free-form comment or suggestion from the customer.
    """
    from pydantic_ai import ModelRetry

    logger.info(
        "LLM Tool called: save_feedback(overall=%s, delivery=%s, recommend=%s)",
        rating_overall,
        rating_delivery,
        recommend,
    )

    # Validate ratings
    if not (1 <= rating_overall <= 5) or not (1 <= rating_delivery <= 5):
        raise ModelRetry(
            "Invalid ratings. Both rating_overall and rating_delivery must be between 1 and 5. "
            "Please ask the customer to clarify their rating."
        )

    # Check for existing feedback (prevent duplicates)
    from sqlalchemy import select

    from src.models.feedback import Feedback

    existing = await ctx.deps.db.execute(
        select(Feedback.id).where(Feedback.conversation_id == ctx.deps.conversation.id)
    )
    if existing.scalar_one_or_none() is not None:
        return "Feedback has already been recorded for this conversation. Thank the customer warmly."

    feedback = Feedback(
        conversation_id=ctx.deps.conversation.id,
        deal_id=ctx.deps.conversation.zoho_deal_id,
        rating_overall=rating_overall,
        rating_delivery=rating_delivery,
        recommend=recommend,
        comment=comment,
    )
    ctx.deps.db.add(feedback)

    return "Feedback saved successfully. Thank you for sharing your experience!"


@sales_agent.tool
async def check_order_status(ctx: RunContext[SalesDeps]) -> str:
    """Check the current status of the customer's order.
    Call this when the customer asks about their order status, delivery, or shipment.
    This tool looks up the deal in CRM and the sale order in Inventory.
    """
    logger.info("LLM Tool called: check_order_status()")

    language = ctx.deps.conversation.language or "en"

    deal_id = ctx.deps.conversation.zoho_deal_id
    if not deal_id:
        if language.startswith("ar"):
            return "لم يتم العثور على طلب مرتبط بهذه المحادثة. قد لا يكون لدى العميل صفقة مؤكدة بعد."
        return "No order found linked to this conversation. The customer may not have a confirmed deal yet."

    # Fetch CRM deal status
    deal_data = None
    if ctx.deps.zoho_crm:
        try:
            deal_data = await ctx.deps.zoho_crm.get_deal_status(deal_id)
        except Exception as e:
            logger.warning("Failed to fetch CRM deal status: %s", e)

    # Fetch Inventory sale order status (use deal_id as reference, or from metadata)
    order_data = None
    metadata = ctx.deps.conversation.metadata_ or {}
    sale_order_id = metadata.get("zoho_sale_order_id")

    if sale_order_id:
        try:
            order_data = await ctx.deps.zoho_inventory.get_sale_order_status(
                sale_order_id
            )
        except Exception as e:
            logger.warning("Failed to fetch Inventory order status: %s", e)

    return format_order_status(deal_data, order_data, language)


@sales_agent.tool
async def escalate_to_manager(
    ctx: RunContext[SalesDeps],
    reason: str,
    escalation_type: Literal["order_confirmation", "human_requested", "general"] = "general",
) -> str:
    """Escalate the conversation to a human manager.
    Call this ONLY when the situation genuinely requires human intervention.

    DO NOT call this for:
    - Simple product questions (even about wholesale, MOQ, bulk)
    - Questions you can answer from the catalog or FAQ
    - Price inquiries for products in stock

    DO call this for:
    - Customer places a concrete large order with quantities and delivery details
    - Customer explicitly asks to speak to a human/manager
    - Complaints about existing orders (damaged, delayed, wrong product)
    - Request for refund/return
    - Highly technical questions you cannot answer
    - Customer threatening legal action
    - Customization requests not in catalog

    Args:
        reason: Clear explanation of WHY escalation is needed.
        escalation_type: Type of escalation.
    """
    logger.info(
        "LLM Tool called: escalate_to_manager(reason=%r, type=%s)",
        reason,
        escalation_type,
    )
    from src.integrations.notifications.escalation import notify_manager_escalation
    from src.schemas.common import EscalationType

    esc_type = EscalationType(escalation_type)

    # Use pre-built history from SalesDeps (no extra SQL query)
    recent_messages = ctx.deps.recent_history or []

    await notify_manager_escalation(
        conversation=ctx.deps.conversation,
        reason=reason,
        recent_messages=recent_messages,
        db=ctx.deps.db,
        escalation_type=esc_type,
    )

    return (
        "Manager has been notified. Acknowledge the customer's request politely "
        "and let them know a human manager will review their conversation shortly."
    )


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
                crm_context = {
                    "Name": name,
                    "Segment": contact.get("Segment", "Unknown"),
                }
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

    # Escalation is now handled by the agent's escalate_to_manager tool.
    # The agent decides when to escalate based on full conversation context.
    # Build recent history for potential escalation context
    recent_history = [
        f"{getattr(msg, 'role', 'unknown')}: {getattr(msg, 'content', '')}"
        for msg in history[-5:]
    ] + [f"user: {masked_text}"]

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
        user_query=masked_text,
        recent_history=recent_history,
    )

    # Pre-compute FAQ search results (once per message, not per tool roundtrip)
    try:
        from src.rag.pipeline import search_knowledge

        deps.faq_context = await search_knowledge(
            db, masked_text, embedding_engine, limit=3
        )
    except Exception:
        logger.warning("FAQ knowledge base search failed", exc_info=True)

    try:
        from src.core.config import get_system_config

        db_model_main = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )

        dynamic_model = OpenAIChatModel(
            db_model_main,
            provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
        )

        result = await sales_agent.run(
            user_prompt=masked_text,
            deps=deps,
            message_history=history,
            model=dynamic_model,
        )

        # Unmask PII before sending back to user
        final_text = unmask_pii(result.output, pii_map)

        usage = result.usage()

        return LLMResponse(
            text=final_text,
            tokens_in=usage.input_tokens if usage else None,
            tokens_out=usage.output_tokens if usage else None,
            cost=None,  # Usage cost tracking usually needs custom logic or litellm
            model=db_model_main,
        )

    except Exception:
        conv_id_str = str(conv.id) if conv else "unknown"
        phone_str = str(conv.phone) if conv else "unknown"
        logger.exception(
            "LLM generation failed for conv_id=%s phone=%s",
            conv_id_str,
            phone_str,
        )
        # NOTE: We do not surface exc details in model= to avoid info leakage
        db_model_label = db_model_main if "db_model_main" in locals() else "unknown"
        return LLMResponse(
            text="I apologize, but I am experiencing a temporary issue. Please try again in a moment.",
            tokens_in=0,
            tokens_out=0,
            cost=0.0,
            model=f"{db_model_label}|error",
        )
