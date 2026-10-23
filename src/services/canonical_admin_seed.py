"""Canonical Treejar knowledge-base articles and Noor operating rules.

The live ``knowledge_base`` and ``bot_behavior_rules`` tables held only
soft-deleted / archived QA smoke rows on 2026-10-23 (tj-ierv), so the bot
retrieved nothing from either on every customer turn. This module is the one
place that defines the canonical content and syncs it idempotently from the
admin dashboard.

Content rules (spec ``docs/specs/admin-dashboard-polish/spec.md`` section 3.1):

* Only owner-approved facts. FAQ answers come verbatim from ``docs/faq.md``.
  Questions 12 (price matching), 13 (warranty) and 17 (payment terms) touch
  manager-controlled terms (see ``src/llm/company_faq.py``) and are not seeded
  verbatim; the warranty / payment articles below defer the specific terms to
  the manager instead of inventing a number of days, years or a fee.
* Policies that the runtime already enforces (dual VAT pricing, B2B handoff
  routes, canonical product links) are described as the runtime does them.
* No free-delivery, free-assembly, return-window, warranty-term, working-hours
  or payment-method claims: no owner-approved source for them exists in the
  repository (explicit defer, see ``.codex/handoff.md``).

Nothing here touches the SHA256-pinned RAG files; embeddings go through the
public ``EmbeddingEngine`` API.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.models.bot_behavior_rule import BotBehaviorRule
from src.models.knowledge_base import KnowledgeBase
from src.rag.embeddings import EmbeddingEngine
from src.services.bot_behavior_rules import rule_embedding_text

logger = logging.getLogger(__name__)

_FAQ_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "faq.md"

CANONICAL_KB_SOURCE = "canonical_treejar"
CANONICAL_RULE_SOURCE_TYPE = "canonical_default"
CANONICAL_ACTOR = "canonical_seed"

# FAQ questions kept out of the verbatim seed: manager-controlled terms.
MANAGER_CONTROLLED_FAQ_QUESTIONS: frozenset[int] = frozenset({12, 13, 17})

TREEJAR_SHOWROOM_MAP_URL = (
    "https://www.google.com/maps/place/Treejar+Trading/@24.9871463,55.1135981,17z"
)

# Synthetic smoke-test rows (e.g. "QA disposable KB 20260511...") stay hidden
# in admin lists unless the operator searches for them explicitly.
QA_SYNTHETIC_TITLE_PREFIXES: tuple[str, ...] = ("QA disposable", "QA sentinel")


def search_mentions_qa(search: str | None) -> bool:
    return bool(search) and "qa" in str(search).casefold()


def qa_synthetic_title_clause(column: Any) -> ColumnElement[bool]:
    return or_(*(column.ilike(f"{prefix}%") for prefix in QA_SYNTHETIC_TITLE_PREFIXES))


def qa_synthetic_source_clause(column: Any) -> ColumnElement[bool]:
    return cast("ColumnElement[bool]", column.ilike("qa\\_%", escape="\\"))


@dataclass(frozen=True)
class CanonicalKnowledgeArticle:
    title: str
    category: str
    content: str
    language: str = "en"


@dataclass(frozen=True)
class CanonicalBotRule:
    key: str
    title: str
    type: str
    priority: int
    instruction: str
    topic: str
    trigger_examples: tuple[str, ...] = field(default_factory=tuple)
    scope: str = "global"
    stage: str | None = None


@dataclass
class CanonicalSyncCounts:
    created: int = 0
    updated: int = 0
    restored: int = 0
    unchanged: int = 0
    total_active: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "restored": self.restored,
            "unchanged": self.unchanged,
            "total_active": self.total_active,
        }


# ---------------------------------------------------------------------------
# Knowledge base
# ---------------------------------------------------------------------------

_POLICY_ARTICLES: tuple[CanonicalKnowledgeArticle, ...] = (
    CanonicalKnowledgeArticle(
        title="Delivery and installation across the UAE",
        category="delivery",
        content=(
            "Treejar provides professional delivery and installation (assembly) "
            "across the UAE, including Dubai. Ready-stock items are delivered "
            "within a few days from the Dubai warehouse; custom-made orders "
            "depend on design and quantity. The delivery and installation cost "
            "and the exact schedule are stated in the quotation or confirmed by "
            "the manager. Do not promise free delivery, free assembly or a "
            "specific delivery date unless the manager has confirmed it."
        ),
    ),
    CanonicalKnowledgeArticle(
        title="Returns, exchanges and warranty",
        category="warranty",
        content=(
            "Treejar offers a warranty that depends on the product type; the "
            "products are made for commercial use. The warranty term for a "
            "specific item and any return or exchange conditions are confirmed "
            "by the manager. Do not state a number of days for returns or a "
            "number of years for the warranty; offer to check it with the "
            "manager instead."
        ),
    ),
    CanonicalKnowledgeArticle(
        title="Prices, UAE 5% VAT and quotations",
        category="payment",
        content=(
            "Catalogue prices are shown without VAT. Every product price and "
            "every package total is given twice: excl. 5% VAT and incl. 5% VAT. "
            "Package totals and budget verdicts come from the deterministic "
            "package calculation, never from mental arithmetic. A formal PDF "
            "quotation is prepared once the customer's name, company or "
            "individual status, delivery address and the exact items and "
            "quantities are confirmed. Payment terms depend on order size and "
            "project scope and are agreed with the manager."
        ),
    ),
    CanonicalKnowledgeArticle(
        title="Showroom in Dubai",
        category="showroom",
        content=(
            "Customers are welcome to visit the Treejar showroom in Dubai, UAE, "
            "to experience the product quality in person. Location on Google "
            f"Maps: {TREEJAR_SHOWROOM_MAP_URL}. The visit time, and whether a "
            "particular product is on display to try, are arranged with the "
            "manager."
        ),
    ),
    CanonicalKnowledgeArticle(
        title="Wholesale orders (20+ units) and office projects",
        category="b2b",
        content=(
            "Bulk orders and large corporate or government office projects are "
            "Treejar's specialty. For 20 or more units, or when the customer "
            "asks for bulk or project pricing, Noor shows 2-3 suitable in-stock "
            "options from the live catalogue with their canonical product links, "
            "asks one short question for the project brief, and hands the "
            "request to a dedicated manager who prepares project pricing."
        ),
    ),
    CanonicalKnowledgeArticle(
        title="Custom-made office furniture",
        category="b2b",
        content=(
            "Treejar offers custom-made solutions through verified manufacturing "
            "partners in China and Europe: size, colour, material and design "
            "follow the client's requirements, and a detailed quotation follows "
            "once the requirement is understood. Custom requests (special "
            "dimensions, materials or built-in power) are handed to a project "
            "manager, while Noor immediately offers the closest standard "
            "in-stock alternatives."
        ),
    ),
    CanonicalKnowledgeArticle(
        title="Product categories Treejar supplies",
        category="products",
        content=(
            "Treejar supplies office furniture from ready stock in Dubai: office "
            "chairs (task and mesh chairs, executive seating, visitor chairs), "
            "desks, manager desks and multi-person workstations, meeting tables, "
            "storage (mobile pedestals, cabinets, lockers and safes), sofas and "
            "acoustic pods. Specific models, prices and stock levels are taken "
            "only from the live catalogue search and Zoho stock; product links "
            "always use https://treejartrading.ae/product/<slug>."
        ),
    ),
)


def _parse_faq_articles(text: str) -> tuple[CanonicalKnowledgeArticle, ...]:
    articles: list[CanonicalKnowledgeArticle] = []
    for part in text.split("\n## ")[1:]:
        heading, _, body = part.partition("\n")
        number, dot, title = heading.strip().partition(". ")
        if not dot or not number.isdigit() or not body.strip():
            continue
        if int(number) in MANAGER_CONTROLLED_FAQ_QUESTIONS:
            continue
        title = title.strip()
        answer = body.strip().rstrip("-").strip()
        articles.append(
            CanonicalKnowledgeArticle(
                title=f"FAQ: {title}",
                category="faq",
                content=f"Q: {title}\nA: {answer}",
            )
        )
    return tuple(articles)


@lru_cache(maxsize=1)
def canonical_faq_articles() -> tuple[CanonicalKnowledgeArticle, ...]:
    try:
        text = _FAQ_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Canonical FAQ source is missing: %s", _FAQ_PATH)
        return ()
    return _parse_faq_articles(text)


def canonical_kb_articles() -> tuple[CanonicalKnowledgeArticle, ...]:
    """Every canonical knowledge-base article: policies first, then FAQ."""
    return (*_POLICY_ARTICLES, *canonical_faq_articles())


# ---------------------------------------------------------------------------
# Bot behavior rules (lower priority number = applied first)
# ---------------------------------------------------------------------------

CANONICAL_BOT_RULES: tuple[CanonicalBotRule, ...] = (
    CanonicalBotRule(
        key="vat_dual_pricing",
        title="UAE 5% VAT dual pricing",
        type="hard_rule",
        priority=10,
        topic="pricing_vat",
        instruction=(
            "Whenever you state a product price or a total, give it both excl. "
            "5% VAT and incl. 5% VAT. Catalogue prices are excl. VAT. Never "
            "show only one of the two figures."
        ),
        trigger_examples=("How much is this chair?", "Price with VAT?"),
    ),
    CanonicalBotRule(
        key="package_math_budget",
        title="Deterministic package math and budget verdict",
        type="hard_rule",
        priority=12,
        topic="pricing_vat",
        instruction=(
            "For several items or a budget question, use only the package "
            "calculation provided by the runtime (quantity x unit price lines, "
            "total excl. and incl. 5% VAT). State clearly whether the package "
            "fits the customer's budget or by how much it exceeds it. Never "
            "compute totals yourself."
        ),
        trigger_examples=(
            "I need 6 desks and 6 chairs, budget 15000 AED",
            "What is the total for all of this?",
        ),
    ),
    CanonicalBotRule(
        key="canonical_product_links",
        title="Canonical product links only",
        type="hard_rule",
        priority=14,
        topic="catalog_links",
        instruction=(
            "Link products only with their canonical product page "
            "https://treejartrading.ae/product/<slug>. Never send image or "
            "media storage links (such as r2.dev) as product links."
        ),
        trigger_examples=("Send me the link", "Where can I see this product?"),
    ),
    CanonicalBotRule(
        key="no_hallucinated_facts",
        title="No invented stock, delivery or specifications",
        type="hard_rule",
        priority=16,
        topic="grounding",
        instruction=(
            "State stock figures, delivery terms, fees, dates and product "
            "specifications only when a tool result or approved company fact in "
            "this turn supports them. If nothing supports a figure, do not give "
            "one; say what will be checked and with whom."
        ),
        trigger_examples=("Is it in stock?", "When can you deliver?"),
    ),
    CanonicalBotRule(
        key="wholesale_handoff",
        title="Wholesale (20+ units) handoff with in-stock options",
        type="escalation_rule",
        priority=20,
        topic="handoff_b2b",
        instruction=(
            "For 20 or more units or a bulk / project pricing request: show 2-3 "
            "suitable in-stock options from the catalogue search with canonical "
            "links, ask exactly one short question for the project brief, and "
            "pass the request to the manager through the escalation tool."
        ),
        trigger_examples=(
            "I need 40 chairs for our new office",
            "Do you give wholesale prices?",
        ),
    ),
    CanonicalBotRule(
        key="custom_furniture_handoff",
        title="Custom furniture handoff with standard alternatives",
        type="escalation_rule",
        priority=22,
        topic="handoff_custom",
        instruction=(
            "For made-to-order requests (custom dimensions, materials, built-in "
            "power, bespoke design): offer the closest standard in-stock "
            "alternatives right away and pass the custom request to the project "
            "manager through the escalation tool."
        ),
        trigger_examples=(
            "Can you make a 3.2 m conference table?",
            "We need desks in our corporate colour",
        ),
    ),
    CanonicalBotRule(
        key="out_of_catalog_sourcing",
        title="Out-of-catalog sourcing notice without freezing the chat",
        type="escalation_rule",
        priority=24,
        topic="sourcing_out_of_catalog",
        instruction=(
            "When the customer asks for an item outside the office furniture "
            "catalogue, notify the manager as a sourcing request and keep "
            "helping in the same conversation with what the catalogue does "
            "offer. Do not tell the customer to wait for the manager."
        ),
        trigger_examples=("Do you sell coffee machines?", "Can you get a projector?"),
    ),
    CanonicalBotRule(
        key="concise_consultative_tone",
        title="Concise consultative tone with one clarifying question",
        type="style_rule",
        priority=50,
        topic="tone_consultation",
        instruction=(
            "Keep replies short and consultative, in the customer's language "
            "(English or Arabic). Focus on the customer's job to be done and ask "
            "at most one clarifying question per reply."
        ),
        trigger_examples=("Hi", "I am furnishing a new office"),
    ),
)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(UTC)


async def sync_canonical_knowledge_base(
    db: AsyncSession,
    embedding_engine: EmbeddingEngine | None = None,
    *,
    actor: str = CANONICAL_ACTOR,
    articles: Sequence[CanonicalKnowledgeArticle] | None = None,
) -> dict[str, int]:
    """Upsert canonical articles by ``(source, title)`` and embed changed rows.

    The caller owns the transaction (commit / audit).
    """
    del actor  # recorded by the caller's audit row
    catalog = tuple(articles) if articles is not None else canonical_kb_articles()
    titles = [article.title for article in catalog]
    existing_result = await db.execute(
        select(KnowledgeBase).where(
            KnowledgeBase.source == CANONICAL_KB_SOURCE,
            KnowledgeBase.title.in_(titles),
        )
    )
    existing = {row.title: row for row in existing_result.scalars().all()}

    counts = CanonicalSyncCounts()
    to_embed: list[KnowledgeBase] = []
    now = _now()
    for article in catalog:
        row = existing.get(article.title)
        if row is None:
            row = KnowledgeBase(
                id=uuid.uuid4(),
                source=CANONICAL_KB_SOURCE,
                title=article.title,
                content=article.content,
                language=article.language,
                category=article.category,
                is_auto_generated=False,
                updated_at=now,
            )
            db.add(row)
            to_embed.append(row)
            counts.created += 1
            continue

        content_changed = (
            row.content != article.content
            or row.category != article.category
            or row.language != article.language
        )
        restored = row.deleted_at is not None
        needs_embedding = content_changed or row.embedding is None
        if restored:
            row.deleted_at = None
            row.deleted_by = None
        if content_changed:
            row.content = article.content
            row.category = article.category
            row.language = article.language
        if needs_embedding:
            to_embed.append(row)
        if restored:
            counts.restored += 1
        elif needs_embedding:
            counts.updated += 1
        else:
            counts.unchanged += 1
        if restored or needs_embedding:
            row.updated_at = now

    if to_embed:
        engine = embedding_engine or EmbeddingEngine()
        embeddings = await engine.embed_batch_async([row.content for row in to_embed])
        for row, embedding in zip(to_embed, embeddings, strict=True):
            row.embedding = embedding

    counts.total_active = len(catalog)
    return counts.as_dict()


def _rule_metadata(rule: CanonicalBotRule) -> dict[str, Any]:
    return {
        "source_type": CANONICAL_RULE_SOURCE_TYPE,
        "canonical_key": rule.key,
        "topic": rule.topic,
    }


def _canonical_key(row: BotBehaviorRule) -> str | None:
    metadata = row.metadata_ if isinstance(row.metadata_, dict) else {}
    if metadata.get("source_type") != CANONICAL_RULE_SOURCE_TYPE:
        return None
    key = metadata.get("canonical_key")
    return key if isinstance(key, str) else None


async def sync_canonical_bot_behavior_rules(
    db: AsyncSession,
    embedding_engine: EmbeddingEngine | None = None,
    *,
    actor: str = CANONICAL_ACTOR,
    rules: Sequence[CanonicalBotRule] | None = None,
) -> dict[str, int]:
    """Upsert canonical rules by ``metadata.canonical_key``; keep them active.

    The caller owns the transaction (commit / audit).
    """
    catalog = tuple(rules) if rules is not None else CANONICAL_BOT_RULES
    existing_result = await db.execute(select(BotBehaviorRule))
    existing: dict[str, BotBehaviorRule] = {}
    for existing_row in existing_result.scalars().all():
        key = _canonical_key(existing_row)
        if key is not None:
            existing.setdefault(key, existing_row)

    counts = CanonicalSyncCounts()
    to_embed: list[BotBehaviorRule] = []
    now = _now()
    for rule in catalog:
        row = existing.get(rule.key)
        desired: dict[str, Any] = {
            "title": rule.title,
            "type": rule.type,
            "priority": rule.priority,
            "scope": rule.scope,
            "stage": rule.stage,
            "language": None,
            "segment": None,
            "instruction": rule.instruction,
            "trigger_examples": list(rule.trigger_examples),
        }
        if row is None:
            row = BotBehaviorRule(
                id=uuid.uuid4(),
                status="active",
                created_by=actor,
                updated_by=actor,
                updated_at=now,
                archived_at=None,
                metadata_=_rule_metadata(rule),
                **desired,
            )
            db.add(row)
            to_embed.append(row)
            counts.created += 1
            continue

        changed = any(getattr(row, name) != value for name, value in desired.items())
        restored = row.status != "active" or row.archived_at is not None
        needs_embedding = changed or row.embedding is None
        if changed:
            for name, value in desired.items():
                setattr(row, name, value)
        if restored:
            row.status = "active"
            row.archived_at = None
        if needs_embedding:
            to_embed.append(row)
        if restored:
            counts.restored += 1
        elif needs_embedding:
            counts.updated += 1
        else:
            counts.unchanged += 1
        if restored or needs_embedding:
            row.metadata_ = _rule_metadata(rule)
            row.updated_by = actor
            row.updated_at = now

    if to_embed:
        engine = embedding_engine or EmbeddingEngine()
        embeddings = await engine.embed_batch_async(
            [rule_embedding_text(row) for row in to_embed]
        )
        for row, embedding in zip(to_embed, embeddings, strict=True):
            row.embedding = embedding

    counts.total_active = len(catalog)
    return counts.as_dict()
