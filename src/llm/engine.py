from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Literal
from uuid import UUID

from pydantic import SkipValidation
from pydantic_ai import Agent, RunContext, ToolReturn
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.tools import ToolDefinition
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.context import build_message_history
from src.llm.order_handoff import is_high_confidence_first_turn_order
from src.llm.order_status import format_order_status
from src.llm.pii import mask_pii, unmask_pii
from src.llm.prompts import build_system_prompt
from src.llm.verified_answers import (
    build_service_handoff_reason,
    build_service_handoff_response,
    build_service_runtime_directives,
    classify_product_match,
    evaluate_verified_answer_policy,
)
from src.models.conversation import Conversation
from src.rag.embeddings import EmbeddingEngine
from src.rag.pipeline import search_products as rag_search_products
from src.schemas.common import Language, SalesStage
from src.schemas.product import ProductSearchQuery
from src.services.escalation_state import is_active_human_handoff
from src.services.public_media import build_signed_product_image_url

logger = logging.getLogger(__name__)

__all__ = ["rag_search_products"]
MAX_PRODUCT_SEARCH_CALLS_PER_MESSAGE = 2
ORDER_HANDOFF_ALLOWED_TOOLS = frozenset({"escalate_to_manager", "update_language"})
SERVICE_POLICY_ALLOWED_TOOLS = frozenset({"escalate_to_manager", "update_language"})
ORDER_HANDOFF_PASS_1_DIRECTIVES = (
    "this is likely a concrete order handoff case",
    "do not ask qualifying questions if order evidence is already sufficient",
    "either escalate_to_manager(order_confirmation) or ask only one truly necessary clarification",
)
ORDER_HANDOFF_PASS_2_DIRECTIVES = (
    "previous pass missed likely order handoff",
    "do not ask qualifying questions",
    "do not search",
    "if order evidence is sufficient, use escalate_to_manager(order_confirmation)",
)


def _search_products_limit_message(*, include_no_results: bool = False) -> str:
    prefix = "No products found matching the query. " if include_no_results else ""
    return (
        prefix + "Search limit reached for this customer message. "
        "Do not call search_products again. "
        "Answer using the previous search results if you already have relevant items. "
        "Otherwise explain that no exact match was found and offer nearby "
        "alternatives or one clarifying question."
    )


def _product_search_response_contract(
    *,
    match_kind: Literal["exact", "nearby", "missing"] = "exact",
    search_budget_exhausted: bool = False,
) -> str:
    if match_kind == "nearby":
        contract_parts = [
            "Catalog results were found, but they are the closest alternatives rather than a confirmed exact match.",
            "Lead with 2-3 closest alternatives from these results before any generic qualifying questions.",
            "Say honestly that the exact requested item is not confirmed from the catalog results.",
            "Do not claim that these are the exact item requested.",
            "Use only facts already present in tool results, such as price or stock, and do not invent specs.",
            "After presenting the closest alternatives, you may ask at most one targeted follow-up to narrow the recommendation.",
        ]
    elif match_kind == "missing":
        contract_parts = [
            "Current catalog results are too weak to establish a reliable match for this request.",
            "Do not present these results as exact options.",
            "Ask at most one narrow clarification unless you can justify a clearly related alternative from the returned items.",
            "Use only facts already present in tool results and do not invent specs or prices.",
        ]
    else:
        contract_parts = [
            "Relevant catalog results were found for this customer message.",
            "In your next reply, lead with 2-3 concrete options or closest alternatives from these results before any generic qualifying questions.",
            "Use only facts already present in tool results, such as price or stock, and do not invent specs.",
            "If the returned items are only nearby alternatives, say that honestly and position them as the closest fit.",
            "After presenting the options, you may ask at most one targeted follow-up to narrow the recommendation.",
            "Do not start with generic discovery like budget, use case, or timeline if the current results are already relevant enough to show options.",
        ]

    if search_budget_exhausted:
        contract_parts.extend(
            [
                "Product search budget for this customer message is exhausted.",
                "Do not say that you lack catalog access or that you cannot browse the catalog.",
                "Use the product results already returned in this conversation and, if needed, offer the closest alternatives plus one narrow clarification.",
            ]
        )

    return " ".join(contract_parts)


