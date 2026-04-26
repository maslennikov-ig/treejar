from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Any, Literal
from uuid import UUID

import httpx
from pydantic import SkipValidation
from pydantic_ai import Agent, RunContext, ToolReturn
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from pydantic_ai.tools import ToolDefinition
from redis.asyncio import Redis
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import (
    ZohoInventoryClient,
    extract_sale_order_data,
)
from src.integrations.messaging.base import MessagingProvider
from src.llm.context import build_message_history
from src.llm.order_handoff import is_high_confidence_first_turn_order
from src.llm.order_status import format_order_status
from src.llm.pii import mask_pii, unmask_pii
from src.llm.prompts import build_system_prompt
from src.llm.safety import (
    PATH_CORE_CHAT,
    model_name_for_path,
    model_settings_for_path,
    run_agent_with_safety,
)
from src.llm.verified_answers import (
    build_clarification_response,
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
VERIFIED_POLICY_REPAIR_KEY = "verified_policy_repair"
ORDER_HANDOFF_ALLOWED_TOOLS = frozenset({"escalate_to_manager", "update_language"})
SERVICE_POLICY_ALLOWED_TOOLS = frozenset({"escalate_to_manager", "update_language"})
EXACT_QUOTE_ALLOWED_TOOLS = frozenset(
    {
        "search_products",
        "get_stock",
        "create_quotation",
        "escalate_to_manager",
        "update_language",
    }
)
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
EXACT_QUOTE_PASS_1_DIRECTIVES = (
    "the customer is asking for an exact quotation-ready commitment",
    "do not ask for full name, company, or email before the quote draft",
    "if exact sku and quantity are already known, confirm via get_stock and then call create_quotation immediately",
    "if Zoho cannot confirm the item, escalate to manager and do not promise exact price or availability",
)
EXACT_QUOTE_PASS_2_DIRECTIVES = (
    "previous pass stayed consultative on an exact quotation-ready request",
    "do not ask for company details first",
    "use Zoho-confirmed stock and price only",
    "if exact sku and quantity are already known, call create_quotation immediately after confirmation",
)
_QUOTE_REQUEST_TERMS = ("quote", "quotation")
_EXACT_COMMITMENT_QUALIFIERS = ("exact", "current")
_EXACT_COMMITMENT_TARGETS = ("price", "availability", "stock", "available")
_CONSULTATIVE_QUOTE_BLOCKERS = (
    "what options",
    "options",
    "recommend",
    "recommendation",
    "ideas",
    "similar",
    "catalog",
    "show me",
    "bulk pricing",
    "wholesale pricing",
)
_QUANTITY_SIGNAL_RE = re.compile(r"\b\d{1,4}\b")
_SKU_SIGNAL_RE = re.compile(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b")
_QUANTITY_ITEM_SIGNAL_RE = re.compile(
    r"\b(?P<quantity>\d{1,4})\b\s+(?P<item>[^?.!,;\n]+)",
    re.IGNORECASE,
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
        "Use this Zoho-confirmed stock and price fact to strengthen the concrete options you already have. "
        "Keep the answer option-first, mention the relevant availability and exact price facts, "
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
    tool_mode: Literal["full", "order_handoff", "service_policy", "exact_quote"] = (
        "full"
    )
    runtime_directives: tuple[str, ...] = ()
    inventory_confirmed: bool = False
    quotation_created: bool = False
    catalog_mismatch_alerted: bool = False


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


@dataclass(frozen=True)
class ExactQuoteCandidate:
    quantity: int
    item_candidate: str
    sku: str | None


def _normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def _tokenize_exact_match_text(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9]+", _normalize_text(text))
        if token and len(token) >= 2
    ]


def _has_exact_commitment_intent(normalized: str) -> bool:
    if any(blocker in normalized for blocker in _CONSULTATIVE_QUOTE_BLOCKERS):
        return False

    if any(term in normalized for term in _QUOTE_REQUEST_TERMS):
        return True

    has_commitment_target = any(
        term in normalized for term in _EXACT_COMMITMENT_TARGETS
    )
    has_exactness_signal = any(
        term in normalized for term in _EXACT_COMMITMENT_QUALIFIERS
    )

    return has_commitment_target and (
        has_exactness_signal
        or (
            "price" in normalized
            and (
                "availability" in normalized
                or "stock" in normalized
                or "available" in normalized
            )
        )
    )


def _looks_like_exact_item_candidate(candidate: str) -> bool:
    normalized = _normalize_text(candidate)
    if not normalized or any(
        blocker in normalized for blocker in _CONSULTATIVE_QUOTE_BLOCKERS
    ):
        return False

    if not re.search(r"[a-z]", normalized):
        return False

    if _SKU_SIGNAL_RE.search(normalized):
        return True

    tokens = [token for token in normalized.split() if token]
    has_digit = bool(re.search(r"\d", normalized))
    return (has_digit and len(tokens) >= 2) or len(tokens) >= 4


def extract_exact_quote_candidate(text: str) -> ExactQuoteCandidate | None:
    """Parse a concrete quantity + item request that should stay on the exact-quote path."""
    normalized = _normalize_text(text)
    if not normalized or not _has_exact_commitment_intent(normalized):
        return None

    for match in _QUANTITY_ITEM_SIGNAL_RE.finditer(text):
        quantity = int(match.group("quantity"))
        item_candidate = " ".join(match.group("item").split()).strip(" -")
        if not _looks_like_exact_item_candidate(item_candidate):
            continue

        sku_match = re.search(_SKU_SIGNAL_RE.pattern, item_candidate, re.IGNORECASE)
        sku = sku_match.group(0).upper() if sku_match else None
        return ExactQuoteCandidate(
            quantity=quantity,
            item_candidate=item_candidate,
            sku=sku,
        )

    return None


def is_exact_quote_request(text: str) -> bool:
    """Return True for narrow exact quotation requests that should not stay consultative."""
    return extract_exact_quote_candidate(text) is not None


def _catalog_product_match_text(product: Any) -> str:
    attributes = getattr(product, "attributes", None) or {}
    return " ".join(
        part
        for part in (
            str(getattr(product, "sku", "") or ""),
            str(getattr(product, "name_en", "") or ""),
            str(getattr(product, "description_en", "") or ""),
            str(attributes.get("treejar_slug") or ""),
        )
        if part
    )


async def _find_catalog_product_by_sku(db: AsyncSession, sku: str) -> Any | None:
    from src.models.product import Product

    normalized_sku = sku.strip()
    if not normalized_sku:
        return None

    result = await db.execute(
        select(Product).where(func.lower(Product.sku) == normalized_sku.casefold())
    )
    product = result.scalar_one_or_none()
    if product is None or not isinstance(getattr(product, "sku", None), str):
        return None
    return product


async def _download_catalog_image(
    image_url: str | None,
) -> tuple[bytes, str] | None:
    if not image_url:
        return None

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        ) as client:
            response = await client.get(image_url)
            response.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        logger.warning("Failed to download catalog image from %s: %s", image_url, exc)
        return None

    if not response.content:
        return None

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
    if not content_type.startswith("image/"):
        logger.warning(
            "Skipping non-image catalog response for %s with content-type %s",
            image_url,
            content_type or "<missing>",
        )
        return None

    return response.content, content_type


async def _resolve_exact_quote_candidate_sku(
    db: AsyncSession,
    candidate: ExactQuoteCandidate,
) -> str | None:
    if candidate.sku:
        exact_sku_product = await _find_catalog_product_by_sku(db, candidate.sku)
        if exact_sku_product is not None:
            return str(exact_sku_product.sku)
        if _normalize_text(candidate.item_candidate) == _normalize_text(candidate.sku):
            return candidate.sku

    from src.models.product import Product

    candidate_tokens = _tokenize_exact_match_text(candidate.item_candidate)
    if len(candidate_tokens) < 2:
        return None

    anchor_terms = [token for token in candidate_tokens if len(token) >= 4]
    if not anchor_terms:
        anchor_terms = candidate_tokens
    anchor = max(
        anchor_terms, key=lambda token: (any(ch.isdigit() for ch in token), len(token))
    )

    result = await db.execute(
        select(Product).where(
            Product.is_active.is_(True),
            or_(
                func.lower(Product.name_en).contains(anchor),
                func.lower(func.coalesce(Product.description_en, "")).contains(anchor),
                func.lower(Product.sku).contains(anchor),
            ),
        )
    )
    products = list(result.scalars().all())
    if not products:
        return None

    candidate_token_set = set(candidate_tokens)
    best_product: Any | None = None
    best_score = (-1, -1, -1)
    second_best_score = (-1, -1, -1)
    for product in products:
        product_tokens = set(
            _tokenize_exact_match_text(_catalog_product_match_text(product))
        )
        overlap = candidate_token_set & product_tokens
        digit_overlap = sum(1 for token in overlap if any(ch.isdigit() for ch in token))
        long_overlap = sum(1 for token in overlap if len(token) >= 4)
        score = (digit_overlap, long_overlap, len(overlap))
        if score > best_score:
            second_best_score = best_score
            best_score = score
            best_product = product
        elif score > second_best_score:
            second_best_score = score

    if best_product is None:
        return None

    min_overlap = 3 if len(candidate_token_set) >= 4 else 2
    if best_score[2] < min_overlap:
        return None
    if best_score == second_best_score:
        return None

    return str(best_product.sku)


def _catalog_mismatch_customer_message() -> str:
    return (
        "I couldn't confirm exact price and availability in Zoho for this item. "
        "A manager has been asked to verify it before we make a commitment."
    )


def _coerce_inventory_item(
    raw_item: Any,
    *,
    require_item_id: bool,
) -> dict[str, Any] | None:
    if not isinstance(raw_item, Mapping):
        return None

    item = dict(raw_item)

    sku = item.get("sku")
    if not isinstance(sku, str) or not sku.strip():
        return None

    rate = item.get("rate")
    stock_on_hand = item.get("stock_on_hand")
    if rate is None or stock_on_hand is None:
        return None
    try:
        item["rate"] = float(rate)
        item["stock_on_hand"] = int(stock_on_hand)
    except (TypeError, ValueError):
        return None

    if require_item_id:
        item_id = item.get("item_id")
        if not isinstance(item_id, str) or not item_id.strip():
            return None

    return item


def _exact_quote_fail_closed_message() -> str:
    return (
        "I couldn't finalize the exact quotation automatically. "
        "A manager has been asked to verify exact price and availability before we make a commitment."
    )


def _string_value(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _metadata_sale_order_is_active(metadata: Mapping[str, Any]) -> bool:
    decision = metadata.get("quotation_decision")
    if isinstance(decision, Mapping):
        status = _string_value(decision.get("status")).lower()
        if decision.get("active") is False or status == "rejected":
            return False

    if (
        metadata.get("zoho_sale_order_active") is False
        or metadata.get("order_active") is False
    ):
        return False

    decision_status = _string_value(
        metadata.get("quotation_decision_status") or metadata.get("quotation_status")
    ).lower()
    return decision_status != "rejected"


def _extract_crm_company(value: Any) -> str:
    if isinstance(value, Mapping):
        return _string_value(value.get("name"))
    return _string_value(value)


def _split_contact_name(name: str) -> tuple[str, str]:
    parts = [part for part in name.split() if part]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def _inventory_contact_id(contact: Mapping[str, Any] | None) -> str | None:
    if not isinstance(contact, Mapping):
        return None

    contact_id = contact.get("contact_id")
    if contact_id is None:
        return None

    contact_id_str = str(contact_id).strip()
    return contact_id_str or None


def _is_duplicate_inventory_contact_error(exc: Exception) -> bool:
    if not isinstance(exc, httpx.HTTPStatusError):
        return False
    if exc.response.status_code != 400:
        return False

    try:
        payload = exc.response.json()
    except ValueError:
        payload = None

    if isinstance(payload, Mapping):
        code = payload.get("code")
        message = str(payload.get("message") or "").casefold()
        if code == 3062 or "already exists" in message:
            return True

    return "already exists" in exc.response.text.casefold()


def _build_inventory_contact_payload(
    *,
    phone: str,
    customer_name: str,
    customer_email: str,
    customer_company: str,
) -> dict[str, Any]:
    fallback_suffix = "".join(ch for ch in phone if ch.isdigit())[-4:] or "customer"
    contact_name = (
        customer_company or customer_name or f"WhatsApp Customer {fallback_suffix}"
    )
    contact_person_name = customer_name or contact_name
    first_name, last_name = _split_contact_name(contact_person_name)
    if not first_name:
        first_name = contact_name

    contact_person: dict[str, Any] = {
        "first_name": first_name,
        "phone": phone,
        "mobile": phone,
        "is_primary_contact": True,
    }
    if last_name:
        contact_person["last_name"] = last_name
    if customer_email:
        contact_person["email"] = customer_email

    payload: dict[str, Any] = {
        "contact_name": contact_name,
        "contact_type": "customer",
        "contact_persons": [contact_person],
    }
    if customer_company:
        payload["company_name"] = customer_company

    return payload


async def resolve_inventory_customer_id(
    *,
    phone: str,
    customer_name: str,
    customer_email: str,
    customer_company: str,
    zoho_inventory: ZohoInventoryClient,
) -> str | None:
    """Resolve or create a valid Zoho Inventory customer contact for quotations."""
    try:
        existing_contact = await zoho_inventory.find_customer_by_phone(phone)
    except Exception:
        logger.exception(
            "Failed to search Zoho Inventory customer by phone for %s",
            phone,
        )
        return None

    existing_contact_id = _inventory_contact_id(existing_contact)
    if existing_contact_id:
        return existing_contact_id

    if customer_email:
        try:
            existing_by_email = await zoho_inventory.find_customer_by_email(
                customer_email
            )
        except Exception:
            logger.exception(
                "Failed to search Zoho Inventory customer by email for %s",
                customer_email,
            )
            return None

        existing_by_email_id = _inventory_contact_id(existing_by_email)
        if existing_by_email_id:
            return existing_by_email_id

    payload = _build_inventory_contact_payload(
        phone=phone,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_company=customer_company,
    )

    try:
        created_contact = await zoho_inventory.create_contact(payload)
    except Exception as exc:
        if _is_duplicate_inventory_contact_error(exc):
            seen_names: set[str] = set()
            for candidate_name in (
                _string_value(payload.get("contact_name")),
                customer_company,
                customer_name,
            ):
                normalized_candidate = _string_value(candidate_name)
                if not normalized_candidate:
                    continue
                key = normalized_candidate.casefold()
                if key in seen_names:
                    continue
                seen_names.add(key)
                try:
                    existing_by_name = await zoho_inventory.find_customer_by_name(
                        normalized_candidate
                    )
                except Exception:
                    logger.exception(
                        "Failed duplicate-name fallback search in Zoho Inventory for %s",
                        normalized_candidate,
                    )
                    continue

                existing_by_name_id = _inventory_contact_id(existing_by_name)
                if existing_by_name_id:
                    return existing_by_name_id

        logger.exception(
            "Failed to create Zoho Inventory customer for phone %s",
            phone,
        )
        return None

    contact_id = _inventory_contact_id(created_contact)
    if contact_id is None:
        logger.error(
            "Zoho Inventory create_contact returned no contact_id for phone %s: %s",
            phone,
            created_contact,
        )
    return contact_id


async def _notify_catalog_mismatch_and_escalate(
    ctx: RunContext[SalesDeps],
    *,
    sku: str,
    catalog_product: Any,
    detail: str,
) -> None:
    if ctx.deps.catalog_mismatch_alerted:
        return

    from src.integrations.notifications.escalation import notify_manager_escalation
    from src.schemas.common import EscalationType
    from src.services.notifications import notify_catalog_mismatch

    attributes = getattr(catalog_product, "attributes", None) or {}
    treejar_slug = str(attributes.get("treejar_slug") or catalog_product.sku)
    product_name = catalog_product.name_en

    await notify_catalog_mismatch(
        sku=getattr(catalog_product, "sku", sku),
        treejar_slug=treejar_slug,
        product_name=product_name,
        detail=detail,
    )
    await notify_manager_escalation(
        conversation=ctx.deps.conversation,
        reason=(
            "Catalog mismatch for exact commitment: Treejar item exists but Zoho "
            "could not confirm exact price/availability."
        ),
        recent_messages=ctx.deps.recent_history or [],
        db=ctx.deps.db,
        escalation_type=EscalationType.GENERAL,
    )
    ctx.deps.catalog_mismatch_alerted = True


async def _fail_closed_exact_quote_request(deps: SalesDeps) -> str:
    from src.integrations.notifications.escalation import notify_manager_escalation
    from src.schemas.common import EscalationType

    if not is_active_human_handoff(deps.conversation.escalation_status):
        await notify_manager_escalation(
            conversation=deps.conversation,
            reason=(
                "Exact quote flow stayed unresolved after two guarded passes and "
                "no deterministic quotation could be created safely."
            ),
            recent_messages=deps.recent_history or [],
            db=deps.db,
            escalation_type=EscalationType.GENERAL,
        )

    return _exact_quote_fail_closed_message()


async def _resolve_inventory_item(
    ctx: RunContext[SalesDeps],
    sku: str,
) -> tuple[dict[str, Any] | None, Any | None]:
    normalized_sku = sku.strip()
    catalog_product = await _find_catalog_product_by_sku(ctx.deps.db, normalized_sku)

    if catalog_product and getattr(catalog_product, "zoho_item_id", None):
        raw_item = await ctx.deps.zoho_inventory.get_item(catalog_product.zoho_item_id)
        zoho_item = _coerce_inventory_item(raw_item, require_item_id=False)
        if zoho_item:
            ctx.deps.inventory_confirmed = True
            return zoho_item, catalog_product

    raw_item = await ctx.deps.zoho_inventory.get_stock(normalized_sku)
    zoho_item = _coerce_inventory_item(raw_item, require_item_id=False)
    if zoho_item:
        ctx.deps.inventory_confirmed = True
        return zoho_item, catalog_product

    if catalog_product:
        await _notify_catalog_mismatch_and_escalate(
            ctx,
            sku=normalized_sku,
            catalog_product=catalog_product,
            detail="Exact Zoho inventory confirmation failed for a runtime quote/stock request.",
        )

    return None, catalog_product


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
    if ctx.deps.tool_mode == "exact_quote":
        return [
            tool_def
            for tool_def in tool_defs
            if tool_def.name in EXACT_QUOTE_ALLOWED_TOOLS
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
CORE_CHAT_MODEL_NAME = model_name_for_path(PATH_CORE_CHAT)
model = OpenAIChatModel(
    CORE_CHAT_MODEL_NAME,
    provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
    settings=model_settings_for_path(PATH_CORE_CHAT, model_name=CORE_CHAT_MODEL_NAME),
)

# Initialize Agent
sales_agent = Agent(
    model=model,
    deps_type=SalesDeps,
    prepare_tools=_prepare_sales_tools,
    retries=2,
    model_settings=model_settings_for_path(
        PATH_CORE_CHAT, model_name=CORE_CHAT_MODEL_NAME
    ),
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

    async def _safe_send_media(
        url: str,
        caption: str,
        product_key: str,
        zoho_item_id: str | None = None,
    ) -> None:
        try:
            send_url = url
            if zoho_item_id and "zoho-image" not in url and "zoho" in url:
                send_url = build_signed_product_image_url(zoho_item_id)

            from src.services.outbound_audit import (
                deterministic_crm_message_id,
                send_wazzup_media_with_audit,
            )

            await send_wazzup_media_with_audit(
                ctx.deps.db,
                provider=ctx.deps.messaging_client,
                conversation_id=UUID(str(ctx.deps.conversation.id)),
                chat_id=ctx.deps.conversation.phone,
                source="product_media",
                crm_message_id=deterministic_crm_message_id(
                    "product",
                    ctx.deps.conversation.id,
                    product_key,
                    "media",
                ),
                caption_crm_message_id=deterministic_crm_message_id(
                    "product",
                    ctx.deps.conversation.id,
                    product_key,
                    "caption",
                ),
                url=send_url,
                caption=caption,
                content=None,
                content_type=None,
            )
            await ctx.deps.db.commit()
        except Exception as e:
            logger.warning("Failed to send product image: %s", e, exc_info=True)

    for r in results.products:
        discounted_price = apply_discount(float(r.price), segment)
        desc = f"Name: {r.name_en}\nSKU: {r.sku}\nPrice: {discounted_price:.2f} {r.currency} (Your segment price)\nDescription: {r.description_en}"

        if r.image_url:
            desc += "\n[Note: Image of this product has been automatically sent to the customer's WhatsApp. Do not mention or include image URLs in your response.]"
            await _safe_send_media(
                url=r.image_url,
                caption=f"{r.name_en} — {discounted_price:.2f} {r.currency}",
                product_key=str(getattr(r, "id", None) or r.sku),
                zoho_item_id=getattr(r, "zoho_item_id", None),
            )

        formatted_results.append(desc)

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
    """Check the Zoho-confirmed exact stock level and unit price for a specific product SKU.

    Args:
        sku: The exact SKU identifier of the product.
    """
    logger.info(f"LLM Tool called: get_stock(sku={sku!r})")
    stock_info, catalog_product = await _resolve_inventory_item(ctx, sku)

    if not stock_info:
        if catalog_product:
            return _catalog_mismatch_customer_message()
        return f"Product with SKU {sku} not found in inventory."

    available = stock_info.get("stock_on_hand", 0)
    price = float(stock_info.get("rate", 0.0))
    currency = str(
        stock_info.get("currency_code") or stock_info.get("currency") or "AED"
    )
    stock_text = (
        f"Zoho-confirmed stock for {sku}: {available} items available. "
        f"Zoho-confirmed price: {price:.2f} {currency}."
    )
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
    Do not block on missing full name, company name, or email: use CRM/conversation fallback and resolve or create a valid Inventory customer first.

    Args:
        items: List of the SKUs and quantities to include in the quote.
    """
    logger.info(f"LLM Tool called: create_quotation(items={items})")

    # Needs to fetch item details from Zoho Inventory
    skus_to_fetch = [item.sku for item in items]
    raw_stock_details = await ctx.deps.zoho_inventory.get_stock_bulk(skus_to_fetch)
    stock_map: dict[str, dict[str, Any]] = {}
    catalog_products: dict[str, Any | None] = {}
    for raw_item in raw_stock_details:
        zoho_item = _coerce_inventory_item(raw_item, require_item_id=True)
        if zoho_item:
            stock_map[str(zoho_item["sku"])] = zoho_item

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
        zoho_item = stock_map.get(item.sku)
        normalized_sku = item.sku.strip()
        if normalized_sku not in catalog_products:
            catalog_products[normalized_sku] = await _find_catalog_product_by_sku(
                ctx.deps.db, item.sku
            )
        catalog_product = catalog_products[normalized_sku]
        if not zoho_item:
            resolved_item, catalog_product = await _resolve_inventory_item(
                ctx, item.sku
            )
            catalog_products[normalized_sku] = catalog_product
            zoho_item = (
                _coerce_inventory_item(resolved_item, require_item_id=True)
                if resolved_item
                else None
            )
            if not zoho_item:
                if catalog_product:
                    return _catalog_mismatch_customer_message()
                return f"Failed to create quotation: SKU {item.sku} not found."
            stock_map[item.sku] = zoho_item

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
                "image_url": None,
                "_catalog_image_url": getattr(catalog_product, "image_url", None),
            }
        )

    # Customer-facing quotation assets are catalog-owned. If the catalog image is
    # missing or cannot be downloaded, render the PDF without an image instead of
    # falling back to Zoho's operational media.
    import asyncio
    import base64
    import json as json_mod

    sem = asyncio.Semaphore(3)  # limit concurrent image downloads

    async def _fetch_image(tpl_item: dict[str, Any]) -> None:
        if not tpl_item.get("_catalog_image_url"):
            return
        async with sem:
            try:
                result = await _download_catalog_image(
                    str(tpl_item["_catalog_image_url"])
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
        ti.pop("_catalog_image_url", None)

    # Resolve customer data from CRM or conversation context
    # Priority: CRM contact > crm_context > conversation fields > fallback
    customer_name = ctx.deps.conversation.customer_name or "Valued Customer"
    customer_email = ""
    customer_company = ""

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
            customer_email = _string_value(contact.get("Email"))
            customer_company = _extract_crm_company(contact.get("Account_Name"))

    if ctx.deps.crm_context:
        customer_name = _string_value(
            ctx.deps.crm_context.get("Name")
            or ctx.deps.crm_context.get("Full_Name")
            or customer_name
        )
        customer_email = _string_value(
            ctx.deps.crm_context.get("Email") or customer_email
        )
        customer_company = _string_value(
            ctx.deps.crm_context.get("Company")
            or ctx.deps.crm_context.get("Account_Name")
            or customer_company
        )

    customer_id = await resolve_inventory_customer_id(
        phone=ctx.deps.conversation.phone,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_company=customer_company,
        zoho_inventory=ctx.deps.zoho_inventory,
    )
    if customer_id is None:
        return await _fail_closed_exact_quote_request(ctx.deps)

    # Create Draft Order in Zoho
    try:
        draft_resp = await ctx.deps.zoho_inventory.create_sale_order(
            customer_id=customer_id, items=zoho_line_items, status="draft"
        )
        saleorder_data = extract_sale_order_data(draft_resp)
        sale_order_number = _string_value(saleorder_data.get("salesorder_number"))
        quote_number = sale_order_number or "DRAFT"

        sale_order_id = _string_value(saleorder_data.get("salesorder_id"))
        if sale_order_id or sale_order_number:
            conv = ctx.deps.conversation
            metadata = dict(conv.metadata_ or {})
            if sale_order_id:
                metadata["zoho_sale_order_id"] = sale_order_id
            if sale_order_number:
                metadata["zoho_sale_order_number"] = sale_order_number
            conv.metadata_ = metadata
            try:
                await ctx.deps.db.flush()
            except Exception as flush_err:
                logger.warning(
                    "Failed to persist sale_order_id in metadata: %s", flush_err
                )
    except Exception as e:
        logger.error("Failed to create draft sale order: %s", e)
        return await _fail_closed_exact_quote_request(ctx.deps)

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
            json_mod.dumps(
                {
                    "quote_number": quote_number,
                    "filename": pdf_filename,
                    "salesorder_number": sale_order_number,
                    "salesorder_id": sale_order_id,
                }
            ),
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

    ctx.deps.quotation_created = True
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
    metadata = ctx.deps.conversation.metadata_ or {}
    sale_order_id = _string_value(metadata.get("zoho_sale_order_id"))
    active_sale_order_id = (
        sale_order_id
        if sale_order_id and _metadata_sale_order_is_active(metadata)
        else ""
    )
    deal_id = _string_value(ctx.deps.conversation.zoho_deal_id)

    if not deal_id and not active_sale_order_id:
        if language.startswith("ar"):
            return "لم يتم العثور على طلب مرتبط بهذه المحادثة. قد لا يكون لدى العميل صفقة مؤكدة بعد."
        return "No order found linked to this conversation. The customer may not have a confirmed deal yet."

    # Fetch Inventory sale order status first so metadata-only orders still work.
    order_data = None
    if active_sale_order_id:
        try:
            order_data = await ctx.deps.zoho_inventory.get_sale_order_status(
                active_sale_order_id
            )
        except Exception as e:
            logger.warning("Failed to fetch Inventory order status: %s", e)

    # Fetch CRM deal status
    deal_data = None
    if deal_id and ctx.deps.zoho_crm:
        try:
            deal_data = await ctx.deps.zoho_crm.get_deal_status(deal_id)
        except Exception as e:
            logger.warning("Failed to fetch CRM deal status: %s", e)

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

    def _get_verified_policy_repair_state() -> dict[str, int | str] | None:
        assert conv is not None
        metadata = conv.metadata_ if isinstance(conv.metadata_, dict) else {}
        state = metadata.get(VERIFIED_POLICY_REPAIR_KEY)
        if not isinstance(state, dict):
            return None
        kind = state.get("kind")
        count = state.get("count")
        if not isinstance(kind, str) or not isinstance(count, int):
            return None
        return {"kind": kind, "count": count}

    async def _set_verified_policy_repair_state(kind: str, count: int) -> None:
        assert conv is not None
        metadata = dict(conv.metadata_ or {})
        metadata[VERIFIED_POLICY_REPAIR_KEY] = {"kind": kind, "count": count}
        conv.metadata_ = metadata
        await db.flush()

    async def _clear_verified_policy_repair_state() -> None:
        assert conv is not None
        metadata = dict(conv.metadata_ or {})
        if VERIFIED_POLICY_REPAIR_KEY not in metadata:
            return
        metadata.pop(VERIFIED_POLICY_REPAIR_KEY, None)
        conv.metadata_ = metadata
        await db.flush()

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

    def _build_static_response(text: str, model_name: str) -> LLMResponse:
        return LLMResponse(
            text=unmask_pii(text, pii_map),
            tokens_in=0,
            tokens_out=0,
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
    recent_history = recent_history[-5:]
    current_user_entry = f"user: {masked_text}"
    if not recent_history or recent_history[-1] != current_user_entry:
        recent_history.append(current_user_entry)

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
        db_model_main = model_name_for_path(PATH_CORE_CHAT, db_model_main)

        dynamic_model = OpenAIChatModel(
            db_model_main,
            provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
            settings=model_settings_for_path(PATH_CORE_CHAT, model_name=db_model_main),
        )

        async def _run_agent(run_deps: SalesDeps) -> Any:
            return await run_agent_with_safety(
                sales_agent,
                PATH_CORE_CHAT,
                user_prompt=masked_text,
                deps=run_deps,
                message_history=history,
                model=dynamic_model,
                model_name=db_model_main,
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
                await _clear_verified_policy_repair_state()
                return _build_llm_response(first_result, db_model_main)

            second_result = await _run_agent(
                replace(
                    deps,
                    tool_mode="order_handoff",
                    runtime_directives=ORDER_HANDOFF_PASS_2_DIRECTIVES,
                )
            )
            await _clear_verified_policy_repair_state()
            return _build_llm_response(second_result, db_model_main)

        exact_quote_candidate = extract_exact_quote_candidate(masked_text)
        if exact_quote_candidate:
            first_exact_deps = replace(
                deps,
                tool_mode="exact_quote",
                runtime_directives=EXACT_QUOTE_PASS_1_DIRECTIVES,
            )
            first_result = await _run_agent(first_exact_deps)
            if first_exact_deps.quotation_created or _has_escalation(conv):
                await _clear_verified_policy_repair_state()
                return _build_llm_response(first_result, db_model_main)

            second_exact_deps = replace(
                deps,
                tool_mode="exact_quote",
                runtime_directives=EXACT_QUOTE_PASS_2_DIRECTIVES,
            )
            second_result = await _run_agent(second_exact_deps)
            if second_exact_deps.quotation_created or _has_escalation(conv):
                await _clear_verified_policy_repair_state()
                return _build_llm_response(second_result, db_model_main)

            resolved_exact_sku = await _resolve_exact_quote_candidate_sku(
                deps.db, exact_quote_candidate
            )
            if resolved_exact_sku:
                from pydantic_ai.usage import RunUsage

                fallback_ctx = RunContext(
                    deps=second_exact_deps,
                    retry=0,
                    messages=[],
                    prompt=masked_text,
                    model=dynamic_model,
                    usage=RunUsage(),
                )
                fallback_text = await create_quotation(
                    fallback_ctx,
                    [
                        QuotationItem(
                            sku=resolved_exact_sku,
                            quantity=exact_quote_candidate.quantity,
                        )
                    ],
                )
                if second_exact_deps.quotation_created or _has_escalation(conv):
                    await _clear_verified_policy_repair_state()
                    return _build_static_response(
                        fallback_text, f"{db_model_main}|exact-quote-fallback"
                    )

            fail_closed_text = await _fail_closed_exact_quote_request(second_exact_deps)
            await _clear_verified_policy_repair_state()
            return _build_static_response(
                fail_closed_text, f"{db_model_main}|exact-quote-fallback"
            )

        policy_action = policy_decision.policy_action
        if not policy_decision.is_order_status and policy_action == "clarify":
            repair_state = _get_verified_policy_repair_state()
            repair_count = (
                repair_state.get("count") if repair_state is not None else None
            )
            if (
                repair_state is not None
                and repair_state.get("kind") == "benign_no_match"
                and isinstance(repair_count, int)
                and repair_count >= 1
            ):
                policy_action = "handoff"
                await _clear_verified_policy_repair_state()
            else:
                await _set_verified_policy_repair_state("benign_no_match", 1)
                return _build_static_response(
                    build_clarification_response(str(deps.conversation.language)),
                    f"{db_model_main}|verified-policy-clarify",
                )

        if not policy_decision.is_order_status and policy_action == "handoff":
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
            await _clear_verified_policy_repair_state()
            return await _build_policy_handoff_response(
                db_model_main,
                str(deps.conversation.language),
                build_service_handoff_response(
                    policy_decision, str(deps.conversation.language)
                ),
            )

        if not policy_decision.is_order_status and policy_decision.question_class in {
            "service_low_risk",
            "service_high_risk",
        }:
            result = await _run_agent(
                replace(
                    deps,
                    tool_mode="service_policy",
                    runtime_directives=build_service_runtime_directives(
                        policy_decision
                    ),
                )
            )
            await _clear_verified_policy_repair_state()
            return _build_llm_response(result, db_model_main)

        result = await _run_agent(deps)
        await _clear_verified_policy_repair_state()
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
