from __future__ import annotations

import datetime
import json
import logging
import re
import sys
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from functools import wraps
from typing import Annotated, Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, ValidationError
from pydantic_ai import RunContext, ToolReturn
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from src.dialogue.claim_contract import (
    AttributeClaim,
    ClaimInput,
    ContractResult,
    RetrievedRow,
    apply_contract,
    assumption_eligible_paths,
    signals_a_project,
)
from src.dialogue.state import DialogueState
from src.integrations.crm.zoho_crm import ZohoCRMClient
from src.integrations.inventory.zoho_inventory import ZohoInventoryClient
from src.integrations.messaging.base import MessagingProvider
from src.llm.money import (
    AMOUNT_TOKEN_PATTERN,
    BUDGET_AED_CURRENCY_PATTERN,
    canonical_amount,
)
from src.llm.response_policy import AskKind, append_required_tool_disclosure
from src.llm.response_runtime import LLMResponse, ProductMediaPayload
from src.llm.verified_answers import VerifiedAnswerDecision
from src.models.conversation import Conversation
from src.models.product import Product
from src.rag.embeddings import EmbeddingEngine
from src.services.customer_language import is_arabic_customer_language
from src.services.escalation_state import is_active_human_handoff
from src.services.runtime_execution_evidence import (
    RuntimeToolTrace,
    build_runtime_tool_trace,
)

logger = logging.getLogger("src.llm.engine")

_VERIFIED_CATALOG_RECOVERY_MAX_CHARS = 900
_VERIFIED_CATALOG_FIELD_MAX_CHARS = 256
_CROSS_SELL_REQUEST_RE = re.compile(r"\bcross(?:-|\s)?sell\b", re.IGNORECASE)


def _engine_runtime() -> Any:
    return sys.modules["src.llm.engine"]


def _normalize_text(text: str) -> str:
    return cast("str", _engine_runtime()._normalize_text(text))


def _coerce_inventory_item(
    raw_item: Any,
    *,
    require_item_id: bool,
) -> dict[str, Any] | None:
    return cast(
        "dict[str, Any] | None",
        _engine_runtime()._coerce_inventory_item(
            raw_item,
            require_item_id=require_item_id,
        ),
    )


def _has_explicit_quote_hold(text: str) -> bool:
    return cast("bool", _engine_runtime()._has_explicit_quote_hold(text))


def _no_verified_cross_sell_disclosure(
    language: str,
    *,
    has_budget: bool = True,
) -> str:
    return cast(
        "str",
        _engine_runtime()._no_verified_cross_sell_disclosure(
            language,
            has_budget=has_budget,
        ),
    )


def _string_value(value: Any) -> str:
    return cast("str", _engine_runtime()._string_value(value))


def _valid_catalog_price(catalog_product: Any | None) -> float | None:
    return cast(
        "float | None",
        _engine_runtime()._valid_catalog_price(catalog_product),
    )


async def recommend_products(*args: Any, **kwargs: Any) -> Any:
    return await _engine_runtime().recommend_products(*args, **kwargs)


# The Treejar catalogue itself is written with Cyrillic lookalikes, so this map
# is load-bearing rather than defensive. Measured in production 2026-08-08:
# 7 of 920 SKUs literally begin with Cyrillic "СН" -- Skyland chairs such as
# "СН 135 black" -- and 132 product names use Cyrillic "х" as the dimension
# separator, as in "1000х500х754". A customer typing Latin "CH 135" must still
# reach the row whose SKU is Cyrillic, and vice versa. Deleting this map silently
# unmatches those products; tj-4e5j nearly did exactly that.
_SKU_HOMOGLYPH_TRANSLATION = str.maketrans(
    {
        "А": "A",
        "В": "B",
        "Е": "E",
        "К": "K",
        "М": "M",
        "Н": "H",
        "О": "O",
        "Р": "P",
        "С": "C",
        "Т": "T",
        "Х": "X",
        "У": "Y",
        "а": "a",
        "в": "b",
        "е": "e",
        "к": "k",
        "м": "m",
        "н": "h",
        "о": "o",
        "р": "p",
        "с": "c",
        "т": "t",
        "х": "x",
        "у": "y",
    }
)

_ACTIVE_PRODUCT_MEDIA_AUDIT_STATUSES = (
    "pending",
    "sent",
    "delivered",
    "read",
    "edited",
    "provider_duplicate",
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


def _explicit_product_option_cap(text: str) -> int | None:
    """Return a small explicit recommendation cap from the customer request."""
    normalized = " ".join(text.casefold().split())
    if not normalized:
        return None

    if re.search(
        r"\b(?:one|1)\s+(?:or|to)\s+(?:two|2)\b"
        r"(?=.{0,80}\b(?:options?|alternatives?|recommendations?|products?)\b)",
        normalized,
    ):
        return 2
    if re.search(r"(?:خيارًا|خيارا)\s+أو\s+خيارين", normalized):
        return 2

    count_match = re.search(
        r"\b(?:up to|at most|no more than|recommend|show|suggest|give|compare)"
        r"(?:\s+me)?\s+(?P<count>one|two|three|1|2|3)\b"
        r"(?=.{0,80}\b(?:options?|alternatives?|recommendations?|products?)\b)",
        normalized,
    )
    if count_match is None:
        return None

    return {
        "one": 1,
        "1": 1,
        "two": 2,
        "2": 2,
        "three": 3,
        "3": 3,
    }[count_match.group("count")]


_PLANNING_COUNT_VALUES = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "واحد": 1,
    "واحدة": 1,
    "اثنان": 2,
    "اثنين": 2,
    "ثلاثة": 3,
    "أربعة": 4,
    "اربعة": 4,
    "خمسة": 5,
    "ستة": 6,
    "سبعة": 7,
    "ثمانية": 8,
    "تسعة": 9,
    "عشرة": 10,
    "أحد عشر": 11,
    "احد عشر": 11,
    "اثنا عشر": 12,
    "اثني عشر": 12,
}
_PLANNING_CAPACITY_RE = re.compile(
    r"\b(?P<count>\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve)(?:[\s-]+)(?:(?:[a-z][\w-]*)\s+){0,2}"
    r"(?:person|people|staff|employees?|users?|designers?|seats?)\b",
    re.IGNORECASE,
)
_AR_PLANNING_CAPACITY_RE = re.compile(
    r"(?<!\w)ل?(?P<count>\d{1,3}|واحد(?:ة)?|اثنان|اثنين|ثلاثة|أربعة|اربعة|خمسة|"
    r"ستة|سبعة|ثمانية|تسعة|عشرة|أحد عشر|احد عشر|اثنا عشر|اثني عشر)\s+"
    r"(?:موظف(?:ين|ا?[ًٌٍَُِّْٰ]*)|مستخدم(?:ين|ا?[ًٌٍَُِّْٰ]*)|"
    r"مصمم(?:ين|ا?[ًٌٍَُِّْٰ]*)|مقعد(?:ا?[ًٌٍَُِّْٰ]*)|مقاعد)(?!\w)",
    re.IGNORECASE,
)
_CATALOG_CAPACITY_RE = re.compile(
    r"\b(?P<count>\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve)(?:[\s-]+)(?:person|people|staff|employees?|users?|seats?)\b",
    re.IGNORECASE,
)
_CATALOG_UNIT_PRODUCT_TERMS = (
    "chair",
    "desk",
    "stool",
)
CatalogFamily = Literal["seating", "workspace", "storage", "privacy"]
CatalogFactDomain = Literal["acoustic", "footprint"]
CatalogAmount = Annotated[float, Field(ge=0, le=10_000_000)]
_ACOUSTIC_FACT_GAP = "acoustic_performance=not_stated"
_FOOTPRINT_FACT_GAP = "footprint_dimensions=not_stated"
_CATALOG_PRODUCT_FAMILIES: tuple[tuple[CatalogFamily, tuple[str, ...]], ...] = (
    ("seating", ("chair", "stool", "seat", "كرسي", "كراسي")),
    (
        "workspace",
        (
            "desk",
            "table",
            "workstation",
            "bench",
            "مكتب",
            "مكاتب",
            "طاولة",
            "طاولات",
            "محطة عمل",
            "محطات عمل",
        ),
    ),
    (
        "storage",
        (
            "pedestal",
            "cabinet",
            "locker",
            "storage",
            "shelf",
            "shelves",
            "accessory",
            "accessories",
            "خزانة",
            "خزائن",
            "تخزين",
        ),
    ),
    ("privacy", ("pod", "booth", "كبسولة", "مقصورة")),
)
_GENERIC_OFFICE_OPENING_RE = re.compile(
    r"\b(?:small|new|our|the|an?|your)?\s*office\b|(?:مكتب|مكاتب)",
    re.IGNORECASE,
)
_CATALOG_PLANNING_KEY = "catalog_planning_v1"
_VERIFIED_CATALOG_PLAN_KEY = "verified_catalog_plan_v1"
_CATALOG_BUDGET_CURRENCY = "AED"
_CATALOG_DECISION_CANDIDATES_PER_FAMILY = 6
_CATALOG_CROSS_SELL_SOURCE: dict[CatalogFamily, str] = {
    "seating": "chair",
    "workspace": "desk",
    "storage": "filing_cabinet",
    "privacy": "acoustic_panel",
}
_CATALOG_BUDGET_CAP_RE = re.compile(
    r"(?:\b(?:under|below|within|up\s+to|maximum|max(?:imum)?\s+of)\s+"
    rf"(?:(?P<currency_before>{BUDGET_AED_CURRENCY_PATTERN})\s*)?"
    rf"(?P<amount_before>{AMOUNT_TOKEN_PATTERN})"
    rf"(?:\s*(?P<currency_after>{BUDGET_AED_CURRENCY_PATTERN}))?\b|"
    rf"\b(?P<currency_leading>{BUDGET_AED_CURRENCY_PATTERN})\s*"
    rf"(?P<amount_leading>{AMOUNT_TOKEN_PATTERN})\s+"
    r"(?:or\s+less|max(?:imum)?|cap)\b)",
    re.IGNORECASE,
)
_PER_ITEM_PRICE_RE = re.compile(
    r"\b(?:each|apiece|per\s+[\w-]+)\b|(?:لكل|للقطعة)",
    re.IGNORECASE,
)
_TOTAL_BUDGET_RE = re.compile(
    r"\b(?:total|overall|combined|complete\s+total)\b|"
    r"(?:الإجمالي|الاجمالي)",
    re.IGNORECASE,
)
_BUDGET_CLAUSE_BOUNDARY_RE = re.compile(
    r"[.;\n،؛]|\b(?:and|but|then)\b",
    re.IGNORECASE,
)
_CATALOG_COMPLETE_COVERAGE_TERMS = (
    "cheaper",
    "lowest cost",
    "complete configuration",
    "full configuration",
    "cover all",
    "all seats",
    "all staff",
    "الأرخص",
    "اقل تكلفة",
    "أقل تكلفة",
    "تكوين كامل",
)
_CATALOG_CONTINUATION_TERMS = (
    "this",
    "that",
    "same",
    "selected",
    "configuration",
    "cheaper",
    "alternative",
    "cross-sell",
    "cross sell",
    "remaining",
    "continue",
    "instead",
    "correction",
    "update",
    "هذا",
    "هذه",
    "نفس",
    "التكوين",
    "المتبقي",
    "استمر",
    "بدلا",
    "تحديث",
)
_NEW_CATALOG_INTENT_RE = re.compile(
    r"\b(?:now\s+)?(?:i|we)\s+(?:need|want|am\s+looking\s+for|"
    r"are\s+looking\s+for)\b|(?:أحتاج|احتاج|نحتاج|أريد|اريد)",
    re.IGNORECASE,
)
_NEW_CATALOG_ACTION_RE = re.compile(
    r"\b(?:new|another)\b|"
    r"(?:جديد|الجديد|جديدة|الجديدة|آخر|اخر|أخرى|اخرى)",
    re.IGNORECASE,
)
_NEW_CATALOG_CONTEXT_RE = re.compile(
    r"\b(?:office|order|configuration|request|project)\b|"
    r"(?:مكتب|التكوين|طلب|مشروع)",
    re.IGNORECASE,
)
_CATALOG_OPTION_CONTEXT_RE = re.compile(
    r"\b(?:option|alternative|variant)\b|(?:خيار|بديل)",
    re.IGNORECASE,
)
_CATALOG_PLAN_REFERENCE_RE = re.compile(
    r"\b(?:this|that|same|selected)\s+(?:selected\s+)?"
    r"(?:configuration|selection|plan)\b|"
    r"(?:هذا|هذه|نفس)\s+(?:التكوين|الاختيار|الخطة)",
    re.IGNORECASE,
)
_ADD_CATALOG_ACTION_RE = re.compile(
    r"\b(?:add|also|too)\b|(?:أضف|اضف|أيضاً|أيضا|ايضاً|ايضا)",
    re.IGNORECASE,
)
_REPLACE_CATALOG_ACTION_RE = re.compile(
    r"\b(?:instead|replace|switch|swap)\b|(?:بدلا|بدلاً|استبدل)",
    re.IGNORECASE,
)