def _search_budget_fallback_contract(*, prior_results_seen: bool) -> str:
    if prior_results_seen:
        return (
            "Product search budget for this customer message is exhausted. "
            "Do not say that you lack catalog access or that you cannot browse the catalog. "
            "Use the product results already returned in this conversation. "
            "If the exact match is still missing, say that honestly, present the closest alternatives, "
            "and ask at most one narrow clarifying question."
        )

    return (
        "Product search budget for this customer message is exhausted and no exact match was found. "
        "Do not search again. Be honest that no exact match was found, offer nearby alternatives if any, "
        "and ask at most one narrow clarifying question instead of an apology-only fallback."
    )


def _stock_follow_up_contract() -> str:
    return (
        "Use this stock fact to strengthen the concrete options you already have. "
        "Keep the answer option-first, mention the relevant availability fact, "
        "and ask at most one targeted follow-up only after presenting options. "
        "Do not switch back to generic qualifying questions before showing the options."
    )


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
    product_search_calls: int = 0
    product_results_seen: bool = False
    tool_mode: Literal["full", "order_handoff", "service_policy"] = "full"
    runtime_directives: tuple[str, ...] = ()


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


async def _prepare_sales_tools(
    ctx: RunContext[SalesDeps], tool_defs: list[ToolDefinition]
) -> list[ToolDefinition]:
    """Hide product search after the allowed per-message budget is exhausted."""
    if ctx.deps.tool_mode == "order_handoff":
        return [
            tool_def
            for tool_def in tool_defs
            if tool_def.name in ORDER_HANDOFF_ALLOWED_TOOLS
        ]
    if ctx.deps.tool_mode == "service_policy":
        return [
            tool_def
            for tool_def in tool_defs
            if tool_def.name in SERVICE_POLICY_ALLOWED_TOOLS
        ]

    if ctx.deps.product_search_calls < MAX_PRODUCT_SEARCH_CALLS_PER_MESSAGE:
        return tool_defs

    filtered_tool_defs = [
        tool_def for tool_def in tool_defs if tool_def.name != "search_products"
    ]

    if len(filtered_tool_defs) != len(tool_defs):
        logger.info(
            "search_products removed from available tools after %d real calls for "
            "conversation %s",
            ctx.deps.product_search_calls,
            ctx.deps.conversation.id,
        )

    return filtered_tool_defs


# Initialize model with OpenRouter provider
model = OpenAIChatModel(
    settings.openrouter_model_main,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
)

# Initialize Agent
sales_agent = Agent(
    model=model,
    deps_type=SalesDeps,
    prepare_tools=_prepare_sales_tools,
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
        faq_block += "Use the above FAQ entries when answering. "
        if ctx.deps.tool_mode == "order_handoff":
            faq_block += (
                "If the answer is NOT in the FAQ, do NOT make up information. "
                "This run is restricted to order handoff handling, so do not rely on FAQ context to continue product discovery.\n"
            )
        elif ctx.deps.tool_mode == "service_policy":
            faq_block += (
                "If the answer is NOT in the FAQ, do NOT make up information. "
                "This run is restricted to verified service-answer handling, so answer only from confirmed FAQ facts and do not continue product discovery.\n"
            )
        else:
            faq_block += (
                "If the answer is NOT in the FAQ, do NOT make up information. "
                "WARNING: If the user asks for specific products or catalog items (e.g. chairs, tables), "
                "you MUST call the `search_products` tool. Do not rely solely on the FAQ for products because the tool fetches live images!\n"
            )
        base_prompt += faq_block

    if ctx.deps.crm_context:
        profile_str = "\n".join(f"{k}: {v}" for k, v in ctx.deps.crm_context.items())
        base_prompt += f"\n\n[CRM CUSTOMER CONTEXT]\n{profile_str}\n"

    if ctx.deps.runtime_directives:
        directives_block = "\n".join(
            f"- {directive}" for directive in ctx.deps.runtime_directives
        )
        base_prompt += f"\n\n[RUNTIME DIRECTIVES]\n{directives_block}\n"

    return base_prompt


# NOTE: Function name MUST match prompt references (prompts.py) exactly.
# PydanticAI derives tool name from function name.
@sales_agent.tool
async def search_products(ctx: RunContext[SalesDeps], query: str) -> str | ToolReturn:
    """Search for products in the Treejar catalog based on the customer's query.
    Call this whenever a customer asks for recommendations, prices, or product features.

    Args:
        query: What the customer is looking for (e.g. "ergonomic chair under $500")
    """
    logger.info(
        "LLM Tool requested: search_products(query=%r, executed_calls=%d)",
        query,
        ctx.deps.product_search_calls,
    )
    if ctx.deps.product_search_calls >= MAX_PRODUCT_SEARCH_CALLS_PER_MESSAGE:
        logger.info(
            "Blocked search_products after reaching per-message cap for conversation %s",
            ctx.deps.conversation.id,
        )
        return ToolReturn(
            return_value=_search_products_limit_message(),
            content=_search_budget_fallback_contract(
                prior_results_seen=ctx.deps.product_results_seen
            ),
        )

    ctx.deps.product_search_calls += 1
    logger.info(
        "Executing real search_products call %d/%d for query=%r",
        ctx.deps.product_search_calls,
        MAX_PRODUCT_SEARCH_CALLS_PER_MESSAGE,
        query,
    )
    search_query = ProductSearchQuery(query=query, limit=3)

    results = await rag_search_products(
        db=ctx.deps.db,
        query=search_query,
        embedding_engine=ctx.deps.embedding_engine,
    )

    if not results.products:
        if ctx.deps.product_search_calls >= MAX_PRODUCT_SEARCH_CALLS_PER_MESSAGE:
            return ToolReturn(
                return_value=_search_products_limit_message(include_no_results=True),
                content=_search_budget_fallback_contract(
                    prior_results_seen=ctx.deps.product_results_seen
                ),
            )
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

    async def _safe_send_media(
        url: str, caption: str, zoho_item_id: str | None = None
    ) -> None:
        try:
            send_url = url
            if zoho_item_id and "zoho-image" not in url and "zoho" in url:
                send_url = build_signed_product_image_url(zoho_item_id)

            await ctx.deps.messaging_client.send_media(
                chat_id=ctx.deps.conversation.phone,
                url=send_url,
                caption=caption,
                content=None,
                content_type=None,
            )
        except Exception as e:
            logger.warning("Failed to send product image: %s", e, exc_info=True)

    for r in results.products:
        discounted_price = apply_discount(float(r.price), segment)
        desc = f"Name: {r.name_en}\nSKU: {r.sku}\nPrice: {discounted_price:.2f} {r.currency} (Your segment price)\nDescription: {r.description_en}"

        if r.image_url:
            desc += "\n[Note: Image of this product has been automatically sent to the customer's WhatsApp. Do not mention or include image URLs in your response.]"
            send_tasks.append(
                _safe_send_media(
                    url=r.image_url,
                    caption=f"{r.name_en} — {discounted_price:.2f} {r.currency}",
                    zoho_item_id=getattr(r, "zoho_item_id", None),
                )
            )

        formatted_results.append(desc)

    if send_tasks:
        await asyncio.gather(*send_tasks)

    product_match = classify_product_match(
        query,
        [
            f"{product.name_en}\n{product.description_en or ''}\n{product.category or ''}"
            for product in results.products
        ],
    )

    if product_match == "nearby":
        formatted_results.insert(
            0,
            "Closest catalog alternatives (exact requested item not confirmed):",
        )
    elif product_match == "missing":
        formatted_results.insert(
            0,
            "Weak catalog matches only (not a reliable exact match):",
        )

    ctx.deps.product_results_seen = True
    search_budget_exhausted = (
        ctx.deps.product_search_calls >= MAX_PRODUCT_SEARCH_CALLS_PER_MESSAGE
    )
    return ToolReturn(
        return_value="\n---\n".join(formatted_results),
        content=_product_search_response_contract(
            match_kind=product_match, search_budget_exhausted=search_budget_exhausted
        ),
    )


@sales_agent.tool
async def get_stock(ctx: RunContext[SalesDeps], sku: str) -> str | ToolReturn:
    """Check current stock level for a specific product SKU.

    Args:
        sku: The exact SKU identifier of the product.
    """
    logger.info(f"LLM Tool called: get_stock(sku={sku!r})")
    stock_info = await ctx.deps.zoho_inventory.get_stock(sku)

    if not stock_info:
        return f"Product with SKU {sku} not found in inventory."

    available = stock_info.get("stock_on_hand", 0)
    stock_text = f"Stock for {sku}: {available} items available."
    if ctx.deps.product_results_seen:
        return ToolReturn(
            return_value=stock_text,
            content=_stock_follow_up_contract(),
        )

    return stock_text


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
                logger.warning(
                    "Failed to download image for %s: %s", tpl_item["sku"], e
                )

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
            f"quotation_pdf:{conv_id_str}",
            86400,
            base64.b64encode(pdf_bytes),
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
    escalation_type: Literal[
        "order_confirmation", "human_requested", "general"
    ] = "general",
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

    def _is_first_turn(history_messages: list[ModelRequest | ModelResponse]) -> bool:
        user_turns = 0
        assistant_turns = 0

        for message in history_messages:
            if isinstance(message, ModelRequest) and any(
                isinstance(part, UserPromptPart) for part in message.parts
            ):
                user_turns += 1
            elif isinstance(message, ModelResponse) and any(
                isinstance(part, TextPart) for part in message.parts
            ):
                assistant_turns += 1

        return assistant_turns == 0 and user_turns >= 1

    def _has_escalation(conversation: Conversation) -> bool:
        return is_active_human_handoff(conversation.escalation_status)

    def _build_llm_response(result: Any, model_name: str) -> LLMResponse:
        final_text = unmask_pii(result.output, pii_map)
        usage = result.usage()
        return LLMResponse(
            text=final_text,
            tokens_in=usage.input_tokens if usage else None,
            tokens_out=usage.output_tokens if usage else None,
            cost=None,
            model=model_name,
        )

    async def _build_policy_handoff_response(
        model_name: str, decision_language: str, decision_text: str
    ) -> LLMResponse:
        return LLMResponse(
            text=decision_text
            if decision_text
            else build_service_handoff_response(policy_decision, decision_language),
            tokens_in=0,
            tokens_out=0,
            cost=None,
            model=f"{model_name}|verified-policy",
        )

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
    is_first_turn = _is_first_turn(history)

    # Escalation is now handled by the agent's escalate_to_manager tool.
    # The agent decides when to escalate based on full conversation context.
    # Build recent history for potential escalation context
    recent_history: list[str] = []
    for message in history:
        if isinstance(message, ModelRequest):
            for request_part in message.parts:
                if isinstance(request_part, UserPromptPart):
                    recent_history.append(f"user: {request_part.content}")
        elif isinstance(message, ModelResponse):
            for response_part in message.parts:
                if isinstance(response_part, TextPart):
                    recent_history.append(f"assistant: {response_part.content}")
    recent_history = recent_history[-5:] + [f"user: {masked_text}"]

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

    policy_decision = evaluate_verified_answer_policy(
        masked_text, deps.faq_context or []
    )

    try:
        from src.core.config import get_system_config

        db_model_main = await get_system_config(
            db, "openrouter_model_main", settings.openrouter_model_main
        )

        dynamic_model = OpenAIChatModel(
            db_model_main,
            provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
        )

        async def _run_agent(run_deps: SalesDeps) -> Any:
            return await sales_agent.run(
                user_prompt=masked_text,
                deps=run_deps,
                message_history=history,
                model=dynamic_model,
            )

        if is_first_turn and is_high_confidence_first_turn_order(masked_text):
            first_result = await _run_agent(
                replace(
                    deps,
                    tool_mode="order_handoff",
                    runtime_directives=ORDER_HANDOFF_PASS_1_DIRECTIVES,
                )
            )
            if _has_escalation(conv):
                return _build_llm_response(first_result, db_model_main)

            second_result = await _run_agent(
                replace(
                    deps,
                    tool_mode="order_handoff",
                    runtime_directives=ORDER_HANDOFF_PASS_2_DIRECTIVES,
                )
            )
            return _build_llm_response(second_result, db_model_main)

        if (
            not policy_decision.is_order_status
            and policy_decision.question_class != "product"
        ):
            if policy_decision.requires_manager_handoff:
                from src.integrations.notifications.escalation import (
                    notify_manager_escalation,
                )
                from src.schemas.common import EscalationType

                await notify_manager_escalation(
                    conversation=deps.conversation,
                    reason=build_service_handoff_reason(masked_text, policy_decision),
                    recent_messages=deps.recent_history or [],
                    db=deps.db,
                    escalation_type=EscalationType.GENERAL,
                )
                return await _build_policy_handoff_response(
                    db_model_main,
                    str(deps.conversation.language),
                    build_service_handoff_response(
                        policy_decision, str(deps.conversation.language)
                    ),
                )

            result = await _run_agent(
                replace(
                    deps,
                    tool_mode="service_policy",
                    runtime_directives=build_service_runtime_directives(
                        policy_decision
                    ),
                )
            )
            return _build_llm_response(result, db_model_main)

        result = await _run_agent(deps)
        return _build_llm_response(result, db_model_main)

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