class CatalogPlanningContext(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    version: Literal[1, 2] = 2
    epoch: int = Field(default=1, ge=1, le=1_000_000)
    requested_seats: int | None = Field(default=None, gt=0, le=1000)
    families: tuple[CatalogFamily, ...] = ()
    complete_coverage: bool = False
    budget_cap: float | None = Field(default=None, gt=0, le=10_000_000)
    per_item_cap: float | None = Field(default=None, gt=0, le=10_000_000)
    family_totals: dict[CatalogFamily, CatalogAmount] = Field(default_factory=dict)

    @property
    def selected_total(self) -> float | None:
        required_families = set(self.families)
        if not required_families or not required_families.issubset(self.family_totals):
            return None
        return round(
            sum(self.family_totals[family] for family in required_families),
            2,
        )


@dataclass(frozen=True, slots=True)
class VerifiedCatalogLine:
    family: CatalogFamily
    name: str
    sku: str
    quantity: int
    unit_price: float
    total: float
    currency: str
    stock: int
    capacity: int


@dataclass(frozen=True, slots=True)
class VerifiedOpeningCatalogLine:
    """One purchasable catalog row selected before an opening can ask a form."""

    family: CatalogFamily
    name: str
    sku: str
    unit_price: float
    currency: str
    stock: int


@dataclass(frozen=True, slots=True)
class StockSnapshot:
    sku: str
    available: int
    source: Literal["zoho", "catalog"]
    as_of: datetime.datetime
    provenance: Literal["authoritative", "unconfirmed"] = "authoritative"


@dataclass(frozen=True, slots=True)
class CatalogCoverageGap:
    family: str
    requested: int
    covered: int
    resolution: Literal["source_additional_stock", "adjust_quantity"]
    closing_question: str


@dataclass(frozen=True, slots=True)
class CatalogDecision:
    requirements: tuple[str, ...]
    selected_lines: tuple[VerifiedCatalogLine, ...]
    requested_seats: int | None
    budget_cap: float | None
    stock_snapshots: tuple[StockSnapshot, ...]
    recommendation: str
    unknown_properties: tuple[str, ...] = ()
    coverage_gaps: tuple[CatalogCoverageGap, ...] = ()


def validate_catalog_decision(decision: CatalogDecision) -> CatalogDecision:
    """Validate model-independent recommendation facts before materialization."""
    snapshots: dict[str, StockSnapshot] = {}
    for snapshot in decision.stock_snapshots:
        key = snapshot.sku.strip().casefold()
        if not key or snapshot.available < 0 or snapshot.as_of.tzinfo is None:
            raise ValueError("invalid stock snapshot")
        if (snapshot.source, snapshot.provenance) not in {
            ("zoho", "authoritative"),
            ("catalog", "unconfirmed"),
        }:
            raise ValueError("stock source and provenance disagree")
        previous = snapshots.get(key)
        if previous is not None and previous.available != snapshot.available:
            raise ValueError(f"conflicting stock for SKU {snapshot.sku}")
        if previous is None or snapshot.source == "zoho":
            snapshots[key] = snapshot

    total = 0.0
    coverage_by_family: dict[str, int] = {}
    sku_count_by_family: dict[str, set[str]] = {}
    for line in decision.selected_lines:
        key = line.sku.strip().casefold()
        stock_snapshot = snapshots.get(key)
        if stock_snapshot is None or stock_snapshot.source != "zoho":
            raise ValueError(f"selected SKU {line.sku} lacks Zoho stock")
        if line.quantity <= 0 or stock_snapshot.available < line.quantity:
            raise ValueError(f"selected SKU {line.sku} exceeds Zoho stock")
        if abs(line.total - line.quantity * line.unit_price) > 0.01:
            raise ValueError(f"selected SKU {line.sku} has inconsistent total")
        total += line.total
        coverage_by_family[line.family] = (
            coverage_by_family.get(line.family, 0) + line.quantity * line.capacity
        )
        sku_count_by_family.setdefault(line.family, set()).add(key)

    if decision.budget_cap is not None and round(total, 2) > decision.budget_cap:
        raise ValueError("selected configuration exceeds budget")
    gaps_by_family: dict[str, CatalogCoverageGap] = {}
    question_count = 0
    for gap in decision.coverage_gaps:
        if gap.family in gaps_by_family:
            raise ValueError(f"duplicate coverage gap for family {gap.family}")
        if gap.requested <= 0 or gap.covered < 0 or gap.covered >= gap.requested:
            raise ValueError(f"invalid coverage gap for family {gap.family}")
        question_count += gap.closing_question.count("?") + gap.closing_question.count(
            "؟"
        )
        gaps_by_family[gap.family] = gap
    if decision.coverage_gaps and question_count != 1:
        raise ValueError("partial plan requires one closing question")

    if decision.requested_seats is not None:
        for family in decision.requirements:
            covered = coverage_by_family.get(family, 0)
            current_gap = gaps_by_family.get(family)
            if current_gap is not None:
                gaps_by_family.pop(family)
            if covered < decision.requested_seats:
                if (
                    current_gap is None
                    or current_gap.requested != decision.requested_seats
                    or current_gap.covered != covered
                ):
                    raise ValueError(f"incomplete coverage for family {family}")
            elif current_gap is not None:
                raise ValueError(f"unexpected coverage gap for family {family}")
            if len(sku_count_by_family.get(family, set())) > 2:
                raise ValueError(f"too many SKUs for family {family}")
    if gaps_by_family:
        raise ValueError("coverage gap references an unrequested family")
    return decision


def _catalog_decision_runtime_directive(deps: SalesDeps) -> str | None:
    decision = deps.catalog_decision
    if decision is None:
        return None
    try:
        validate_catalog_decision(decision)
    except ValueError:
        return None
    payload = {
        "catalog_decision": {
            "lines": [
                {
                    "sku": line.sku,
                    "qty": line.quantity,
                    "unit": line.unit_price,
                    "total": line.total,
                    "currency": line.currency,
                }
                for line in decision.selected_lines
            ],
            "budget": decision.budget_cap,
            "coverage_gaps": [
                {
                    "family": gap.family,
                    "requested": gap.requested,
                    "covered": gap.covered,
                    "uncovered": gap.requested - gap.covered,
                    "resolution": gap.resolution,
                    "closing_question": gap.closing_question or None,
                }
                for gap in decision.coverage_gaps
            ],
            "cross_sell": (
                {
                    "name": deps.verified_cross_sell.name,
                    "sku": deps.verified_cross_sell.sku,
                    "price": deps.verified_cross_sell.price,
                    "currency": deps.verified_cross_sell.currency,
                }
                if deps.verified_cross_sell is not None
                else None
            ),
            "quote_created": False,
        }
    }
    compact_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return (
        "Render one customer-facing recommendation from catalog_decision only. "
        "Include every SKU, quantity, unit price and line total; preserve the "
        "customer language and state that no quotation was created. Do not add "
        f"products or facts. {compact_payload}"
    )


def _catalog_number_in_text(text: str, value: int | float) -> bool:
    normalized = text.replace(",", "")
    candidates = {f"{float(value):.2f}", f"{float(value):g}"}
    return any(
        re.search(
            rf"(?<![\d.]){re.escape(candidate)}(?!\d|\.\d)",
            normalized,
        )
        is not None
        for candidate in candidates
    )


_CATALOG_DECISION_UNUSABLE = "unusable"


def _catalog_decision_defects(text: str, deps: SalesDeps) -> tuple[str, ...]:
    """Name what is wrong with a rendered catalog decision.

    This used to answer only yes or no, and a no threw the reply away for a
    template. A named defect can be handed back to the model instead, which is
    what the engine now does: the check was right to fire on S05, but the
    substitute dropped a whole product family to fix a cross-sell that had one
    bad number in it.

    ``_CATALOG_DECISION_UNUSABLE`` means there is nothing to repair against —
    no decision, no text, or a decision that does not validate. Those go
    straight to the fallback.
    """

    decision = deps.catalog_decision
    if decision is None or not isinstance(text, str) or not text.strip():
        return (_CATALOG_DECISION_UNUSABLE,)
    try:
        validate_catalog_decision(decision)
    except ValueError:
        return (_CATALOG_DECISION_UNUSABLE,)

    defects: list[str] = []
    normalized = text.casefold()
    allowed_skus = {line.sku.strip().casefold() for line in decision.selected_lines}
    if deps.verified_cross_sell is not None and deps.verified_cross_sell.sku:
        allowed_skus.add(deps.verified_cross_sell.sku.strip().casefold())
    mentioned_by_fold: dict[str, str] = {}
    for match in re.finditer(
        r"\bsku\s*[:#-]?\s*([a-z0-9][a-z0-9._/-]*)",
        text,
        re.IGNORECASE,
    ):
        written = match.group(1).strip()
        mentioned_by_fold.setdefault(written.casefold(), written)
    mentioned_skus = set(mentioned_by_fold)
    invented = sorted(mentioned_by_fold[fold] for fold in mentioned_skus - allowed_skus)
    if invented:
        defects.append(
            "these SKUs are not in the verified decision and must not appear: "
            f"{', '.join(invented)}"
        )
    for line in decision.selected_lines:
        sku = line.sku.strip().casefold()
        index = normalized.find(sku)
        if index < 0:
            defects.append(f"SKU {line.sku} is missing from the reply")
            continue
        window = normalized[max(0, index - 100) : index + 260]
        wrong = [
            label
            for label, value in (
                ("quantity", line.quantity),
                ("unit price", line.unit_price),
                ("line total", line.total),
            )
            if not _catalog_number_in_text(window, value)
        ]
        if wrong:
            defects.append(
                f"SKU {line.sku} must state {', '.join(wrong)} exactly as "
                f"{line.quantity} x {line.unit_price} = {line.total}"
            )
    cross_sell = deps.verified_cross_sell
    if cross_sell is not None and (
        cross_sell.name.casefold() not in normalized
        or not _catalog_number_in_text(normalized, cross_sell.price)
    ):
        defects.append(
            f"the verified cross-sell {cross_sell.name} at {cross_sell.price} "
            "is missing or priced differently"
        )
    no_quote_created = re.search(
        r"(?:\bno\s+(?:formal\s+)?(?:quotation|quote).{0,24}\bcreated\b|"
        r"\b(?:quotation|quote).{0,24}\bnot\s+created\b|"
        r"لم\s+يتم\s+إنشاء\s+عرض\s+سعر)",
        normalized,
    )
    if not (_has_explicit_quote_hold(text) or no_quote_created is not None):
        defects.append("the reply must state that no quotation was created")
    return tuple(defects)


def _catalog_decision_output_is_valid(text: str, deps: SalesDeps) -> bool:
    return not _catalog_decision_defects(text, deps)


def _catalog_decision_repair_directive(defects: tuple[str, ...]) -> str | None:
    """Hand the defect back instead of replacing the reply.

    The engine already repairs claim-contract failures this way. A rejected
    catalog decision is the same shape of problem: the facts are settled and
    only the rendering is wrong, so naming the wrong part costs one run and
    keeps a person's sentence.
    """

    if not defects or _CATALOG_DECISION_UNUSABLE in defects:
        return None
    numbered = "; ".join(f"({index}) {d}" for index, d in enumerate(defects, start=1))
    return (
        "Your previous reply was rejected against catalog_decision. Fix exactly "
        f"these problems and render the recommendation again: {numbered}. Keep "
        "the reasoning, the recommendation and the customer's language; change "
        "nothing else and add no products or facts."
    )


def _catalog_recovery_output_is_valid(text: str, deps: SalesDeps) -> bool:
    if not isinstance(text, str) or not text.strip():
        return False
    selected_by_family = (
        deps.current_catalog_selections or deps.verified_catalog_selections
    )
    selected_lines = tuple(
        line
        for family in dict.fromkeys(deps.catalog_planning.families)
        for line in selected_by_family.get(family, ())
    )
    if not selected_lines:
        return False
    normalized = text.casefold()
    for line in selected_lines:
        sku = line.sku.strip().casefold()
        index = normalized.find(sku)
        if index < 0:
            return False
        window = normalized[max(0, index - 100) : index + 260]
        if not all(
            _catalog_number_in_text(window, value)
            for value in (line.quantity, line.unit_price, line.total)
        ):
            return False
    cross_sell = deps.verified_cross_sell
    if cross_sell is not None and (
        cross_sell.name.casefold() not in normalized
        or not _catalog_number_in_text(normalized, cross_sell.price)
    ):
        return False
    no_quote_created = re.search(
        r"(?:\bno\s+(?:formal\s+)?(?:quotation|quote).{0,24}\bcreated\b|"
        r"\b(?:quotation|quote).{0,24}\bnot\s+created\b|"
        r"لم\s+يتم\s+إنشاء\s+عرض\s+سعر)",
        normalized,
    )
    return _has_explicit_quote_hold(text) or no_quote_created is not None


@dataclass(frozen=True, slots=True)
class VerifiedCrossSell:
    name: str
    sku: str | None
    price: float
    currency: str
    stock: int


@dataclass(frozen=True, slots=True)
class VerifiedCatalogFactProduct:
    name: str
    sku: str
    price: float | None
    currency: str
    stock: int
    description: str
    capacity: int | None
    fact_gaps: tuple[str, ...]
    search_call: int = 0
    result_rank: int = 0


@dataclass(frozen=True, slots=True)
class _CatalogCoverageCandidate:
    family: CatalogFamily
    name: str
    sku: str
    capacity: int
    stock: int
    unit_price: float
    currency: str


@dataclass(frozen=True)
class CatalogBudgetConstraints:
    total_cap: float | None = None
    per_item_cap: float | None = None


def _planning_count_value(raw: str) -> int:
    normalized = raw.casefold()
    return (
        int(normalized) if normalized.isdigit() else _PLANNING_COUNT_VALUES[normalized]
    )


def _requested_seat_count(text: str) -> int | None:
    normalized = _normalize_text(text)
    match = _PLANNING_CAPACITY_RE.search(normalized)
    if match is None:
        match = _AR_PLANNING_CAPACITY_RE.search(normalized)
    return _planning_count_value(match.group("count")) if match else None


@dataclass(frozen=True)
class AnchorFamily:
    """One family the anchor is allowed to name, and how a row joins it."""

    key: str
    name_terms: tuple[str, ...]
    taxonomy_terms: tuple[str, ...]
    label_en: str
    label_ar: str


@dataclass(frozen=True)
class AnchorCatalogRow:
    """One catalog row as the anchor reads it."""

    name: str
    category: str | None
    subcategory: str | None
    price: float | None
    stock: int | None


@dataclass(frozen=True)
class CatalogAnchor:
    """Rendered floor plus the volume caveat the winning rows require."""

    line: str
    has_limited_stock: bool


# Narrower than the family term lists on purpose: the anchor names what it
# prices. A row joins a family only when its name *and* its catalog taxonomy
# both say so, and it joins exactly one -- the first it matches.
#
# `tj-3jo0`: the name alone was not enough. "Desk height pedestal", a Storage /
# Pedestal row, headed "desks and workstations" and priced the whole clause at
# AED 154 while the cheapest orderable desk or workstation was AED 491. The same
# rule counted workstation chairs as desks. Requiring the taxonomy to agree
# removes both, and the order below settles the overlap the honest way: a
# workstation chair is a chair.
_ANCHOR_FAMILIES: tuple[AnchorFamily, ...] = (
    AnchorFamily(
        key="seating",
        name_terms=("chair",),
        taxonomy_terms=("chair",),
        label_en="Chairs",
        label_ar="الكراسي",
    ),
    AnchorFamily(
        key="workspace",
        name_terms=("desk", "workstation"),
        taxonomy_terms=("desk", "workstation"),
        label_en="desks and workstations",
        label_ar="المكاتب ومحطات العمل",
    ),
)
# An anchor is the price one customer can act on now. Owner decision 2026-08-14:
# one available unit is a real purchasable floor; volume is a separate promise
# and is disclosed whenever the winning row has fewer than five units.
_ANCHOR_MIN_STOCK = 1
_anchor_line_cache: dict[str, CatalogAnchor | None] = {}


def _anchor_part(lowest: float, *, label: str, is_arabic: bool) -> str:
    amount = f"{float(lowest):,.0f}"
    return f"{label} من {amount} درهم" if is_arabic else f"{label} from AED {amount}"


def anchor_family_of_row(row: AnchorCatalogRow) -> AnchorFamily | None:
    """The one family this row may be priced under, or none."""

    name = str(row.name or "").casefold()
    taxonomy = f"{row.category or ''} {row.subcategory or ''}".casefold()
    for family in _ANCHOR_FAMILIES:
        names_it = any(term in name for term in family.name_terms)
        catalogued_as_it = any(term in taxonomy for term in family.taxonomy_terms)
        if names_it and catalogued_as_it:
            return family
    return None


def catalog_anchor_from_catalog_rows(
    rows: Iterable[AnchorCatalogRow],
    *,
    language: str,
) -> CatalogAnchor | None:
    """The same anchor as `catalog_anchor`, from rows already in hand.

    `tj-rdqc`: the measured round has no database. It has the pinned catalog
    snapshot the retrieval evidence was built on, which holds the same rows the
    query below reads, so it derives the anchor here rather than sending an
    opening with no price where production adds one. The families, the stock
    floor and the wording are declared once and used by both callers, so a
    round follows production when production changes.

    A row missing either number is skipped exactly as the query's `IS NOT NULL`
    skips it.
    """

    is_arabic = is_arabic_customer_language(language)
    lowest: dict[str, tuple[float, int]] = {}
    for row in rows:
        price, stock = row.price, row.stock
        if price is None or stock is None or price <= 0 or stock < _ANCHOR_MIN_STOCK:
            continue
        family = anchor_family_of_row(row)
        if family is None:
            continue
        current = lowest.get(family.key)
        if current is None or price < current[0]:
            lowest[family.key] = (price, stock)
    parts = [
        _anchor_part(
            lowest[family.key][0],
            label=(family.label_ar if is_arabic else family.label_en),
            is_arabic=is_arabic,
        )
        for family in _ANCHOR_FAMILIES
        if family.key in lowest
    ]
    if not parts:
        return None
    # `tj-b8il`: Arabic separates clauses with its own comma. The full stop is
    # the Latin one in both languages -- Modern Standard Arabic writes it that
    # way, and U+06D4 belongs to Urdu and Persian, not to a UAE customer.
    separator = "، " if is_arabic else ", "
    return CatalogAnchor(
        line=separator.join(parts) + ".",
        has_limited_stock=any(stock < 5 for _price, stock in lowest.values()),
    )


def anchor_line_from_catalog_rows(
    rows: Iterable[AnchorCatalogRow],
    *,
    language: str,
) -> str | None:
    """Compatibility surface for callers that only need the exact line."""

    anchor = catalog_anchor_from_catalog_rows(rows, language=language)
    return anchor.line if anchor is not None else None


async def catalog_anchor(db: AsyncSession, language: str) -> CatalogAnchor | None:
    """Build the live purchasable price floor and its volume qualification.

    The cheapest live row in each of the two families a customer names first.
    It exists so the opening reply carries a real number before the customer has
    told us anything, which is what both research reports of 2026-08-09 say the
    first message must do.

    Every figure is a catalog row. There is no fallback text with a number in
    it: if the catalog cannot answer, the reply simply goes out without an
    anchor rather than with an invented one.

    `tj-3jo0`: this used to run one `MIN(price)` per family in SQL, which is why
    it could not tell a Storage / Pedestal row from a desk -- the query only saw
    the name. It reads the orderable rows and hands them to the same pure
    function the measured round uses, so there is one family rule and not two.
    """

    from src.models.product import Product

    is_arabic = is_arabic_customer_language(language)
    cache_key = "ar" if is_arabic else "en"
    if cache_key in _anchor_line_cache:
        return _anchor_line_cache[cache_key]

    result = await db.execute(
        select(
            Product.name_en,
            Product.category,
            Product.subcategory,
            Product.price,
            Product.stock,
        ).where(
            Product.price.is_not(None),
            Product.price > 0,
            Product.stock >= _ANCHOR_MIN_STOCK,
        )
    )
    rows = [
        AnchorCatalogRow(
            name=str(name or ""),
            category=category,
            subcategory=subcategory,
            price=(float(price) if isinstance(price, int | float | Decimal) else None),
            stock=stock,
        )
        for name, category, subcategory, price, stock in result.all()
    ]

    anchor = catalog_anchor_from_catalog_rows(rows, language=language)
    _anchor_line_cache[cache_key] = anchor
    return anchor


async def catalog_anchor_line(db: AsyncSession, language: str) -> str | None:
    """Compatibility surface for callers that only need the exact line."""

    anchor = await catalog_anchor(db, language)
    return anchor.line if anchor is not None else None


# `tj-7vhq`. The anchor puts a price on the table before the customer has asked
# for one, and on a bare greeting -- a third of every conversation this channel
# has -- that is the whole point of it. On a message that is not about furniture
# it is worse than silence: on 2026-08-13 a job application received chair and
# desk prices and, three sentences later, the news that this channel cannot
# process applications.
#
# The test is deliberately one-sided. Saying nothing about furniture still earns
# the anchor, because that is the case it was built for; only a message that
# positively says it is about something else loses it. A named piece of
# furniture then wins the argument back, so a supplier pitching chairs is still
# answered with our own prices.
#
# The word "furniture" is not one of those names, and that is the whole
# calibration: the applicant on dialog 28 wrote it about the industry they want
# to work in. A need is stated in items -- a chair, a desk, ten workstations --
# and the industry is stated in the abstract noun.
_ANCHORLESS_OPENING_RE = re.compile(
    r"\bcv\b|\bresum(?:e|es)\b|curriculum\s+vitae|\bvacanc(?:y|ies)\b"
    r"|\bjob\s+(?:application|vacanc(?:y|ies)|opening|opportunit(?:y|ies)|interview)\b"
    r"|\b(?:looking|apply(?:ing)?)\s+for\s+(?:a\s+|any\s+)?job\b"
    r"|\bhiring\b|\brecruit(?:er|ment|ing)?\b|\bapplicants?\b"
    r"|\bapply\s+for\s+(?:a|the|this|any)\s+(?:position|role|vacancy)\b"
    r"|\bemployment\b|\bsalary\b|\binternship\b|\bfresher\b"
    r"|tracking\s+number|\bawb\b|\bwaybill\b|out\s+for\s+delivery|\bconsignment\b"
    r"|\bcourier\b|\bshipments?\b|has\s+been\s+(?:shipped|dispatched|delivered)"
    r"|investment\s+opportunit(?:y|ies)|\bseo\b|digital\s+marketing|\bbacklinks?\b"
    r"|\bcrypto\w*|business\s+proposal|partnership\s+proposal"
    r"|سيرة\s*ذاتية|وظيف|وظائف|توظيف|أبحث\s+عن\s+عمل|راتب"
    r"|رقم\s+التتبع|شحنة|الشحنة|تم\s+الشحن"
    r"|تسويق\s+رقمي|فرصة\s+استثمار",
    re.IGNORECASE | re.UNICODE,
)
_FURNITURE_MENTION_RE = re.compile(
    r"\bchairs?\b|\bdesks?\b|\btables?\b|\bsofas?\b|\bcabinets?\b"
    r"|\bworkstations?\b|\bpedestals?\b|\bwardrobes?\b|\bshel(?:f|ves|ving)\b"
    r"|\bcredenzas?\b|\bpartitions?\b|\bcatalogue?s?\b"
    r"|كرسي|كراسي|مكتب|مكاتب|طاولة|طاولات|كنب|خزانة|خزائن|رفوف|كتالوج",
    re.IGNORECASE | re.UNICODE,
)


def opening_wants_a_price_anchor(customer_text: str) -> bool:
    """Whether a first turn on this message should carry the catalog anchor."""

    text = str(customer_text or "")
    if not _ANCHORLESS_OPENING_RE.search(text):
        return True
    return bool(_FURNITURE_MENTION_RE.search(text))


def _turn_owes_the_company_question(deps: SalesDeps) -> bool:
    """Does rule 13 apply to this turn, and has nobody asked yet?

    Three conditions, all of them about the world or about stored state, none
    about what Noor believes she already did. That distinction is the one four
    rules died on in `tj-2m5m.8`, and it is why the last condition reads the
    `company_activity` slot rather than the transcript: the slot is written only
    by `record_customer_requirements`, which is to say only when the customer
    actually said it.

    The middle condition is what stops this firing on a seven-chair order. Rule
    13 is expertise on a fit-out and friction on a shopping trip, which is the
    whole point of the 2026-08-09 fork.
    """

    conversation = deps.conversation
    state = DialogueState.from_conversation(conversation)
    if _string_value(state.slots.company_activity):
        return False
    if not _string_value(state.slots.company) and not _string_value(
        getattr(conversation, "zoho_contact_id", None)
    ):
        return False
    customer_texts = [text for text in (deps.user_query,) if text]
    customer_texts.extend(
        entry.split(":", 1)[1] if ":" in entry else entry
        for entry in (deps.recent_history or ())
        if entry.startswith("user:")
    )
    return any(signals_a_project(text) for text in customer_texts)


def _catalog_product_capacity(product_text: str) -> int | None:
    normalized = _normalize_text(product_text)
    match = _CATALOG_CAPACITY_RE.search(normalized)
    if match:
        return _planning_count_value(match.group("count"))
    if any(
        _contains_catalog_term(normalized, term) for term in _CATALOG_UNIT_PRODUCT_TERMS
    ):
        return 1
    return None


def _contains_catalog_term(normalized: str, term: str) -> bool:
    arabic = re.search(r"[\u0600-\u06ff]", term) is not None
    prefix = "(?:و)?(?:ال)?" if arabic else ""
    suffix = "" if arabic else "(?:s|es)?"
    return (
        re.search(
            rf"(?<!\w){prefix}{re.escape(term.casefold())}{suffix}(?!\w)",
            normalized,
            flags=re.UNICODE,
        )
        is not None
    )


def _catalog_product_families(text: str) -> tuple[CatalogFamily, ...]:
    normalized = _normalize_text(text)
    return tuple(
        family
        for family, terms in _CATALOG_PRODUCT_FAMILIES
        if any(_contains_catalog_term(normalized, term) for term in terms)
    )


def _catalog_product_family(text: str) -> CatalogFamily | None:
    matched = _catalog_product_families(text)
    return matched[0] if len(matched) == 1 else None


def _catalog_search_query_with_constraints(
    query: str,
    customer_text: str,
    planning: CatalogPlanningContext | None = None,
) -> str:
    requested_seats = (
        planning.requested_seats
        if planning is not None and planning.requested_seats is not None
        else _requested_seat_count(customer_text)
    )
    enriched = " ".join(query.split())
    if requested_seats is not None and _requested_seat_count(enriched) is None:
        enriched = f"{enriched} {requested_seats} person"

    normalized_customer = _normalize_text(customer_text)
    normalized_query = _normalize_text(enriched)
    customer_needs_privacy = any(
        term in normalized_customer
        for term in ("private", "privacy", "divider", "panel", "screen", "enclosed")
    )
    query_has_privacy = any(
        term in normalized_query
        for term in ("private", "privacy", "divider", "panel", "screen", "enclosed")
    )
    if customer_needs_privacy and not query_has_privacy:
        enriched = f"{enriched} privacy panels"
    return enriched


def _requests_complete_catalog_coverage(text: str) -> bool:
    normalized = _normalize_text(text)
    return any(
        _contains_catalog_term(normalized, term)
        for term in _CATALOG_COMPLETE_COVERAGE_TERMS
    )


def _needs_complete_catalog_coverage(text: str) -> bool:
    return _requested_seat_count(text) is not None and (
        _requests_complete_catalog_coverage(text)
    )


def _budget_clause(
    normalized: str,
    amount_match: re.Match[str],
) -> str:
    boundaries = tuple(_BUDGET_CLAUSE_BOUNDARY_RE.finditer(normalized))
    clause_start = max(
        (
            boundary.end()
            for boundary in boundaries
            if boundary.end() <= amount_match.start()
        ),
        default=0,
    )
    clause_end = min(
        (
            boundary.start()
            for boundary in boundaries
            if boundary.start() >= amount_match.end()
        ),
        default=len(normalized),
    )
    return normalized[clause_start:clause_end]


def _catalog_budget_constraints(text: str) -> CatalogBudgetConstraints:
    normalized = _normalize_text(text)
    total_cap: float | None = None
    per_item_cap: float | None = None
    for match in _CATALOG_BUDGET_CAP_RE.finditer(normalized):
        raw_amount = match.group("amount_before") or match.group("amount_leading")
        normalized_amount = canonical_amount(raw_amount)
        if normalized_amount is None:
            continue
        amount = float(normalized_amount)
        if not 0 < amount <= 10_000_000:
            continue
        clause = _budget_clause(normalized, match)
        if _PER_ITEM_PRICE_RE.search(clause) and not _TOTAL_BUDGET_RE.search(clause):
            per_item_cap = amount
        else:
            total_cap = amount
    return CatalogBudgetConstraints(
        total_cap=total_cap,
        per_item_cap=per_item_cap,
    )


def _catalog_budget_cap(text: str) -> float | None:
    return _catalog_budget_constraints(text).total_cap


def _catalog_replacement_families(
    text: str,
    current_families: tuple[CatalogFamily, ...],
    previous_families: tuple[CatalogFamily, ...],
) -> tuple[CatalogFamily, ...]:
    normalized = _normalize_text(text)
    target_text = normalized
    if " instead of " in normalized:
        target_text = normalized.split(" instead of ", maxsplit=1)[0]
    elif " بدلا من " in normalized or " بدلاً من " in normalized:
        marker = " بدلا من " if " بدلا من " in normalized else " بدلاً من "
        target_text = normalized.split(marker, maxsplit=1)[0]
    elif match := re.search(
        r"\b(?:replace\b.+?\bwith|switch\b.+?\bto)\b(?P<target>.+)",
        normalized,
    ):
        target_text = match.group("target")

    target_families = _catalog_product_families(target_text)
    if target_families:
        return target_families
    non_previous = tuple(
        family for family in current_families if family not in previous_families
    )
    return non_previous or current_families


def _catalog_planning_from_metadata(
    conversation: Conversation,
) -> CatalogPlanningContext:
    metadata = (
        conversation.metadata_ if isinstance(conversation.metadata_, Mapping) else {}
    )
    raw = metadata.get(_CATALOG_PLANNING_KEY)
    if not isinstance(raw, Mapping):
        return CatalogPlanningContext()
    try:
        planning = CatalogPlanningContext.model_validate(raw)
        planning.version = 2
        return planning
    except ValidationError:
        logger.warning(
            "Ignored invalid catalog planning state for conversation %s",
            conversation.id,
        )
        return CatalogPlanningContext()


def _catalog_planning_for_turn(
    conversation: Conversation,
    recent_history: Sequence[str],
    current_text: str,
) -> CatalogPlanningContext:
    planning = _catalog_planning_from_metadata(conversation)
    user_turns = [
        entry.removeprefix("user:").strip()
        for entry in recent_history[-5:]
        if entry.startswith("user:")
    ]
    if not user_turns or user_turns[-1] != current_text:
        user_turns.append(current_text)

    normalized_current = _normalize_text(current_text)
    current_families = _catalog_product_families(current_text)
    disjoint_family_request = bool(
        current_families and set(current_families).isdisjoint(planning.families)
    )
    has_new_marker = _NEW_CATALOG_ACTION_RE.search(current_text) is not None
    starts_new_epoch = (
        has_new_marker
        and _CATALOG_OPTION_CONTEXT_RE.search(current_text) is None
        and (
            _NEW_CATALOG_CONTEXT_RE.search(current_text) is not None
            or (
                disjoint_family_request
                and _NEW_CATALOG_INTENT_RE.search(current_text) is not None
            )
        )
    )
    replaces_family = _REPLACE_CATALOG_ACTION_RE.search(current_text) is not None
    adds_family = _ADD_CATALOG_ACTION_RE.search(current_text) is not None
    explicit_new_intent = _NEW_CATALOG_INTENT_RE.search(current_text) is not None
    references_plan = _CATALOG_PLAN_REFERENCE_RE.search(current_text) is not None
    references_existing = any(
        _contains_catalog_term(normalized_current, term)
        for term in _CATALOG_CONTINUATION_TERMS
    )
    is_continuation = adds_family or (
        not starts_new_epoch and not replaces_family and references_existing
    )
    starts_independent_intent = (
        bool(planning.families)
        and bool(current_families)
        and not replaces_family
        and not adds_family
        and (
            starts_new_epoch
            or (explicit_new_intent and not references_plan)
            or (not is_continuation and disjoint_family_request)
        )
    )
    if starts_independent_intent:
        planning = CatalogPlanningContext(epoch=planning.epoch + 1)
        user_turns = [current_text]

    current_requested_seats = _requested_seat_count(current_text)
    if (
        current_requested_seats is not None
        and current_requested_seats != planning.requested_seats
    ):
        planning.family_totals = {}
    planning.requested_seats = current_requested_seats or planning.requested_seats
    if replaces_family and current_families:
        replacement_families = _catalog_replacement_families(
            current_text,
            current_families,
            planning.families,
        )
        planning.families = replacement_families
        planning.family_totals = {
            family: total
            for family, total in planning.family_totals.items()
            if family in replacement_families
        }
    elif current_families:
        planning.families = (
            tuple(dict.fromkeys((*planning.families, *current_families)))
            if is_continuation
            else current_families
        )
    current_budget = _catalog_budget_constraints(current_text)
    planning.budget_cap = current_budget.total_cap or planning.budget_cap
    planning.per_item_cap = current_budget.per_item_cap or planning.per_item_cap
    for turn in reversed(user_turns):
        planning.requested_seats = planning.requested_seats or _requested_seat_count(
            turn
        )
        if not planning.families:
            planning.families = _catalog_product_families(turn)
        turn_budget = _catalog_budget_constraints(turn)
        planning.budget_cap = planning.budget_cap or turn_budget.total_cap
        planning.per_item_cap = planning.per_item_cap or turn_budget.per_item_cap

    planning.complete_coverage = planning.complete_coverage or any(
        _requests_complete_catalog_coverage(turn) for turn in user_turns
    )
    if (
        planning.requested_seats is not None
        and not planning.families
        and any(_GENERIC_OFFICE_OPENING_RE.search(turn) for turn in user_turns)
    ):
        # R02 names the use and headcount but not a product noun. That is
        # enough state to show one chair and one desk before asking anything;
        # it is not enough to claim a full fit-out or create a quotation.
        planning.families = ("seating", "workspace")
    return planning


async def _store_catalog_planning(
    db: AsyncSession,
    conversation: Conversation,
    planning: CatalogPlanningContext,
) -> None:
    metadata = dict(conversation.metadata_ or {})
    if not any(
        (
            planning.requested_seats,
            planning.complete_coverage,
            planning.budget_cap,
            planning.per_item_cap,
            planning.family_totals,
            metadata.get(_CATALOG_PLANNING_KEY),
        )
    ):
        return
    payload = planning.model_dump(mode="json")
    if metadata.get(_CATALOG_PLANNING_KEY) == payload:
        return
    metadata[_CATALOG_PLANNING_KEY] = payload
    conversation.metadata_ = metadata
    await db.flush()


def _minimum_catalog_coverage_total(
    variants: Sequence[tuple[int, int, float]],
    requested_seats: int,
) -> float | None:
    if requested_seats <= 0:
        return None
    costs: dict[int, float] = {0: 0.0}
    for capacity, stock, unit_price in variants:
        if capacity <= 0 or stock <= 0 or unit_price <= 0:
            continue
        max_units = min(stock, (requested_seats + capacity - 1) // capacity)
        updated = dict(costs)
        for covered, cost in costs.items():
            for quantity in range(1, max_units + 1):
                new_covered = min(requested_seats, covered + quantity * capacity)
                new_cost = cost + quantity * unit_price
                previous = updated.get(new_covered)
                if previous is None or new_cost < previous:
                    updated[new_covered] = new_cost
        costs = updated
    total = costs.get(requested_seats)
    return round(total, 2) if total is not None else None


def _minimum_catalog_coverage_selection(
    candidates: Sequence[_CatalogCoverageCandidate],
    requested_seats: int,
) -> tuple[VerifiedCatalogLine, ...] | None:
    return _catalog_coverage_selection(
        candidates,
        requested_seats,
        allow_partial=False,
    )


def _best_catalog_coverage_selection(
    candidates: Sequence[_CatalogCoverageCandidate],
    requested_seats: int,
) -> tuple[VerifiedCatalogLine, ...] | None:
    return _catalog_coverage_selection(
        candidates,
        requested_seats,
        allow_partial=True,
    )


def _catalog_coverage_selection(
    candidates: Sequence[_CatalogCoverageCandidate],
    requested_seats: int,
    *,
    allow_partial: bool,
) -> tuple[VerifiedCatalogLine, ...] | None:
    if requested_seats <= 0 or not candidates:
        return None
    states: dict[int, tuple[int, float, tuple[int, ...]]] = {
        0: (0, 0.0, (0,) * len(candidates))
    }
    for index, candidate in enumerate(candidates):
        if candidate.capacity <= 0 or candidate.stock <= 0 or candidate.unit_price <= 0:
            continue
        max_units = min(
            candidate.stock,
            (requested_seats + candidate.capacity - 1) // candidate.capacity,
        )
        updated = dict(states)
        for covered, (sku_count, cost, quantities) in states.items():
            for quantity in range(1, max_units + 1):
                new_covered = min(
                    requested_seats,
                    covered + quantity * candidate.capacity,
                )
                new_cost = cost + quantity * candidate.unit_price
                previous = updated.get(new_covered)
                new_score = (sku_count + 1, new_cost)
                if previous is not None and previous[:2] <= new_score:
                    continue
                new_quantities = list(quantities)
                new_quantities[index] = quantity
                updated[new_covered] = (*new_score, tuple(new_quantities))
        states = updated

    selected = states.get(requested_seats)
    if selected is None and allow_partial:
        best_covered = max(states)
        selected = states[best_covered] if best_covered > 0 else None
    if selected is None:
        return None
    sku_count, _, quantities = selected
    if sku_count > 2:
        return None
    lines = tuple(
        VerifiedCatalogLine(
            family=candidate.family,
            name=candidate.name,
            sku=candidate.sku,
            quantity=quantity,
            unit_price=round(candidate.unit_price, 2),
            total=round(quantity * candidate.unit_price, 2),
            currency=candidate.currency,
            stock=candidate.stock,
            capacity=candidate.capacity,
        )
        for candidate, quantity in zip(candidates, quantities, strict=True)
        if quantity > 0
    )
    return lines or None


def _catalog_product_text(product: Any) -> str:
    return " ".join(
        str(value).strip()
        for value in (
            getattr(product, "name_en", None),
            getattr(product, "name_ar", None),
            getattr(product, "description_en", None),
            getattr(product, "description_ar", None),
            getattr(product, "category", None),
            getattr(product, "subcategory", None),
        )
        if value
    )


def _catalog_coverage_candidates(
    planning: CatalogPlanningContext,
    products: Sequence[Any],
    *,
    customer_context: str,
    segment: str,
) -> dict[CatalogFamily, list[_CatalogCoverageCandidate]]:
    from src.core.discounts import apply_discount

    required_families = tuple(dict.fromkeys(planning.families))
    needs_lumbar = _requests_confirmed_lumbar_support(customer_context)
    candidates: dict[CatalogFamily, list[_CatalogCoverageCandidate]] = {
        family: [] for family in required_families
    }
    for product in products:
        product_text = _catalog_product_text(product)
        family = _catalog_product_family(product_text)
        if family not in candidates:
            continue
        if (
            family == "seating"
            and needs_lumbar
            and not _has_positive_lumbar_support(product_text)
        ):
            continue
        sku = str(getattr(product, "sku", "") or "").strip()
        name = str(getattr(product, "name_en", "") or "").strip()
        currency = str(getattr(product, "currency", "") or "").strip().upper()
        stock = max(int(getattr(product, "stock", 0) or 0), 0)
        capacity = _catalog_product_capacity(product_text)
        raw_price = _valid_catalog_price(product)
        if (
            not sku
            or not name
            or len(sku) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
            or len(name) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
            or currency != _CATALOG_BUDGET_CURRENCY
            or stock <= 0
            or capacity is None
            or capacity <= 0
            or raw_price is None
        ):
            continue
        unit_price = round(float(apply_discount(raw_price, segment)), 2)
        if unit_price <= 0 or (
            planning.per_item_cap is not None and unit_price > planning.per_item_cap
        ):
            continue
        candidates[family].append(
            _CatalogCoverageCandidate(
                family=family,
                name=name,
                sku=sku,
                capacity=capacity,
                stock=stock,
                unit_price=unit_price,
                currency=currency,
            )
        )
    return candidates


def _solve_verified_catalog_selections(
    planning: CatalogPlanningContext,
    products: Sequence[Any],
    *,
    customer_context: str,
    segment: str,
    authoritative_stock_by_sku: Mapping[str, int] | None = None,
) -> dict[CatalogFamily, tuple[VerifiedCatalogLine, ...]] | None:
    requested_seats = planning.requested_seats
    required_families = tuple(dict.fromkeys(planning.families))
    if (
        requested_seats is None
        or requested_seats <= 0
        or not required_families
        or not planning.complete_coverage
    ):
        return None

    candidates = _catalog_coverage_candidates(
        planning,
        products,
        customer_context=customer_context,
        segment=segment,
    )

    selections: dict[CatalogFamily, tuple[VerifiedCatalogLine, ...]] = {}
    for family in required_families:
        family_candidates = sorted(
            candidates[family],
            key=lambda item: (
                item.unit_price / item.capacity,
                item.unit_price,
                item.name.casefold(),
                item.sku,
            ),
        )
        if authoritative_stock_by_sku is not None:
            family_candidates = [
                replace(
                    candidate,
                    stock=max(
                        authoritative_stock_by_sku.get(
                            candidate.sku.strip().casefold(), 0
                        ),
                        0,
                    ),
                )
                for candidate in family_candidates
            ]
        selection = _best_catalog_coverage_selection(
            family_candidates,
            requested_seats,
        )
        selections[family] = selection or ()

    if not any(selections.values()):
        return None

    currencies = {
        line.currency.strip().upper()
        for family_lines in selections.values()
        for line in family_lines
    }
    selected_total = _catalog_selection_total(selections, required_families)
    if (
        len(currencies) != 1
        or selected_total is None
        or (planning.budget_cap is not None and selected_total > planning.budget_cap)
    ):
        return None
    return selections


def _catalog_selection_total(
    selections: Mapping[CatalogFamily, tuple[VerifiedCatalogLine, ...]],
    families: Sequence[CatalogFamily],
) -> float | None:
    required_families = set(families)
    if not required_families or not required_families.issubset(selections):
        return None
    return round(
        sum(line.total for family in required_families for line in selections[family]),
        2,
    )


def _catalog_coverage_gaps(
    selections: Mapping[CatalogFamily, tuple[VerifiedCatalogLine, ...]],
    families: Sequence[CatalogFamily],
    requested_seats: int,
) -> tuple[CatalogCoverageGap, ...]:
    gaps: list[CatalogCoverageGap] = []
    for family in dict.fromkeys(families):
        covered = sum(
            line.quantity * line.capacity for line in selections.get(family, ())
        )
        if covered >= requested_seats:
            continue
        uncovered = requested_seats - covered
        gaps.append(
            CatalogCoverageGap(
                family=family,
                requested=requested_seats,
                covered=covered,
                resolution="source_additional_stock",
                closing_question=(
                    f"Should I source {uncovered} additional {family} unit"
                    f"{'s' if uncovered != 1 else ''}?"
                    if not gaps
                    else ""
                ),
            )
        )
    return tuple(gaps)


def _catalog_remaining_budget(
    planning: CatalogPlanningContext,
    selections: Mapping[CatalogFamily, tuple[VerifiedCatalogLine, ...]] | None = None,
) -> float | None:
    selected_total = (
        planning.selected_total
        if selections is None
        else _catalog_selection_total(selections, planning.families)
    )
    if planning.budget_cap is None or selected_total is None:
        return None
    return round(max(planning.budget_cap - selected_total, 0.0), 2)


_LUMBAR_SUPPORT_TERMS = (
    "lumbar",
    "lower back",
    "lower-back",
    "دعم قطني",
    "دعما قطنيا",
    "الدعم القطني",
    "أسفل الظهر",
    "اسفل الظهر",
)
_LUMBAR_CLAUSE_BOUNDARY_RE = re.compile(
    r"[.!?؟;؛\n]|\b(?:but|however)\b|(?:لكن|ولكن)",
    re.IGNORECASE,
)
_LUMBAR_PRE_NEGATION_RE = re.compile(
    r"(?:\bno\b|\bwithout\b|"
    r"\b(?:do|does|did)\s+not\s+"
    r"(?:need|require|want|include|provide|have|feature)\b|"
    r"\b(?:don't|doesn't|didn't)\s+"
    r"(?:need|require|want|include|provide|have|feature)\b|"
    r"\b(?:am|are|is|was|were)\s+not\s+"
    r"(?:(?:asking|looking)\s+for|interested\s+in)\b|"
    r"لا\s+(?:أحتاج|احتاج|نحتاج|أريد|اريد|نريد|يريد|يتضمن|تتضمن|"
    r"يوجد|يتوفر|تتوفر|يوفر|توفر|نبحث)|"
    r"بدون|دون|غير\s+مطلوب)"
    r"[^.!?؟;؛\n]{0,28}$",
    re.IGNORECASE,
)
_LUMBAR_POST_NEGATION_RE = re.compile(
    r"^\s*(?:support\s+)?(?:"
    r"(?:is|are|was|were)\s+(?:not|unconfirmed|unstated|unavailable|"
    r"unsupported|absent|missing)\b|"
    r"(?:isn't|aren't|wasn't|weren't)\b|"
    r"(?:does|do|did)\s+not\s+(?:exist|include|provide)\b|"
    r"غير\s+(?:متوفر|متضمن|موجود|مطلوب|مؤكد|مدمج|مدعوم)|"
    r"(?:ليس|ليست)\s+(?:متوفرا|متوفرة|متوفر|موجودا|موجودة|موجود)|"
    r"لا\s+(?:يتوفر|تتوفر|يتضمن|تتضمن|يوجد))",
    re.IGNORECASE,
)


def _lumbar_term_is_negated(
    normalized: str,
    *,
    start: int,
    end: int,
) -> bool:
    boundaries_before = list(_LUMBAR_CLAUSE_BOUNDARY_RE.finditer(normalized, 0, start))
    clause_start = boundaries_before[-1].end() if boundaries_before else 0
    boundary_after = _LUMBAR_CLAUSE_BOUNDARY_RE.search(normalized, end)
    clause_end = boundary_after.start() if boundary_after else len(normalized)
    prefix = normalized[clause_start:start]
    suffix = normalized[end:clause_end]
    return (
        _LUMBAR_PRE_NEGATION_RE.search(prefix) is not None
        or _LUMBAR_POST_NEGATION_RE.search(suffix) is not None
    )


def _has_unnegated_lumbar_term(text: str) -> bool:
    normalized = re.sub(
        r"[\u064b-\u065f\u0670\u06d6-\u06ed\u0640]",
        "",
        _normalize_text(text),
    )
    for term in _LUMBAR_SUPPORT_TERMS:
        start = 0
        while (index := normalized.find(term, start)) >= 0:
            end = index + len(term)
            if not _lumbar_term_is_negated(
                normalized,
                start=index,
                end=end,
            ):
                return True
            start = end
    return False


def _has_positive_lumbar_support(text: str) -> bool:
    return _has_unnegated_lumbar_term(text)


def _requests_confirmed_lumbar_support(text: str) -> bool:
    return _has_unnegated_lumbar_term(text)


_ACOUSTIC_MEASUREMENT_RE = re.compile(
    r"\b(?:NRC|STC)\s*:?\s*\d+(?:\.\d+)?\b"
    r"|\b(?:acoustic|sound|noise)\s+"
    r"(?:attenuation|reduction|isolation|separation|blocking|dampening)"
    r"(?:\s+(?:rating|performance))?\s*(?::|of)?\s*"
    r"(?:up\s+to\s+)?\d+(?:\.\d+)?\s*dB\b"
    r"|\b(?:rated\s+at\s+)?\d+(?:\.\d+)?\s*dB\s+"
    r"(?:acoustic|sound|noise)\s+"
    r"(?:attenuation|reduction|isolation|separation|blocking|dampening)\b",
    re.IGNORECASE,
)
_ACOUSTIC_PERFORMANCE_FACT_RE = re.compile(
    r"\b(?:absorbs?|dampens?|attenuates?|reduces?|blocks?)\s+"
    r"(?:the\s+)?(?:sound|noise)\b"
    r"|\b(?:sound|noise)[-\s]+"
    r"(?:absorbing|dampening|attenuating|reducing|blocking)\b",
    re.IGNORECASE,
)
_ACOUSTIC_QUERY_RE = re.compile(
    r"\bacoustic\b|\bnoise\b"
    r"|\bsound\s+(?:attenuation|reduction|isolation|separation|control|"
    r"proofing|privacy|absorbing|dampening)\b"
    r"|\b(?:absorbs?|dampens?|attenuates?|reduces?|blocks?)\s+"
    r"(?:the\s+)?sound\b"
    r"|(?:العزل\s+الصوتي|الأداء\s+الصوتي|اداء\s+صوتي|صوت|ضوضاء|ضجيج)",
    re.IGNORECASE,
)
_FOOTPRINT_QUERY_RE = re.compile(
    r"\b(?:footprint|dimensions?|space[-\s]?saving)\b"
    r"|\bfloor\s+(?:space|area)\b"
    r"|\b(?:occup(?:y|ies|ied)|requires?|uses?|takes?)\s+"
    r"(?:up\s+)?(?:(?:less|more)\s+)?(?:floor\s+)?(?:space|area)\b"
    r"|\b(?:physical|overall|product)\s+size\b"
    r"|(?:المساحة|مساحة|الأبعاد|ابعاد|الحجم)",
    re.IGNORECASE,
)
_COMPACT_PRODUCT_QUERY_RE = re.compile(
    r"\bcompact\s+(?:product|model|option|chair|desk|table|workstation|pod|booth)\b"
    r"|\b(?:product|model|option|chair|desk|table|workstation|pod|booth)s?\b"
    r"(?:\W+\w+){0,4}\W+(?:more\s+)?compact\b",
    re.IGNORECASE,
)
_COMPACT_NON_PRODUCT_RE = re.compile(
    r"\bcompact\s+(?:team|company|business|staff|workforce|office)\b",
    re.IGNORECASE,
)
_CATALOG_PRODUCT_SUBJECT = (
    r"(?:product|model|option|chair|desk|table|workstation|pod|booth)s?"
)
_ACOUSTIC_PRODUCT_QUERY_RE = re.compile(
    rf"\b{_CATALOG_PRODUCT_SUBJECT}\b(?:\W+\w+){{0,5}}\W+"
    r"(?:quiet(?:er|est)?|(?:less|least)\s+echo|chatter)\b"
    rf"|\b(?:quiet(?:er|est)?|(?:less|least)\s+echo|chatter)\b"
    rf"(?:\W+\w+){{0,5}}\W+{_CATALOG_PRODUCT_SUBJECT}\b",
    re.IGNORECASE,
)
_FOOTPRINT_PRODUCT_QUERY_RE = re.compile(
    rf"\b{_CATALOG_PRODUCT_SUBJECT}\b(?:\W+\w+){{0,6}}\W+"
    r"(?:(?:smallest|least)\s+(?:space|room)|"
    r"(?:fits?|needs?|requires?)\s+(?:the\s+)?(?:smallest|least)\s+"
    r"(?:space|room))\b",
    re.IGNORECASE,
)
_CATALOG_FACT_COMPARISON_CONTEXT_RE = re.compile(
    r"\b(?:compare|comparison|option|which|recommend|product|model|sku)\b"
    r"|(?:قارن|مقارنة|الخيار|الخيارات|أي\s+خيار|منتج|طراز)",
    re.IGNORECASE,
)
_DIMENSION_UNIT = r"(?:mm|cm|m|in(?:ches?)?|ft|feet)"
_DIMENSION_PAIR_RE = re.compile(
    rf"\b\d+(?:\.\d+)?\s*(?:{_DIMENSION_UNIT})?\s*(?:x|×|by)\s*"
    rf"\d+(?:\.\d+)?\s*(?:{_DIMENSION_UNIT})?"
    rf"(?:\s*(?:x|×|by)\s*\d+(?:\.\d+)?\s*(?:{_DIMENSION_UNIT})?)?",
    re.IGNORECASE,
)
_DIMENSION_AXIS_RE = re.compile(
    r"(?P<axis>width|depth|length|height|العرض|العمق|الطول|الارتفاع)\s*:?\s*"
    r"\d+(?:\.\d+)?\s*(?:mm|cm|m|in(?:ches?)?|ft|feet|مم|سم|متر)\b",
    re.IGNORECASE,
)
_FOOTPRINT_AREA_RE = re.compile(
    r"\b(?:footprint|floor\s+area)\s*:?\s*\d+(?:\.\d+)?\s*"
    r"(?:m2|m²|sqm|sq\.?\s*ft)\b"
    r"|(?:المساحة)\s*:?\s*\d+(?:\.\d+)?\s*(?:م2|م²|متر\s+مربع)",
    re.IGNORECASE,
)
_NON_FOOTPRINT_COMPONENT_RE = re.compile(
    r"(?:cable\s+tray|mounting\s+plate|screen|panel|seat|armrest|cutout|opening)"
    r"(?:\s+\w+){0,2}\s*:?\s*$",
    re.IGNORECASE,
)
_FOOTPRINT_PAIR_CONTEXT_RE = re.compile(
    r"(?:^|[.;؛\n])\s*(?:(?:overall|product|footprint)\s+)?"
    r"dimensions?\s*"
    r"(?:(?:\(\s*)?(?:W\s*(?:x|×)\s*D|L\s*(?:x|×)\s*W)"
    r"(?:\s*(?:x|×)\s*H)?(?:\s*\))?\s*)?"
    r"(?::\s*|(?:are|is)\s*)$"
    r"|(?:^|[.;؛\n])\s*الأبعاد\s*(?::\s*|هي\s*)$",
    re.IGNORECASE,
)
_FOOTPRINT_AXIS_CONTEXT_RE = re.compile(
    r"(?:^|[.;؛\n])\s*(?:(?:overall|product|footprint)\s+)?dimensions?\s*:\s*"
    r"|(?:^|[.;؛\n])\s*الأبعاد\s*:\s*",
    re.IGNORECASE,
)


def _catalog_fact_match_is_negated(
    text: str,
    *,
    start: int,
    end: int,
) -> bool:
    before = text[max(0, start - 80) : start]
    before_clause = re.split(r"[.;؛\n]", before)[-1]
    after = text[end : end + 50]
    negative_prefix = re.search(
        r"\b(?:no|not|never|cannot|can['’]?t|doesn['’]?t|do\s+not|"
        r"unable(?:\s+to)?|fails?(?:\s+to)?|without|unrated|unknown|"
        r"unspecified|unconfirmed|"
        r"unavailable|absent|pending|tbd|awaiting)\b"
        r"(?:\W+\w+){0,5}\W*$"
        r"|(?:غير\s+(?:مؤكد|مذكور|محدد|متاح)|لا\s+يوجد|لا\s+توجد|بدون)"
        r"(?:\W+\w+){0,5}\W*$",
        before_clause,
        flags=re.IGNORECASE,
    )
    negative_suffix = re.match(
        r"^\W*(?:(?:is|are|remains?)\W+)?"
        r"(?:not|unrated|unknown|unspecified|unconfirmed|unavailable|"
        r"absent|pending|tbd|n\s*/\s*a)\b"
        r"|^\W*(?:awaiting\s+confirmation|to\s+be\s+"
        r"(?:confirmed|provided|tested))\b"
        r"|^\W*(?:غير\s+(?:مؤكد|مذكور|محدد|متاح))",
        after,
        flags=re.IGNORECASE,
    )
    return negative_prefix is not None or negative_suffix is not None


def _has_acoustic_performance_evidence(product_text: str) -> bool:
    for clause in re.split(r"[.;؛\n]+", product_text):
        matches = (
            *_ACOUSTIC_MEASUREMENT_RE.finditer(clause),
            *_ACOUSTIC_PERFORMANCE_FACT_RE.finditer(clause),
        )
        for match in matches:
            if not _catalog_fact_match_is_negated(
                clause,
                start=match.start(),
                end=match.end(),
            ):
                return True
    return False


def _requested_catalog_fact_domains(
    customer_text: str,
) -> tuple[CatalogFactDomain, ...]:
    normalized = _normalize_text(customer_text)
    domains: list[CatalogFactDomain] = []
    if _ACOUSTIC_QUERY_RE.search(normalized) or _ACOUSTIC_PRODUCT_QUERY_RE.search(
        normalized
    ):
        domains.append("acoustic")
    compact_product_request = bool(
        _COMPACT_PRODUCT_QUERY_RE.search(normalized)
        and not _COMPACT_NON_PRODUCT_RE.search(normalized)
    )
    if (
        _FOOTPRINT_QUERY_RE.search(normalized)
        or compact_product_request
        or _FOOTPRINT_PRODUCT_QUERY_RE.search(normalized)
    ):
        domains.append("footprint")
    return tuple(domains)


def _is_catalog_fact_comparison_query(customer_text: str) -> bool:
    return bool(
        _requested_catalog_fact_domains(customer_text)
        and (
            _catalog_product_families(customer_text)
            or _CATALOG_FACT_COMPARISON_CONTEXT_RE.search(customer_text)
        )
    )


def _should_override_policy_for_catalog_fact_query(
    customer_text: str,
    decision: VerifiedAnswerDecision,
) -> bool:
    return bool(
        _is_catalog_fact_comparison_query(customer_text)
        and not decision.is_order_status
        and decision.question_class != "service_high_risk"
        and not decision.matched_topics
        and not decision.asks_for_specific_commitment
    )


def _has_footprint_dimension_evidence(product_text: str) -> bool:
    for match in _DIMENSION_PAIR_RE.finditer(product_text):
        prefix = product_text[max(0, match.start() - 60) : match.start()]
        has_unit = re.search(_DIMENSION_UNIT, match.group(), re.IGNORECASE) is not None
        if (
            has_unit
            and _FOOTPRINT_PAIR_CONTEXT_RE.search(prefix)
            and not _NON_FOOTPRINT_COMPONENT_RE.search(prefix)
            and not _catalog_fact_match_is_negated(
                product_text,
                start=match.start(),
                end=match.end(),
            )
        ):
            return True

    area_match = _FOOTPRINT_AREA_RE.search(product_text)
    if area_match is not None and not _catalog_fact_match_is_negated(
        product_text,
        start=area_match.start(),
        end=area_match.end(),
    ):
        return True

    axis_groups = {
        "width": "width",
        "العرض": "width",
        "depth": "depth",
        "العمق": "depth",
        "length": "length",
        "الطول": "length",
        "height": "",
        "الارتفاع": "",
    }
    for context_match in _FOOTPRINT_AXIS_CONTEXT_RE.finditer(product_text):
        fragment_end_match = re.search(
            r"[.\n]",
            product_text[context_match.end() :],
        )
        fragment_end = (
            context_match.end() + fragment_end_match.start()
            if fragment_end_match is not None
            else len(product_text)
        )
        fragment = product_text[context_match.end() : fragment_end]
        planar_axes: set[str] = set()
        for segment in re.split(r"[,;؛]", fragment):
            normalized_segment = segment.strip()
            axis_match = _DIMENSION_AXIS_RE.match(normalized_segment)
            if axis_match is None:
                break
            if _catalog_fact_match_is_negated(
                normalized_segment,
                start=axis_match.start(),
                end=axis_match.end(),
            ):
                continue
            planar_axis = axis_groups[axis_match.group("axis").casefold()]
            if planar_axis:
                planar_axes.add(planar_axis)
        if len(planar_axes) >= 2:
            return True
    return False


def _requested_catalog_evidence_gaps(
    customer_text: str,
    product_text: str,
    *,
    required_facts: tuple[CatalogFactDomain, ...] | None = None,
) -> tuple[str, ...]:
    normalized_customer = _normalize_text(customer_text)
    requested_facts = (
        _requested_catalog_fact_domains(normalized_customer)
        if required_facts is None
        else required_facts
    )
    gaps: list[str] = []
    if "acoustic" in requested_facts and not _has_acoustic_performance_evidence(
        product_text
    ):
        gaps.append(_ACOUSTIC_FACT_GAP)
    if "footprint" in requested_facts and not _has_footprint_dimension_evidence(
        product_text
    ):
        gaps.append(_FOOTPRINT_FACT_GAP)
    if _requests_confirmed_lumbar_support(
        normalized_customer
    ) and not _has_positive_lumbar_support(product_text):
        gaps.append("lumbar_support=not_stated")
    return tuple(gaps)


def _product_search_response_contract(
    *,
    match_kind: Literal["exact", "nearby", "missing", "empty"] = "exact",
    search_budget_exhausted: bool = False,
    target_coverage_complete: bool | None = None,
    lower_verified_family_total: tuple[CatalogFamily, float, float] | None = None,
) -> str:
    if match_kind == "nearby":
        contract_parts = [
            "Catalog results were found, but they are the closest alternatives rather than a confirmed exact match.",
            "Lead with up to 3 closest alternatives from these results before any generic qualifying questions, but respect an explicit smaller maximum in the customer's request.",
            "Say honestly that the exact requested item is not confirmed from the catalog results.",
            "Do not claim that these are the exact item requested.",
            "Use only facts already present in tool results; do not invent specs or allocate more units than returned catalog stock.",
            "Treejar Catalog price is the customer-facing commercial truth by default.",
            "Zoho rate is operational execution data and must not be used as a customer-facing replacement price or mismatch signal.",
            "After the alternatives, ask at most one narrow follow-up; do not offer sourcing or escalation for an ordinary no-match.",
            "Tie one verified fact to the stated need and end with one concrete next action.",
        ]
    elif match_kind == "empty":
        # tj-b93r. A search that returns nothing used to hand the model the
        # bare string "No products found matching the query." and no contract
        # at all, so the one turn with no grounding whatsoever was also the one
        # turn with no instructions. That is the shape the blinded sales review
        # caught inventing pod sizes after an empty search.
        contract_parts = [
            "The catalog search returned no products for this request.",
            "Say that plainly and do not present anything as a catalog option.",
            "Invent nothing: no specs, sizes, prices, lead times or quantities. "
            "Nothing was returned that could ground them.",
            "Ask one narrow clarification that could make a second search "
            "succeed, or name a related family you can then verify by searching.",
            "Do not offer sourcing or escalation for an ordinary no-match.",
            "End with one concrete next action.",
        ]
    elif match_kind == "missing":
        contract_parts = [
            "Current catalog results are too weak to establish a reliable match for this request.",
            "Do not present these results as exact options.",
            "Give related alternatives or ask one narrow clarification; do not offer sourcing or escalation for an ordinary no-match.",
            "Use only facts already present in tool results; do not invent specs, prices, or quantities above returned catalog stock.",
            "Treejar Catalog price is the customer-facing commercial truth by default for any catalog option you do show.",
            "Zoho rate is operational execution data and must not be used as a customer-facing replacement price or mismatch signal.",
            "If showing an alternative, tie one verified fact to the stated need and give one concrete next action.",
        ]
    else:
        contract_parts = [
            "Relevant catalog results were found for this customer message.",
            "In your next reply, lead with up to 3 concrete options or closest alternatives from these results before any generic qualifying questions, but respect an explicit smaller maximum in the customer's request.",
            "Use only facts already present in tool results; do not invent specs or allocate more units than returned catalog stock.",
            "Treejar Catalog price is the customer-facing commercial truth by default.",
            "Zoho rate is operational execution data and must not be used as a customer-facing replacement price or mismatch signal.",
            "If the returned items are only nearby alternatives, say that honestly and position them as the closest fit.",
            "After presenting the options, you may ask at most one targeted follow-up to narrow the recommendation.",
            "Do not start with generic discovery like budget, use case, or timeline if the current results are already relevant enough to show options.",
            "Tie one verified fact to the stated need and end with one concrete next action.",
        ]

    if target_coverage_complete is not None:
        contract_parts.append(
            "Do not call a configuration viable unless it covers the full target; "
            "state any verified coverage gap explicitly."
        )

    if lower_verified_family_total is not None:
        family, prior_total, current_total = lower_verified_family_total
        contract_parts.append(
            f"An earlier verified {family} total of {prior_total:.2f} AED is lower "
            f"than this search's complete total of {current_total:.2f} AED; do not "
            "call the current option cheapest or minimum."
        )

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
        "Use this stock/price fact to strengthen the concrete options you already have. "
        "Zoho confirms operational stock; Treejar Catalog price remains the customer-facing commercial truth when present. "
        "Do not replace or invalidate catalog price with Zoho rate in the customer reply. "
        "Keep the answer option-first, mention the relevant availability and customer-facing catalog price facts, "
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
    behavior_rules: list[dict[str, Any]] | None = None
    recent_history: list[str] | None = None  # Last N messages for escalation context
    defer_product_media: bool = False
    pending_product_media: list[ProductMediaPayload] = field(default_factory=list)
    product_search_calls: int = 0
    product_results_seen: bool = False
    tool_mode: Literal[
        "full",
        "order_handoff",
        "service_policy",
        "exact_quote",
        "selection_confirmation",
        "catalog_materialization",
    ] = "full"
    runtime_directives: tuple[str, ...] = ()
    permitted_asks: frozenset[AskKind] | None = None
    customer_facts_context: str | None = None
    source_message_id: str | None = None
    catalog_planning: CatalogPlanningContext = field(
        default_factory=CatalogPlanningContext
    )
    inventory_confirmed: bool = False
    quotation_created: bool = False
    catalog_mismatch_alerted: bool = False
    required_cross_sell_disclosure: str | None = None
    unsupported_catalog_facts: set[str] = field(default_factory=set)
    catalog_fact_products: dict[str, VerifiedCatalogFactProduct] = field(
        default_factory=dict
    )
    # Every catalog row that reached the model this turn, recorded whether or
    # not the customer asked about an attribute. The old guard only recorded
    # rows on request, which is exactly why a volunteered claim had nothing to
    # be checked against.
    claim_rows: dict[str, RetrievedRow] = field(default_factory=dict)
    verified_catalog_selections: dict[
        CatalogFamily, tuple[VerifiedCatalogLine, ...]
    ] = field(default_factory=dict)
    current_catalog_selections: dict[CatalogFamily, tuple[VerifiedCatalogLine, ...]] = (
        field(default_factory=dict)
    )
    verified_cross_sell: VerifiedCrossSell | None = None
    stock_snapshots: dict[str, StockSnapshot] = field(default_factory=dict)
    catalog_decision: CatalogDecision | None = None
    executed_tool_names: list[str] = field(default_factory=list)
    recovery_tool_traces: list[RuntimeToolTrace] = field(default_factory=list)


_PRICE_FIGURE_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _turn_saw_catalog_evidence(deps: SalesDeps) -> bool:
    return bool(
        deps.product_results_seen
        or deps.claim_rows
        or deps.catalog_fact_products
        or deps.verified_catalog_selections
        or deps.current_catalog_selections
        or deps.pending_product_media
        or deps.stock_snapshots
    )


def grounded_amounts_for_turn(
    deps: SalesDeps,
    *,
    customer_text: str = "",
) -> tuple[object, ...] | None:
    """The sums this turn may say out loud, or `None` to leave the check off.

    Deliberately narrow. `tj-vz7o.10.1` measured one failure and this closes
    exactly that one: a bare "Good Afternoon" retrieved nothing, and the reply
    still named a confident starting price and attributed it to our catalog.
    When the turn touched no catalog at all, every sum in the reply is invented
    by construction, and the only honest exception is a figure the customer
    wrote first -- their own budget read back is theirs, not ours.

    The moment a row *is* retrieved this returns `None` and the check stands
    down, because a price-per-row claim is the claim contract's job and it has
    the field paths to do it. A blunter rule here would strip real quotations,
    which is a worse defect than the one being fixed.
    """

    if _turn_saw_catalog_evidence(deps):
        return None
    return tuple(_PRICE_FIGURE_RE.findall(str(customer_text or "")))


_CLAIM_CONTRACT_CONTRACT = (
    'Return JSON only: {"claims":[{"claim_type":"catalog_fact|derived_fact|'
    'absence|explicit_assumption|recommendation","sku":"","field_path":"",'
    '"value":"","source_value":"","operation":"","inputs":[{"sku":"",'
    '"field_path":"","value":"","customer_stated":false}],'
    '"marker_present":false,"confirming_question":false}],"answer":""}. '
    "List one claim object for every product attribute the answer asserts, "
    "naming the exact field path it relies on. value is the value alone, not "
    "the sentence around it. Use absence when the answer reports an attribute "
    "the catalog is silent about. Use derived_fact for a comparison, total or "
    "calculation: set operation to comparison, sum, difference or product, and "
    "list every figure it rests on in inputs. Every input must do one of two "
    "things: name a sku and field_path from the retrieved rows, or set "
    "customer_stated true because the customer gave you that figure — a "
    "quantity they asked for is theirs, not the catalog's. A figure you "
    "assumed is neither, and belongs in an explicit_assumption instead. "
    "When value is not in English, put the English catalog "
    "value it translates in source_value. Technical provenance stays in "
    "the claims and never appears in answer. answer is the customer-facing "
    "reply and nothing else."
)


def _claim_contract_directive(
    repair_payload: str,
    withheld_field_paths: tuple[str, ...] = (),
) -> str:
    """The per-turn directive for the structured repair pass.

    The product system prompt is frozen, so the contract lives here, on the
    turn, where it can also name the exact paths a previous attempt failed on.
    """
    directive = (
        "Revise candidate_response against verified_catalog_facts. "
        "Preserve supported recommendation reasoning and remove unsupported "
        f"claims. {_CLAIM_CONTRACT_CONTRACT} {repair_payload}"
    )
    assumption_paths, plain_paths = assumption_eligible_paths(withheld_field_paths)
    if plain_paths:
        directive += (
            # Since 2026-08-06 a path only reaches this branch when the row
            # positively contradicts it, so the instruction is to use the value
            # the catalog holds rather than to fall back on not knowing.
            " The retrieved rows state a different value for these field "
            f"paths: {', '.join(plain_paths)}. Use the value the row states, or "
            "drop the claim. Do not tell the customer the catalog is silent "
            "about them, because it is not, and keep every other detail."
        )
    if assumption_paths:
        # Withholding these as flatly as the paths above is what produced the
        # false refusals `tj-feet.5` measured. The contract approves them when
        # they carry a marker and a confirming question, so the retry is told
        # to re-offer them that way rather than to drop the answer.
        directive += (
            " These field paths are not catalog facts and must not be stated "
            f"as facts: {', '.join(assumption_paths)}. Do not drop the answer. "
            "Re-offer each as an explicit assumption: mark it as an "
            "assumption, state the per-unit figure you are assuming, and ask "
            "one short question that confirms it."
        )
    # tj-7z1x. The sizing directive demands the arithmetic in the open and one
    # concrete next step; this one demanded neither, and reading the four turns
    # the contract still rewrites showed the worst of them losing exactly that
    # closing offer, 349 characters down to 271. Stated here so a repaired
    # reply is held to the same bar as an unrepaired one.
    directive += (
        " Keep the arithmetic visible where the answer rests on it, and close "
        "with one concrete next step."
    )
    return directive


def _log_claim_contract(
    contract: ContractResult | None,
    conversation_id: Any,
    *,
    scope: str,
) -> None:
    """Record what the contract refuted and what it merely could not confirm.

    Since the owner decision of 2026-08-06 the contract blocks only a claim the
    row positively contradicts, so the unverified bucket is where the evidence
    now lives: it is how we find out, on live traffic, whether the strict rule
    was protecting anything. It is logged at info, because it changes no reply.
    """
    if contract is None:
        return
    if contract.withheld:
        logger.warning(
            "Claim contract refuted %s on a %s catalog turn for conversation %s",
            list(contract.withheld_field_paths),
            scope,
            conversation_id,
        )
    if contract.unverified:
        logger.info(
            "Claim contract could not confirm %s on a %s catalog turn for "
            "conversation %s; the reply was left intact",
            list(contract.unverified_field_paths),
            scope,
            conversation_id,
        )


class _ContractedResult:
    """A model result whose text is the contract-approved answer.

    Usage and telemetry are delegated, so cost accounting stays attached to the
    call that actually happened.
    """

    def __init__(self, source: Any, output: str) -> None:
        self._source = source
        self.output = output

    def usage(self) -> Any:
        return self._source.usage()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._source, name)


def _parse_claim_payload(
    output: str,
) -> tuple[tuple[AttributeClaim, ...], str] | None:
    """Read the structured repair payload, or give up cleanly.

    A model that ignores the contract must not break the turn, so an
    unparseable payload falls back to the previous plain-text behaviour.
    """
    try:
        parsed = json.loads(str(output).strip())
    except (TypeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    answer = parsed.get("answer")
    raw_claims = parsed.get("claims")
    if not isinstance(answer, str) or not answer.strip():
        return None
    if raw_claims is None:
        raw_claims = []
    if not isinstance(raw_claims, list):
        return None
    claims: list[AttributeClaim] = []
    for raw in raw_claims:
        if not isinstance(raw, Mapping):
            continue
        claim_type = str(raw.get("claim_type") or "catalog_fact")
        if claim_type not in {
            "catalog_fact",
            "derived_fact",
            "absence",
            "explicit_assumption",
            "recommendation",
        }:
            claim_type = "catalog_fact"
        claims.append(
            AttributeClaim(
                claim_type=claim_type,  # type: ignore[arg-type]
                sku=str(raw.get("sku") or ""),
                field_path=str(raw.get("field_path") or ""),
                value=str(raw.get("value") or ""),
                marker_present=bool(raw.get("marker_present")),
                confirming_question=bool(raw.get("confirming_question")),
                source_value=str(raw.get("source_value") or ""),
                operation=str(raw.get("operation") or ""),
                inputs=_parse_claim_inputs(raw.get("inputs")),
            )
        )
    return tuple(claims), answer.strip()


def _parse_claim_inputs(raw_inputs: Any) -> tuple[ClaimInput, ...]:
    """The figures a derivation names, or nothing.

    A malformed input list must not break the turn any more than a malformed
    payload does; it leaves the derivation with nothing to verify against, which
    the contract already withholds.
    """
    if not isinstance(raw_inputs, list):
        return ()
    parsed: list[ClaimInput] = []
    for raw in raw_inputs:
        if not isinstance(raw, Mapping):
            continue
        parsed.append(
            ClaimInput(
                sku=str(raw.get("sku") or ""),
                field_path=str(raw.get("field_path") or ""),
                value=str(raw.get("value") or ""),
                customer_stated=bool(raw.get("customer_stated")),
            )
        )
    return tuple(parsed)


async def _enforce_claim_contract(
    repaired_result: Any,
    *,
    repair_deps: SalesDeps,
    repair_payload: str,
    run_agent: Any,
) -> tuple[Any, ContractResult | None]:
    """Verify the emitted claims and keep unsupported ones off the wire.

    One bounded retry: the second attempt is told exactly which field paths the
    rows do not carry, so the answer becomes a useful partial one rather than a
    refusal or a quiet repetition of the same claim.
    """
    parsed = _parse_claim_payload(getattr(repaired_result, "output", ""))
    if parsed is None:
        return repaired_result, None
    claims, answer = parsed
    contract = apply_contract(claims, repair_deps.claim_rows)
    if not contract.withheld:
        return _ContractedResult(repaired_result, answer), contract

    retry_deps = replace(
        repair_deps,
        runtime_directives=(
            *repair_deps.runtime_directives[:-1],
            _claim_contract_directive(
                repair_payload, withheld_field_paths=contract.withheld_field_paths
            ),
        ),
    )
    retried = await run_agent(retry_deps)
    retried_parsed = _parse_claim_payload(getattr(retried, "output", ""))
    if retried_parsed is None:
        return retried, contract
    retried_claims, retried_answer = retried_parsed
    retried_contract = apply_contract(retried_claims, repair_deps.claim_rows)
    return _ContractedResult(retried, retried_answer), retried_contract


CLAIM_CONTRACT_SCOPE_KEY = "claim_contract_scope"
_CLAIM_CONTRACT_SCOPE_EVERY_TURN = "every_catalog_turn"
_CLAIM_CONTRACT_ROW_LIMIT = 5
_CLAIM_CONTRACT_VALUE_MAX_CHARS = 256


def _claim_contract_runs_every_catalog_turn(configured: str) -> bool:
    """One config value decides the scope, and it defaults to today's behaviour.

    `tj-feet.10` costs an extra model call on every catalog turn, which is a
    latency decision the owner holds. So the widened scope ships switched off,
    reversible by a single `system_configs` row exactly like the model slot,
    and any value that is not the widened one leaves the old trigger in place.
    """
    return str(configured).strip().casefold() == _CLAIM_CONTRACT_SCOPE_EVERY_TURN


def _materialize_claim_rows(deps: SalesDeps) -> dict[str, dict[str, str]] | None:
    """The rows this turn retrieved, as the contract will check them.

    Structural, not lexical: the trigger is *a catalog row reached the model*,
    never a pattern over the reply text, which the specification rejects.
    """
    if not deps.claim_rows:
        return None
    rows: dict[str, dict[str, str]] = {}
    for sku, row in sorted(deps.claim_rows.items())[:_CLAIM_CONTRACT_ROW_LIMIT]:
        rows[sku] = {
            path: value[:_CLAIM_CONTRACT_VALUE_MAX_CHARS]
            for path, value in sorted(row.fields.items())
        }
    return rows or None


async def _verify_volunteered_claims(
    result: Any,
    *,
    run_deps: SalesDeps,
    run_agent: Any,
) -> tuple[Any, ContractResult | None]:
    """Check a catalog turn nobody asked a question about.

    The `tj-feet.3` repair pass fires only on one of two hardcoded requested
    gap types. On a turn where the customer asked nothing, the model's text was
    final and a volunteered attribute had nothing to be checked against.

    A clean turn keeps its original reply untouched: the check is paid, the
    rewrite is not. Only a turn that actually volunteered something unsupported
    is regenerated, and an answer that cannot be parsed leaves the turn exactly
    as it was.
    """
    rows = _materialize_claim_rows(run_deps)
    if rows is None:
        return result, None
    verify_payload = json.dumps(
        {"candidate_response": str(result.output), "retrieved_rows": rows},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    verify_deps = replace(
        run_deps,
        tool_mode="catalog_materialization",
        runtime_directives=(
            *run_deps.runtime_directives,
            _claim_contract_directive(verify_payload),
        ),
    )
    verified = await run_agent(verify_deps)
    parsed = _parse_claim_payload(getattr(verified, "output", ""))
    if parsed is None:
        return result, None
    claims, _answer = parsed
    contract = apply_contract(claims, run_deps.claim_rows)
    if not contract.withheld:
        return result, contract
    return await _enforce_claim_contract(
        verified,
        repair_deps=verify_deps,
        repair_payload=verify_payload,
        run_agent=run_agent,
    )


def _materialize_verified_catalog_facts(deps: SalesDeps) -> str | None:
    guarded_facts = deps.unsupported_catalog_facts.intersection(
        {
            _ACOUSTIC_FACT_GAP,
            _FOOTPRINT_FACT_GAP,
        }
    )
    products = tuple(
        sorted(
            deps.catalog_fact_products.values(),
            key=lambda product: (
                not bool(set(product.fact_gaps).intersection(guarded_facts)),
                -product.search_call,
                product.result_rank,
            ),
        )[:5]
    )
    if not guarded_facts or not products:
        return None

    arabic = is_arabic_customer_language(str(deps.conversation.language))
    lines = [
        (
            "إليك مقارنة تعتمد فقط على بيانات الكتالوج المؤكدة:"
            if arabic
            else "Here is a comparison using only verified catalog data:"
        )
    ]
    for product in products:
        lines.append(f"\n- {product.name} (SKU: {product.sku})")
        if product.price is not None:
            price = f"{product.price:.2f} {product.currency}"
        else:
            price = "يتطلب التحقق" if arabic else "requires verification"
        lines.append(f"  - {'السعر' if arabic else 'Price'}: {price}")
        snapshot = deps.stock_snapshots.get(product.sku.strip().casefold())
        if snapshot is not None and snapshot.provenance == "authoritative":
            stock = str(snapshot.available)
        else:
            stock = "غير مؤكد" if arabic else "unconfirmed"
        lines.append(f"  - {'المخزون' if arabic else 'Stock'}: {stock}")
        if product.capacity is not None and product.capacity > 1:
            basis = (
                f"وحدة كاملة لـ {product.capacity} مقاعد"
                if arabic
                else f"full {product.capacity}-seat SKU unit"
            )
            lines.append(f"  - {'أساس السعر' if arabic else 'Price basis'}: {basis}")
        description = " ".join(product.description.split())[:500]
        if description:
            lines.append(
                f"  - {'وصف الكتالوج' if arabic else 'Catalog description'}: "
                f"{description}"
            )
        product_gaps = set(product.fact_gaps)
        if _ACOUSTIC_FACT_GAP in product_gaps:
            lines.append(
                "  - الأداء الصوتي: غير مذكور في الكتالوج"
                if arabic
                else "  - Acoustic performance: not stated in the catalog"
            )
        if _FOOTPRINT_FACT_GAP in product_gaps:
            lines.append(
                "  - أبعاد المساحة: غير مذكورة في الكتالوج"
                if arabic
                else "  - Footprint dimensions: not stated in the catalog"
            )

    missing_acoustic = _ACOUSTIC_FACT_GAP in guarded_facts
    missing_footprint = _FOOTPRINT_FACT_GAP in guarded_facts
    if arabic:
        if missing_acoustic and missing_footprint:
            unavailable_facts = "بيانات صوتية أو أبعاد غير مؤكدة"
        elif missing_acoustic:
            unavailable_facts = "بيانات صوتية غير مؤكدة"
        else:
            unavailable_facts = "أبعاد غير مؤكدة"
        footer = (
            f"\nلن أرتب هذه الخيارات بناءً على {unavailable_facts}. "
            "ما عامل الكتالوج المؤكد الذي تريد اعتماده؟"
        )
    else:
        if missing_acoustic and missing_footprint:
            unavailable_facts = "unconfirmed acoustic or footprint claims"
        elif missing_acoustic:
            unavailable_facts = "unconfirmed acoustic claims"
        else:
            unavailable_facts = "unconfirmed footprint claims"
        footer = (
            f"\nI will not rank these options using {unavailable_facts}. "
            "Which confirmed catalog fact should drive the choice?"
        )
    lines.append(footer)
    return "\n".join(lines)


def _product_search_call_limit(deps: SalesDeps) -> int:
    turn_families = _catalog_product_families(getattr(deps, "user_query", ""))
    family_count = len(set(turn_families or deps.catalog_planning.families))
    return min(6, max(2, 2 * family_count))


def _verified_opening_catalog_lines(
    products: Sequence[Any],
    *,
    families: Sequence[CatalogFamily],
    language: str,
) -> tuple[VerifiedOpeningCatalogLine, ...]:
    """Pick one cheapest purchasable row per requested anchor family.

    Family membership is deliberately the `tj-3jo0` rule used by the price
    anchor: both the row name and its catalog taxonomy must agree. A generic
    office opening can therefore gain concrete options without letting a
    pedestal or workstation chair masquerade as a desk.
    """

    requested = set(families)
    cheapest: dict[str, VerifiedOpeningCatalogLine] = {}
    arabic = is_arabic_customer_language(language)
    for product in products:
        name_en = _string_value(getattr(product, "name_en", None))
        family = anchor_family_of_row(
            AnchorCatalogRow(
                name=name_en,
                category=_string_value(getattr(product, "category", None)) or None,
                subcategory=(
                    _string_value(getattr(product, "subcategory", None)) or None
                ),
                price=None,
                stock=None,
            )
        )
        if family is None or family.key not in requested:
            continue
        try:
            price = float(getattr(product, "price", 0) or 0)
            stock = int(getattr(product, "stock", 0) or 0)
        except (TypeError, ValueError, OverflowError):
            continue
        sku = _string_value(getattr(product, "sku", None))
        currency = _string_value(getattr(product, "currency", None)).upper()
        name_ar = _string_value(getattr(product, "name_ar", None))
        name = name_ar if arabic and name_ar else name_en
        if not name or not sku or price <= 0 or stock <= 0 or not currency:
            continue
        line = VerifiedOpeningCatalogLine(
            family=cast("CatalogFamily", family.key),
            name=name,
            sku=sku,
            unit_price=price,
            currency=currency,
            stock=stock,
        )
        previous = cheapest.get(family.key)
        if previous is None or (line.unit_price, line.name.casefold(), line.sku) < (
            previous.unit_price,
            previous.name.casefold(),
            previous.sku,
        ):
            cheapest[family.key] = line
    return tuple(cheapest[family] for family in families if family in cheapest)


def _materialize_verified_opening_catalog_options(
    lines: Sequence[VerifiedOpeningCatalogLine],
    *,
    requested_seats: int,
    language: str,
) -> str | None:
    if not lines:
        return None
    if is_arabic_customer_language(language):
        rendered = [
            f"هذه خيارات بداية مؤكدة من الكتالوج لمكتب يضم {requested_seats} أشخاص:"
        ]
        rendered.extend(
            f"- {line.name} (SKU {line.sku}) — {line.unit_price:.2f} {line.currency}."
            for line in lines
        )
        rendered.extend(
            (
                "هذه خيارات بداية وليست حجزاً للكمية كاملة. يعتمد موعد التسليم "
                "على المنتجات والكمية المختارة، لذلك سأؤكده مقابل المخزون الحالي "
                "قبل الالتزام.",
            )
        )
        return "\n".join(rendered)

    rendered = [
        f"Here are verified catalog starting options for the {requested_seats}-person office:"
    ]
    rendered.extend(
        f"- {line.name} (SKU {line.sku}) — {line.currency} {line.unit_price:.2f}."
        for line in lines
    )
    rendered.extend(
        (
            "These are starting options, not a reservation for the full quantity. "
            "Delivery timing depends on the chosen SKUs and quantity, so I will "
            "confirm it against current stock before committing.",
        )
    )
    return "\n".join(rendered)


async def _try_verified_opening_catalog_options(deps: SalesDeps) -> str | None:
    """Answer a scoped office opening from catalog state before free generation."""

    planning = deps.catalog_planning
    current_families = _catalog_product_families(deps.user_query)
    generic_office = _GENERIC_OFFICE_OPENING_RE.search(deps.user_query) is not None
    if (
        planning.requested_seats is None
        or not planning.families
        or not (current_families or generic_office)
        or is_active_human_handoff(deps.conversation.escalation_status)
    ):
        return None

    result = await deps.db.execute(
        select(Product)
        .options(
            load_only(
                Product.sku,
                Product.name_en,
                Product.name_ar,
                Product.category,
                Product.subcategory,
                Product.price,
                Product.currency,
                Product.stock,
            )
        )
        .where(
            Product.is_active.is_(True),
            Product.stock > 0,
            Product.price > 0,
        )
    )
    lines = _verified_opening_catalog_lines(
        tuple(result.scalars().all()),
        families=planning.families,
        language=str(deps.conversation.language),
    )
    response = _materialize_verified_opening_catalog_options(
        lines,
        requested_seats=planning.requested_seats,
        language=str(deps.conversation.language),
    )
    if response is None:
        return None

    captured_at = datetime.datetime.now(datetime.UTC)
    for line in lines:
        deps.claim_rows[line.sku] = RetrievedRow(
            sku=line.sku,
            fields={
                "name": line.name,
                "price": f"{line.unit_price:.2f}",
                "currency": line.currency,
            },
        )
        deps.stock_snapshots[line.sku.casefold()] = StockSnapshot(
            sku=line.sku,
            available=line.stock,
            source="catalog",
            as_of=captured_at,
            provenance="unconfirmed",
        )
    deps.product_results_seen = True
    return response


def _append_required_tool_disclosures(text: str, deps: SalesDeps) -> str:
    return append_required_tool_disclosure(
        text,
        _string_value(deps.required_cross_sell_disclosure) or None,
    )


def _track_sales_tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """Record every executed sales tool without changing its public signature."""

    @wraps(func)
    async def tracked(
        ctx: RunContext[SalesDeps],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        executed_tool_names = getattr(ctx.deps, "executed_tool_names", None)
        if isinstance(executed_tool_names, list):
            executed_tool_names.append(func.__name__)
        return await func(ctx, *args, **kwargs)

    return tracked


def _record_recovery_tool_result(
    deps: SalesDeps,
    *,
    tool_name: str,
    arguments: Mapping[str, object],
    result: str | ToolReturn,
) -> str | ToolReturn:
    outcome = (
        {
            "return_value": result.return_value,
            "content": result.content,
        }
        if isinstance(result, ToolReturn)
        else result
    )
    traces = getattr(deps, "recovery_tool_traces", None)
    if isinstance(traces, list):
        traces.append(
            build_runtime_tool_trace(
                tool_name=tool_name,
                arguments={
                    "sequence": len(traces) + 1,
                    **arguments,
                },
                outcome=outcome,
            )
        )
    return result


_VERIFIED_PROSE_NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


_VERIFIED_PROSE_LIST_MARKER_RE = re.compile(r"^[ \t]*\d+[.)][ \t]", re.MULTILINE)


def _verified_prose_numbers(text: str) -> set[Decimal]:
    # "1." at the start of a line is a list marker, not a quantity. The
    # selection-confirmation template numbers its items that way, so counting
    # markers as facts would have failed every multi-item rewrite and quietly
    # sent the template every time.
    text = _VERIFIED_PROSE_LIST_MARKER_RE.sub("", text)
    values: set[Decimal] = set()
    for match in _VERIFIED_PROSE_NUMBER_RE.finditer(text):
        try:
            values.add(Decimal(match.group(0).replace(",", "")))
        except InvalidOperation:  # pragma: no cover - regex admits only numerals
            continue
    return values


_VERIFIED_PROSE_PROTECTED_RE = re.compile(
    r"(?<![\w.])"
    r"(?:[A-Za-z]+[A-Za-z0-9]*\d[A-Za-z0-9]*(?:[-_/][A-Za-z0-9]+)*"
    r"|\d[\d,]*(?:\.\d+)?)"
    r"(?![\w.]*[A-Za-z0-9])"
)
_VERIFIED_PROSE_SLOT_RE = re.compile(r"\{\{f(\d+)\}\}")


def _verified_prose_mask(verified_text: str) -> tuple[str, tuple[str, ...]]:
    """Replace every protected figure with a numbered slot.

    The model is never asked to copy a number. It is given the route's own
    sentence with each figure already replaced by ``{{f1}}``, ``{{f2}}`` and so
    on, and it rewrites the words around those tokens; the values are put back
    by code afterwards.

    This is the standard answer to the problem and the reason for the rewrite
    of this module. Asking a model to reproduce figures and checking them
    afterwards -- which is what this did first -- fails in a way that is well
    documented: on the 2026-08-07 acceptance the model dropped a unit price,
    a stock figure or a quotation number on nearly every attempt, so the guard
    was correct every time and the customer got the template every time.
    Emitting placeholders and substituting them makes a wrong or missing figure
    a structural impossibility rather than something to detect. ASPIRO
    (Vejvar & Fujimoto, EMNLP Findings 2023) measures the same effect on
    entity-agnostic templates.
    """

    marker_spans = [
        match.span() for match in _VERIFIED_PROSE_LIST_MARKER_RE.finditer(verified_text)
    ]
    values: list[str] = []
    slot_of: dict[str, int] = {}

    def _swap(match: re.Match[str]) -> str:
        start, end = match.span()
        if any(start >= low and end <= high for low, high in marker_spans):
            # "1." opening a list line is formatting, not a figure.
            return match.group(0)
        written = match.group(0)
        # One slot per distinct figure: a total stated twice is one fact, and
        # asking for it twice would only be another way to fail.
        slot = slot_of.setdefault(written, len(values) + 1)
        if slot == len(values) + 1:
            values.append(written)
        return f"{{{{f{slot}}}}}"

    masked = _VERIFIED_PROSE_PROTECTED_RE.sub(_swap, verified_text)
    return masked, tuple(values)


_VERIFIED_PROSE_MIN_OVERLAP = 0.3
_VERIFIED_PROSE_WORD_RE = re.compile(r"[^\W\d_]{4,}", re.UNICODE)


def _verified_prose_content_words(text: str) -> set[str]:
    return {
        match.group(0).casefold() for match in _VERIFIED_PROSE_WORD_RE.finditer(text)
    }


def _verified_prose_render(
    candidate: str,
    values: tuple[str, ...],
    *,
    verified_text: str,
    customer_text: str,
    already_said: str,
) -> tuple[str | None, str | None]:
    """Substitute the verified figures back, or say why the rewrite failed.

    Three checks, in the order the sources that describe this pattern put them:
    every slot is present, no slot was invented, and no bare figure escaped the
    slots. Only the last needs a judgement call -- a figure the customer or an
    earlier turn already used is theirs to restate.
    """

    if not candidate.strip():
        return None, "empty"

    if not values:
        # No figure to anchor on, so the only question left is whether this is
        # a restatement at all. A reply on a different subject shares almost no
        # content words with the one it claims to be rewriting.
        anchor = _verified_prose_content_words(verified_text)
        if anchor:
            shared = anchor & _verified_prose_content_words(candidate)
            if len(shared) / len(anchor) < _VERIFIED_PROSE_MIN_OVERLAP:
                return None, f"shares only {len(shared)} of {len(anchor)} words"
        return candidate, None

    used = {int(m.group(1)) for m in _VERIFIED_PROSE_SLOT_RE.finditer(candidate)}
    expected = set(range(1, len(values) + 1))
    if missing := expected - used:
        return None, f"dropped slots {sorted(missing)}"
    if invented := used - expected:
        return None, f"invented slots {sorted(invented)}"

    stripped = _VERIFIED_PROSE_SLOT_RE.sub(" ", candidate)
    stripped = _VERIFIED_PROSE_LIST_MARKER_RE.sub("", stripped)
    said = _verified_prose_numbers(customer_text) | _verified_prose_numbers(
        already_said
    )
    if loose := _verified_prose_numbers(stripped) - said:
        return None, f"figures outside a slot {sorted(map(str, loose))}"

    rendered = _VERIFIED_PROSE_SLOT_RE.sub(
        lambda m: values[int(m.group(1)) - 1], candidate
    )
    return rendered, None


_VERIFIED_PROSE_EXAMPLE = (
    "Worked example. Given verified_reply: 'Confirmed: {{f1}} x LUMA {{f2}}, "
    "{{f3}} AED each.' a correct answer is: 'All {{f1}} of the LUMA {{f2}} are "
    "confirmed for you, Sara, at {{f3}} AED each -- shall I hold them?' Note "
    "that every token came through untouched and no digit was written."
)


def _verified_prose_directive(
    masked_text: str,
    slot_count: int,
    retry: bool,
    *,
    customer_name: str = "",
    customer_text: str = "",
) -> str:
    slots = ", ".join(f"{{{{f{index}}}}}" for index in range(1, slot_count + 1))
    rule = ""
    if slot_count:
        rule = (
            f" {slots} are not placeholders for you to fill in. They are "
            "verified figures already in their final form, and the system "
            "substitutes them after you answer. Copy each token through into "
            "your reply character for character, in the place its figure "
            "belongs, and use every one at least once. Do not write any digit "
            "yourself: no price, quantity, stock level or reference code. A "
            f"reply that spells a figure out instead of using its token is "
            f"discarded. {_VERIFIED_PROSE_EXAMPLE}"
        )
    insist = (
        " Your previous attempt spelled figures out instead of using the "
        "tokens and was discarded. Use the tokens this time."
        if retry
        else ""
    )
    # Enough of the turn to write to a person rather than into the air. The
    # agent has no history of its own, and without this it cannot use a name or
    # answer what was actually asked.
    context = ""
    if customer_name:
        context += f" The customer is {customer_name}."
    if customer_text:
        context += f' Their message was: "{customer_text.strip()[:400]}"'
    return (
        "verified_reply below is already correct and its facts are final. Send "
        "the same message in your own words, as Noor speaking to this customer: "
        "acknowledge what they asked for, say briefly why this fits their "
        "stated need, and close on the next step verified_reply names."
        f"{context}{rule}{insist} Keep the customer's language, do not greet "
        "them again, and claim nothing beyond verified_reply. "
        f"verified_reply: {masked_text}"
    )


async def _verified_prose_response(
    *,
    verified_text: str,
    deps: SalesDeps,
    model_name: str,
    customer_text: str,
    build_static_response: Callable[..., LLMResponse],
    build_llm_response: Callable[..., LLMResponse] | None = None,
    run_agent: Callable[[SalesDeps], Awaitable[Any]] | None = None,
    run_prose_agent: Callable[[str, SalesDeps], Awaitable[Any]] | None = None,
) -> LLMResponse:
    """Let the model write the sentence over facts a route already verified.

    The route's write has happened by the time this is called and nothing here
    can undo it: the rewrite runs with no tools at all. If the model is
    unavailable, fails, or changes a number, the route's own text ships exactly
    as it does today. The route label is kept either way, so the turn is still
    attributable; what changes is text_provenance.
    """

    if run_prose_agent is None or build_llm_response is None:
        logger.info(
            "Verified-prose rewrite skipped for %s: no model runner on this path",
            model_name,
        )
        return build_static_response(
            verified_text, model_name, response_deps=deps, allow_product_media=False
        )
    masked_text, values = _verified_prose_mask(verified_text)

    prose_deps = replace(deps, tool_mode="catalog_materialization")

    async def _attempt(retry: bool) -> Any:
        return await run_prose_agent(
            _verified_prose_directive(
                masked_text,
                len(values),
                retry,
                customer_name=_string_value(deps.conversation.customer_name),
                customer_text=customer_text,
            ),
            prose_deps,
        )

    try:
        result = await _attempt(False)
    except Exception:
        # Deliberately broad. By this point the quotation exists, the CRM row is
        # written or the selection is persisted, and the route's own reply is
        # already correct. A cosmetic rewrite must never turn that into an
        # error, so any failure ships the route text and is logged instead.
        logger.warning(
            "Verified-prose rewrite failed for %s; sending route text",
            model_name,
            exc_info=True,
        )
        return build_static_response(
            verified_text, model_name, response_deps=deps, allow_product_media=False
        )
    candidate = str(getattr(result, "output", "") or "")
    rendered, rejection = _verified_prose_render(
        candidate,
        values,
        verified_text=verified_text,
        customer_text=customer_text,
        already_said="\n".join(deps.recent_history or ()),
    )
    if rendered is None and rejection is not None and rejection.startswith("dropped"):
        # One reprompt naming the failure, which is what the parse-error loop in
        # ASPIRO does and what the model needs when it has ignored the tokens.
        try:
            result = await _attempt(True)
        except Exception:
            logger.warning(
                "Verified-prose retry failed for %s; sending route text", model_name
            )
            return build_static_response(
                verified_text, model_name, response_deps=deps, allow_product_media=False
            )
        rendered, rejection = _verified_prose_render(
            str(getattr(result, "output", "") or ""),
            values,
            verified_text=verified_text,
            customer_text=customer_text,
            already_said="\n".join(deps.recent_history or ()),
        )
    if rendered is None:
        logger.warning(
            "Verified-prose rewrite rejected for %s (%s); sending route text",
            model_name,
            rejection,
        )
        return build_static_response(
            verified_text, model_name, response_deps=deps, allow_product_media=False
        )
    return build_llm_response(
        # The verified figures are put back here, by code. Usage and telemetry
        # stay attached to the call that actually happened.
        _ContractedResult(result, rendered),
        model_name,
        response_deps=deps,
        allow_product_media=False,
    )


def _catalog_display_name(name: str) -> str:
    r"""Render a catalog name as a name, not as an escape sequence.

    A supplier packaging note reached a customer as "2 pcs\\1 ctn": the single
    backslash the catalog holds had been doubled somewhere upstream. Collapsing
    a run of backslashes back to one is true whichever layer doubled it, and it
    is the last point before the text is sent (tj-v41l).
    """

    return re.sub(r"\\{2,}", lambda _match: "\\", name.strip())


def _materialize_verified_catalog_recovery(
    deps: SalesDeps,
    tool_traces: tuple[RuntimeToolTrace, ...],
    *,
    explicit_quote_hold: bool,
) -> str | None:
    if deps.catalog_decision is not None:
        try:
            validate_catalog_decision(deps.catalog_decision)
        except ValueError:
            logger.warning(
                "Blocked verified catalog materialization after decision validation"
            )
            return None
    planning = deps.catalog_planning
    coverage_gaps = (
        {gap.family: gap for gap in deps.catalog_decision.coverage_gaps}
        if deps.catalog_decision is not None
        else {}
    )
    required_families = tuple(dict.fromkeys(planning.families))
    current_selections = deps.current_catalog_selections
    selected_by_family = current_selections or deps.verified_catalog_selections
    uses_current_selections = bool(current_selections)
    trace_names = tuple(trace.tool_name for trace in tool_traces)
    deterministic_plan_trace = trace_names == ("plan_catalog_configuration",)
    has_cross_sell_evidence = deterministic_plan_trace or (
        "recommend_products" in trace_names
        or (
            deps.verified_cross_sell is not None
            and trace_names.count("search_products") > len(required_families)
        )
    )
    allowed_tools = {
        "search_products",
        "recommend_products",
        "plan_catalog_configuration",
    }
    if (
        not explicit_quote_hold
        or deps.quotation_created
        or is_active_human_handoff(deps.conversation.escalation_status)
        or not planning.complete_coverage
        or planning.requested_seats is None
        or planning.budget_cap is None
        or not required_families
        or not tool_traces
        or any(trace.state != "returned" for trace in tool_traces)
        or not set(trace_names).issubset(allowed_tools)
        or tuple(deps.executed_tool_names) != trace_names
        or (
            not deterministic_plan_trace
            and trace_names.count("search_products") < len(required_families)
        )
        or not has_cross_sell_evidence
    ):
        return None

    selected_lines: list[VerifiedCatalogLine] = []
    uncovered_families: list[str] = []
    for family in required_families:
        family_lines = selected_by_family.get(family, ())
        if not family_lines and family not in coverage_gaps:
            return None
        if not family_lines:
            # A family with no verified option used to vanish from the list and
            # reappear only as a coverage gap, so "Workspace coverage gap: 0 of
            # 12" landed under twelve chairs and read as a contradiction of the
            # line above it (tj-v41l). Say the family found nothing.
            uncovered_families.append(family)
        family_total = 0.0
        family_coverage = 0
        for line in family_lines:
            if (
                line.family != family
                or not line.name.strip()
                or not line.sku.strip()
                or len(line.name.strip()) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
                or len(line.sku.strip()) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
                or line.quantity <= 0
                or line.unit_price <= 0
                or line.stock < line.quantity
                or line.capacity <= 0
                or abs(line.total - line.quantity * line.unit_price) > 0.01
            ):
                return None
            family_total += line.total
            family_coverage += line.quantity * line.capacity
        if family_coverage < planning.requested_seats:
            gap = coverage_gaps.get(family)
            if (
                gap is None
                or gap.requested != planning.requested_seats
                or gap.covered != family_coverage
            ):
                return None
        if (
            not uses_current_selections
            and abs(family_total - planning.family_totals.get(family, -1.0)) > 0.01
        ):
            return None
        selected_lines.extend(family_lines)

    selected_total = round(sum(line.total for line in selected_lines), 2)
    if not selected_lines or selected_total > planning.budget_cap:
        return None

    cross_sell = deps.verified_cross_sell
    disclosure = _string_value(deps.required_cross_sell_disclosure)
    if cross_sell is None and not disclosure:
        return None
    currencies = {line.currency.strip().upper() for line in selected_lines}
    if len(currencies) != 1 or "" in currencies:
        return None
    currency = currencies.pop()
    final_total = selected_total
    if cross_sell is not None:
        if (
            not cross_sell.name.strip()
            or len(cross_sell.name.strip()) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
            or (
                cross_sell.sku is not None
                and len(cross_sell.sku.strip()) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
            )
            or cross_sell.price <= 0
            or cross_sell.stock <= 0
            or cross_sell.currency.strip().upper() != currency
        ):
            return None
        final_total = round(selected_total + cross_sell.price, 2)
        if final_total > planning.budget_cap:
            return None

    remaining = round(planning.budget_cap - final_total, 2)
    language = str(deps.conversation.language)
    if language == "ar":
        heading = (
            f"تكوين جزئي مؤكد لـ {planning.requested_seats} مقعداً:"
            if coverage_gaps
            else f"تكوين مؤكد ضمن الميزانية لـ {planning.requested_seats} مقعداً:"
        )
        lines = [heading]
        lines.extend(
            (
                f"- {_catalog_display_name(line.name)} (SKU {line.sku}): "
                f"{line.quantity} × {line.unit_price:.2f} {currency} = "
                f"{line.total:.2f} {currency}"
            )
            for line in selected_lines
        )
        lines.extend(
            f"- {family}: لا يوجد خيار مؤكد ضمن الميزانية بعد."
            for family in uncovered_families
        )
        lines.append(f"إجمالي التكوين: {selected_total:.2f} {currency}.")
        if cross_sell is not None:
            sku = f" (SKU {cross_sell.sku})" if cross_sell.sku else ""
            lines.append(
                f"إضافة مؤكدة: {cross_sell.name}{sku} — "
                f"{cross_sell.price:.2f} {currency}."
            )
            lines.append(
                f"الإجمالي مع الإضافة: {final_total:.2f} {currency}. "
                f"المتبقي من الميزانية: {remaining:.2f} {currency}."
            )
        elif disclosure:
            lines.append(disclosure)
        for gap in coverage_gaps.values():
            lines.append(
                f"فجوة {gap.family}: تم تغطية {gap.covered} من {gap.requested}؛ "
                f"المتبقي {gap.requested - gap.covered}."
            )
            if gap.closing_question:
                lines.append(gap.closing_question)
        lines.append("لم يتم إنشاء عرض سعر.")
        response_text = "\n".join(lines)
        if len(response_text) <= _VERIFIED_CATALOG_RECOVERY_MAX_CHARS:
            return response_text
        compact_lines = [
            f"تكوين مؤكد ضمن الميزانية لـ {planning.requested_seats} مقعداً:"
        ]
        compact_lines.extend(
            (
                f"- {line.family} SKU {line.sku}: {line.quantity} × "
                f"{line.unit_price:.2f} {currency} = {line.total:.2f} {currency}"
            )
            for line in selected_lines
        )
        compact_lines.extend(
            f"- {family}: لا يوجد خيار مؤكد." for family in uncovered_families
        )
        compact_lines.extend(lines[1 + len(selected_lines) + len(uncovered_families) :])
        compact_text = "\n".join(compact_lines)
        return (
            compact_text
            if len(compact_text) <= _VERIFIED_CATALOG_RECOVERY_MAX_CHARS
            else None
        )

    heading = (
        f"Verified partial configuration for {planning.requested_seats} seats:"
        if coverage_gaps
        else f"Verified budget-fit configuration for {planning.requested_seats} seats:"
    )
    lines = [heading]
    lines.extend(
        (
            f"- {_catalog_display_name(line.name)} (SKU {line.sku}): "
            f"{line.quantity} × {currency} {line.unit_price:.2f} = "
            f"{currency} {line.total:.2f}"
        )
        for line in selected_lines
    )
    lines.extend(
        f"- {family.title()}: no verified option within budget yet."
        for family in uncovered_families
    )
    lines.append(f"Configuration total: {currency} {selected_total:.2f}.")
    if cross_sell is not None:
        sku = f" (SKU {cross_sell.sku})" if cross_sell.sku else ""
        lines.append(
            f"Verified cross-sell: {cross_sell.name}{sku} — "
            f"{currency} {cross_sell.price:.2f}."
        )
        lines.append(
            f"Total with cross-sell: {currency} {final_total:.2f}. "
            f"Remaining budget: {currency} {remaining:.2f}."
        )
    elif disclosure:
        lines.append(disclosure)
    for gap in coverage_gaps.values():
        lines.append(
            f"{gap.family.title()} coverage gap: {gap.covered} of {gap.requested}; "
            f"{gap.requested - gap.covered} uncovered."
        )
        if gap.closing_question:
            lines.append(gap.closing_question)
    lines.append("No quotation was created.")
    response_text = "\n".join(lines)
    if len(response_text) <= _VERIFIED_CATALOG_RECOVERY_MAX_CHARS:
        return response_text
    compact_lines = [
        f"Verified budget-fit configuration for {planning.requested_seats} seats:"
    ]
    compact_lines.extend(
        (
            f"- {line.family} SKU {line.sku}: {line.quantity} × "
            f"{currency} {line.unit_price:.2f} = {currency} {line.total:.2f}"
        )
        for line in selected_lines
    )
    compact_lines.extend(
        f"- {family.title()}: no verified option yet." for family in uncovered_families
    )
    compact_lines.extend(lines[1 + len(selected_lines) + len(uncovered_families) :])
    compact_text = "\n".join(compact_lines)
    return (
        compact_text
        if len(compact_text) <= _VERIFIED_CATALOG_RECOVERY_MAX_CHARS
        else None
    )


async def _complete_verified_cross_sell_for_recovery(
    ctx: RunContext[SalesDeps],
    *,
    explicit_quote_hold: bool,
) -> None:
    deps = ctx.deps
    planning = deps.catalog_planning
    required_families = tuple(dict.fromkeys(planning.families))
    trace_names = tuple(trace.tool_name for trace in deps.recovery_tool_traces)
    if (
        not explicit_quote_hold
        or not _CROSS_SELL_REQUEST_RE.search(deps.user_query)
        or not planning.complete_coverage
        or not required_families
        or deps.verified_cross_sell is not None
        or deps.required_cross_sell_disclosure is not None
        or any(trace.state != "returned" for trace in deps.recovery_tool_traces)
        or set(trace_names) != {"search_products"}
        or tuple(deps.executed_tool_names) != trace_names
        or trace_names.count("search_products") < len(required_families)
        or not all(
            deps.current_catalog_selections.get(family) for family in required_families
        )
    ):
        return

    primary_terms = {family: terms[0] for family, terms in _CATALOG_PRODUCT_FAMILIES}
    category = " ".join(
        primary_terms[family] for family in required_families if family in primary_terms
    )
    if not category:
        return

    try:
        await recommend_products(
            ctx,
            category=category,
            recommendation_type="cross_sell",
        )
    except Exception:
        logger.warning(
            "Verified catalog cross-sell recovery could not complete",
            exc_info=True,
        )


def _verified_catalog_plan_payload(
    deps: SalesDeps,
    selections: Mapping[CatalogFamily, tuple[VerifiedCatalogLine, ...]],
    *,
    cross_sell_status: Literal["verified", "not_found", "over_budget"],
) -> dict[str, object]:
    selected_total = _catalog_selection_total(
        selections,
        deps.catalog_planning.families,
    )
    cross_sell = deps.verified_cross_sell
    final_total = (
        round(selected_total + cross_sell.price, 2)
        if selected_total is not None and cross_sell is not None
        else selected_total
    )
    remaining_budget = (
        round(deps.catalog_planning.budget_cap - final_total, 2)
        if deps.catalog_planning.budget_cap is not None and final_total is not None
        else None
    )
    return {
        "version": 1,
        "epoch": deps.catalog_planning.epoch,
        "requested_seats": deps.catalog_planning.requested_seats,
        "families": list(deps.catalog_planning.families),
        "budget_cap": deps.catalog_planning.budget_cap,
        "currency": _CATALOG_BUDGET_CURRENCY,
        "selected_total": selected_total,
        "final_total": final_total,
        "remaining_budget": remaining_budget,
        "lines": [
            {
                "family": line.family,
                "name": line.name,
                "sku": line.sku,
                "quantity": line.quantity,
                "unit_price": line.unit_price,
                "total": line.total,
                "currency": line.currency,
                "stock": line.stock,
                "capacity": line.capacity,
            }
            for family in deps.catalog_planning.families
            for line in selections[family]
        ],
        "stock_snapshots": [
            {
                "sku": snapshot.sku,
                "available": snapshot.available,
                "source": snapshot.source,
                "provenance": snapshot.provenance,
                "as_of": snapshot.as_of.isoformat(),
            }
            for snapshot in sorted(
                deps.stock_snapshots.values(), key=lambda item: item.sku.casefold()
            )
        ],
        "coverage_gaps": [
            {
                "family": gap.family,
                "requested": gap.requested,
                "covered": gap.covered,
                "uncovered": gap.requested - gap.covered,
                "resolution": gap.resolution,
                "closing_question": gap.closing_question or None,
            }
            for gap in (
                deps.catalog_decision.coverage_gaps if deps.catalog_decision else ()
            )
        ],
        "cross_sell": (
            {
                "name": cross_sell.name,
                "sku": cross_sell.sku,
                "price": cross_sell.price,
                "currency": cross_sell.currency,
                "stock": cross_sell.stock,
            }
            if cross_sell is not None
            else None
        ),
        "cross_sell_status": cross_sell_status,
        "quotation_created": False,
    }


async def _store_verified_catalog_plan(
    deps: SalesDeps,
    selections: Mapping[CatalogFamily, tuple[VerifiedCatalogLine, ...]],
    *,
    cross_sell_status: Literal["verified", "not_found", "over_budget"],
) -> dict[str, object]:
    payload = _verified_catalog_plan_payload(
        deps,
        selections,
        cross_sell_status=cross_sell_status,
    )
    metadata = dict(deps.conversation.metadata_ or {})
    metadata[_VERIFIED_CATALOG_PLAN_KEY] = payload
    deps.conversation.metadata_ = metadata
    await deps.db.flush()
    return payload


async def _try_verified_catalog_plan(
    deps: SalesDeps,
) -> tuple[str, tuple[RuntimeToolTrace, ...]] | None:
    planning = deps.catalog_planning
    if (
        not _has_explicit_quote_hold(deps.user_query)
        or not _CROSS_SELL_REQUEST_RE.search(deps.user_query)
        or not planning.complete_coverage
        or planning.requested_seats is None
        or planning.budget_cap is None
        or not planning.families
        or is_active_human_handoff(deps.conversation.escalation_status)
    ):
        return None

    stmt = (
        select(Product)
        .options(
            load_only(
                Product.sku,
                Product.name_en,
                Product.name_ar,
                Product.description_en,
                Product.description_ar,
                Product.category,
                Product.subcategory,
                Product.price,
                Product.currency,
                Product.stock,
            )
        )
        .where(
            Product.is_active.is_(True),
            Product.stock > 0,
            Product.price > 0,
        )
    )
    result = await deps.db.execute(stmt)
    products = tuple(result.scalars().all())
    customer_context = "\n".join(
        entry.removeprefix("user:").strip()
        for entry in (*(deps.recent_history or ()), f"user: {deps.user_query}")
        if entry.startswith("user:")
    )
    segment = (
        str(
            (deps.crm_context or {}).get("Segment")
            or (deps.crm_context or {}).get("segment")
            or "Unknown"
        )
        if isinstance(deps.crm_context, Mapping)
        else "Unknown"
    )
    candidate_skus = _bounded_catalog_candidate_skus(
        planning,
        products,
        customer_context=customer_context,
        segment=segment,
    )
    authoritative_stock = await _zoho_stock_for_catalog_candidates(deps, candidate_skus)
    if authoritative_stock is None:
        return None
    stock_by_sku, stock_as_of = authoritative_stock
    selections = _solve_verified_catalog_selections(
        planning,
        products,
        customer_context=customer_context,
        segment=segment,
        authoritative_stock_by_sku=stock_by_sku,
    )
    if selections is None:
        return None
    coverage_gaps = _catalog_coverage_gaps(
        selections,
        planning.families,
        planning.requested_seats,
    )
    selected_stock = {
        line.sku.strip().casefold(): line
        for family_lines in selections.values()
        for line in family_lines
    }
    stock_snapshots = tuple(
        StockSnapshot(
            sku=line.sku,
            available=stock_by_sku[key],
            source="zoho",
            as_of=stock_as_of,
        )
        for key, line in selected_stock.items()
    )
    decision = CatalogDecision(
        requirements=tuple(planning.families),
        selected_lines=tuple(
            line for family in planning.families for line in selections[family]
        ),
        requested_seats=planning.requested_seats,
        budget_cap=planning.budget_cap,
        stock_snapshots=stock_snapshots,
        recommendation=(
            "verified_partial_configuration"
            if coverage_gaps
            else "verified_complete_configuration"
        ),
        coverage_gaps=coverage_gaps,
    )
    try:
        validate_catalog_decision(decision)
    except ValueError:
        logger.warning("Verified catalog plan failed authoritative stock validation")
        return None

    selected_total = _catalog_selection_total(selections, planning.families)
    if selected_total is None:
        return None
    remaining_budget = round(planning.budget_cap - selected_total, 2)
    selected_names = {
        line.name.casefold()
        for family_lines in selections.values()
        for line in family_lines
    }
    cross_sell_candidates: list[VerifiedCrossSell] = []
    cross_sell_over_budget = False
    try:
        from src.services.recommendations import get_cross_sell

        seen_names: set[str] = set()
        for family in dict.fromkeys(planning.families):
            source_category = _CATALOG_CROSS_SELL_SOURCE.get(family)
            if source_category is None:
                continue
            for item in await get_cross_sell(
                deps.db,
                source_category,
                limit=3,
            ):
                normalized_name = str(item.name).strip().casefold()
                price = round(float(item.price), 2)
                stock = int(item.stock)
                currency = (
                    str(getattr(item, "currency", _CATALOG_BUDGET_CURRENCY) or "")
                    .strip()
                    .upper()
                )
                sku = _string_value(getattr(item, "sku", None))
                if (
                    not normalized_name
                    or normalized_name in seen_names
                    or normalized_name in selected_names
                    or len(str(item.name).strip()) > _VERIFIED_CATALOG_FIELD_MAX_CHARS
                    or price <= 0
                    or stock <= 0
                    or currency != _CATALOG_BUDGET_CURRENCY
                ):
                    continue
                seen_names.add(normalized_name)
                if price > remaining_budget:
                    cross_sell_over_budget = True
                    continue
                cross_sell_candidates.append(
                    VerifiedCrossSell(
                        name=str(item.name).strip(),
                        sku=sku,
                        price=price,
                        currency=currency,
                        stock=stock,
                    )
                )
    except Exception:
        logger.warning(
            "Configured cross-sell lookup failed during deterministic catalog plan",
            exc_info=True,
        )
        return None

    verified_cross_sell = (
        min(
            cross_sell_candidates,
            key=lambda item: (item.price, item.name.casefold()),
        )
        if cross_sell_candidates
        else None
    )
    cross_sell_status: Literal["verified", "not_found", "over_budget"] = (
        "verified"
        if verified_cross_sell is not None
        else ("over_budget" if cross_sell_over_budget else "not_found")
    )
    cross_sell_disclosure = (
        None
        if verified_cross_sell is not None
        else _no_verified_cross_sell_disclosure(
            str(deps.conversation.language),
            has_budget=cross_sell_status == "over_budget",
        )
    )
    if coverage_gaps:
        verified_cross_sell = None
        cross_sell_status = "not_found"
        cross_sell_disclosure = (
            "تم تأجيل الإضافة حتى يتم إغلاق فجوة التغطية."
            if str(deps.conversation.language) == "ar"
            else "Cross-sell deferred until the coverage gap is closed."
        )
    resolved_planning = planning.model_copy(deep=True)
    resolved_planning.family_totals = {
        family: round(sum(line.total for line in selections[family]), 2)
        for family in resolved_planning.families
    }
    resolved_deps = replace(
        deps,
        catalog_planning=resolved_planning,
        current_catalog_selections=dict(selections),
        verified_catalog_selections=dict(selections),
        verified_cross_sell=verified_cross_sell,
        required_cross_sell_disclosure=cross_sell_disclosure,
        stock_snapshots={
            snapshot.sku.casefold(): snapshot for snapshot in stock_snapshots
        },
        catalog_decision=decision,
        executed_tool_names=[],
        recovery_tool_traces=[],
    )
    payload = _verified_catalog_plan_payload(
        resolved_deps,
        selections,
        cross_sell_status=cross_sell_status,
    )
    trace = build_runtime_tool_trace(
        tool_name="plan_catalog_configuration",
        arguments={
            "epoch": resolved_planning.epoch,
            "requested_seats": resolved_planning.requested_seats,
            "families": list(resolved_planning.families),
            "budget_cap": resolved_planning.budget_cap,
            "budget_currency": _CATALOG_BUDGET_CURRENCY,
            "per_item_cap": resolved_planning.per_item_cap,
        },
        outcome=payload,
    )
    resolved_deps.executed_tool_names = [trace.tool_name]
    resolved_deps.recovery_tool_traces = [trace]
    response = _engine_runtime()._materialize_verified_catalog_recovery(
        resolved_deps,
        (trace,),
        explicit_quote_hold=True,
    )
    if response is None:
        logger.error("Verified deterministic catalog plan failed materialization")
        return None

    await _store_catalog_planning(
        resolved_deps.db,
        resolved_deps.conversation,
        resolved_planning,
    )
    await _store_verified_catalog_plan(
        resolved_deps,
        selections,
        cross_sell_status=cross_sell_status,
    )
    deps.catalog_planning = resolved_planning
    deps.current_catalog_selections = dict(selections)
    deps.verified_catalog_selections = dict(selections)
    deps.verified_cross_sell = verified_cross_sell
    deps.required_cross_sell_disclosure = cross_sell_disclosure
    deps.stock_snapshots = dict(resolved_deps.stock_snapshots)
    deps.catalog_decision = decision
    deps.executed_tool_names = [trace.tool_name]
    deps.recovery_tool_traces = [trace]
    return response, (trace,)


def _bounded_catalog_candidate_skus(
    planning: CatalogPlanningContext,
    products: Sequence[Any],
    *,
    customer_context: str,
    segment: str,
) -> list[str]:
    candidates = _catalog_coverage_candidates(
        planning,
        products,
        customer_context=customer_context,
        segment=segment,
    )
    skus: list[str] = []
    for family in dict.fromkeys(planning.families):
        family_candidates = sorted(
            candidates.get(family, ()),
            key=lambda item: (
                item.unit_price / item.capacity,
                item.unit_price,
                item.name.casefold(),
                item.sku,
            ),
        )[:_CATALOG_DECISION_CANDIDATES_PER_FAMILY]
        skus.extend(candidate.sku for candidate in family_candidates)
    return list(dict.fromkeys(skus))


async def _zoho_stock_for_catalog_candidates(
    deps: SalesDeps,
    skus: Sequence[str],
) -> tuple[dict[str, int], datetime.datetime] | None:
    if not skus:
        return None
    try:
        raw_items = await deps.zoho_inventory.get_stock_bulk(list(skus))
    except Exception:
        logger.warning(
            "Zoho stock lookup failed for verified catalog plan", exc_info=True
        )
        return None
    if not isinstance(raw_items, list):
        return None

    stock_by_sku: dict[str, int] = {}
    for raw_item in raw_items:
        item = _coerce_inventory_item(raw_item, require_item_id=False)
        if item is None:
            continue
        raw_stock = item.get("stock_on_hand")
        if raw_stock is None:
            continue
        try:
            inventory_available = int(raw_stock)
        except (TypeError, ValueError):
            continue
        stock_by_sku[str(item["sku"]).strip().casefold()] = max(inventory_available, 0)

    return stock_by_sku, datetime.datetime.now(datetime.UTC)


__all__ = (
    "RuntimeToolTrace",
    "CLAIM_CONTRACT_SCOPE_KEY",
    "CatalogAmount",
    "CatalogBudgetConstraints",
    "CatalogCoverageGap",
    "CatalogDecision",
    "CatalogFactDomain",
    "CatalogFamily",
    "CatalogPlanningContext",
    "SalesDeps",
    "StockSnapshot",
    "VerifiedCatalogFactProduct",
    "VerifiedCatalogLine",
    "VerifiedOpeningCatalogLine",
    "VerifiedCrossSell",
    "_ACOUSTIC_FACT_GAP",
    "_ACOUSTIC_MEASUREMENT_RE",
    "_ACOUSTIC_PERFORMANCE_FACT_RE",
    "_ACOUSTIC_PRODUCT_QUERY_RE",
    "_ACOUSTIC_QUERY_RE",
    "_ACTIVE_PRODUCT_MEDIA_AUDIT_STATUSES",
    "_ADD_CATALOG_ACTION_RE",
    "_ANCHOR_FAMILIES",
    "_ANCHOR_MIN_STOCK",
    "_AR_PLANNING_CAPACITY_RE",
    "_BUDGET_CLAUSE_BOUNDARY_RE",
    "_CATALOG_BUDGET_CAP_RE",
    "_CATALOG_BUDGET_CURRENCY",
    "_CATALOG_CAPACITY_RE",
    "_CATALOG_COMPLETE_COVERAGE_TERMS",
    "_CATALOG_CONTINUATION_TERMS",
    "_CATALOG_CROSS_SELL_SOURCE",
    "_CATALOG_DECISION_CANDIDATES_PER_FAMILY",
    "_CATALOG_DECISION_UNUSABLE",
    "_CATALOG_FACT_COMPARISON_CONTEXT_RE",
    "_CATALOG_OPTION_CONTEXT_RE",
    "_CATALOG_PLANNING_KEY",
    "_CATALOG_PLAN_REFERENCE_RE",
    "_CATALOG_PRODUCT_FAMILIES",
    "_CATALOG_PRODUCT_SUBJECT",
    "_CATALOG_UNIT_PRODUCT_TERMS",
    "_CLAIM_CONTRACT_CONTRACT",
    "_CLAIM_CONTRACT_ROW_LIMIT",
    "_CLAIM_CONTRACT_SCOPE_EVERY_TURN",
    "_CLAIM_CONTRACT_VALUE_MAX_CHARS",
    "_COMPACT_NON_PRODUCT_RE",
    "_COMPACT_PRODUCT_QUERY_RE",
    "_CatalogCoverageCandidate",
    "_ContractedResult",
    "_DIMENSION_AXIS_RE",
    "_DIMENSION_PAIR_RE",
    "_DIMENSION_UNIT",
    "_FOOTPRINT_AREA_RE",
    "_FOOTPRINT_AXIS_CONTEXT_RE",
    "_FOOTPRINT_FACT_GAP",
    "_FOOTPRINT_PAIR_CONTEXT_RE",
    "_FOOTPRINT_PRODUCT_QUERY_RE",
    "_FOOTPRINT_QUERY_RE",
    "_LUMBAR_CLAUSE_BOUNDARY_RE",
    "_LUMBAR_POST_NEGATION_RE",
    "_LUMBAR_PRE_NEGATION_RE",
    "_LUMBAR_SUPPORT_TERMS",
    "_NEW_CATALOG_ACTION_RE",
    "_NEW_CATALOG_CONTEXT_RE",
    "_NEW_CATALOG_INTENT_RE",
    "_NON_FOOTPRINT_COMPONENT_RE",
    "_PER_ITEM_PRICE_RE",
    "_PLANNING_CAPACITY_RE",
    "_PLANNING_COUNT_VALUES",
    "_PRICE_FIGURE_RE",
    "_REPLACE_CATALOG_ACTION_RE",
    "_SKU_HOMOGLYPH_TRANSLATION",
    "_TOTAL_BUDGET_RE",
    "_VERIFIED_CATALOG_PLAN_KEY",
    "_VERIFIED_PROSE_EXAMPLE",
    "_VERIFIED_PROSE_LIST_MARKER_RE",
    "_VERIFIED_PROSE_MIN_OVERLAP",
    "_VERIFIED_PROSE_NUMBER_RE",
    "_VERIFIED_PROSE_PROTECTED_RE",
    "_VERIFIED_PROSE_SLOT_RE",
    "_VERIFIED_PROSE_WORD_RE",
    "_anchor_line_cache",
    "_append_required_tool_disclosures",
    "_best_catalog_coverage_selection",
    "_bounded_catalog_candidate_skus",
    "_budget_clause",
    "_catalog_budget_cap",
    "_catalog_budget_constraints",
    "_catalog_coverage_candidates",
    "_catalog_coverage_gaps",
    "_catalog_coverage_selection",
    "_catalog_decision_defects",
    "_catalog_decision_output_is_valid",
    "_catalog_decision_repair_directive",
    "_catalog_decision_runtime_directive",
    "_catalog_display_name",
    "_catalog_fact_match_is_negated",
    "_catalog_number_in_text",
    "_catalog_planning_for_turn",
    "_catalog_planning_from_metadata",
    "_catalog_product_capacity",
    "_catalog_product_families",
    "_catalog_product_family",
    "_catalog_product_text",
    "_catalog_recovery_output_is_valid",
    "_catalog_remaining_budget",
    "_catalog_replacement_families",
    "_catalog_search_query_with_constraints",
    "_catalog_selection_total",
    "_claim_contract_directive",
    "_claim_contract_runs_every_catalog_turn",
    "_complete_verified_cross_sell_for_recovery",
    "_contains_catalog_term",
    "_enforce_claim_contract",
    "_explicit_product_option_cap",
    "_has_acoustic_performance_evidence",
    "_has_footprint_dimension_evidence",
    "_has_positive_lumbar_support",
    "_has_unnegated_lumbar_term",
    "_is_catalog_fact_comparison_query",
    "_log_claim_contract",
    "_lumbar_term_is_negated",
    "_materialize_claim_rows",
    "_materialize_verified_catalog_facts",
    "_materialize_verified_catalog_recovery",
    "_minimum_catalog_coverage_selection",
    "_minimum_catalog_coverage_total",
    "_needs_complete_catalog_coverage",
    "_parse_claim_inputs",
    "_parse_claim_payload",
    "_planning_count_value",
    "_product_search_call_limit",
    "_product_search_response_contract",
    "_record_recovery_tool_result",
    "_requested_catalog_evidence_gaps",
    "_requested_catalog_fact_domains",
    "_requested_seat_count",
    "_requests_complete_catalog_coverage",
    "_requests_confirmed_lumbar_support",
    "_search_budget_fallback_contract",
    "_search_products_limit_message",
    "_should_override_policy_for_catalog_fact_query",
    "_solve_verified_catalog_selections",
    "_stock_follow_up_contract",
    "_store_catalog_planning",
    "_store_verified_catalog_plan",
    "_track_sales_tool",
    "_try_verified_catalog_plan",
    "_try_verified_opening_catalog_options",
    "_turn_owes_the_company_question",
    "_turn_saw_catalog_evidence",
    "_verified_catalog_plan_payload",
    "_verified_prose_content_words",
    "_verified_prose_directive",
    "_verified_prose_mask",
    "_verified_prose_numbers",
    "_verified_prose_render",
    "_verified_prose_response",
    "_verify_volunteered_claims",
    "_zoho_stock_for_catalog_candidates",
    "AnchorCatalogRow",
    "CatalogAnchor",
    "AnchorFamily",
    "anchor_family_of_row",
    "anchor_line_from_catalog_rows",
    "catalog_anchor",
    "catalog_anchor_from_catalog_rows",
    "catalog_anchor_line",
    "opening_wants_a_price_anchor",
    "build_runtime_tool_trace",
    "grounded_amounts_for_turn",
    "validate_catalog_decision",
)
