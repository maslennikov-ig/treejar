"""Pure customer fact extraction boundary for the memory layer."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.core.config import settings
from src.dialogue.order_guards import is_order_selection_blocked
from src.dialogue.order_runtime import run_order_runtime
from src.dialogue.order_state import order_lines_snapshot
from src.llm.money import (
    AMOUNT_TOKEN_PATTERN,
    BUDGET_AED_CURRENCY_PATTERN,
    canonical_amount,
)
from src.llm.pii import EMAIL_PATTERN, PHONE_PATTERN
from src.llm.safety import (
    PATH_FACT_EXTRACTION,
    model_settings_for_path,
    usage_limits_for_path,
)

CustomerFactScope = Literal[
    "persistent_profile",
    "current_order",
    "past_order_reference",
]
CustomerFactConfidence = Literal["high", "medium", "low"]
CustomerFactSource = Literal["deterministic", "fast_model"]

MAX_EVIDENCE_CHARS = 160
_COMPANY_PATTERN = re.compile(
    r"\b(?:company\s+name|company|account|organization|organisation)"
    r"\s*(?:is|:|-)\s*(?P<value>[^,.;\n]+)",
    re.IGNORECASE,
)
_LABELED_NAME_PATTERN = re.compile(
    r"\b(?:my\s+name\s+is|name\s*(?:is|:|-))\s*"
    r"(?P<value>[A-Za-z][A-Za-z .'-]{1,60})",
    re.IGNORECASE,
)
_CUSTOMER_LABEL_NAME_PATTERN = re.compile(
    r"\bcustomer(?:\s+name)?\s*(?:is|:|-)\s*"
    r"(?P<value>[A-Za-z][A-Za-z '-]{1,60})(?=$|[,.;\n])",
    re.IGNORECASE,
)
_FROM_NAME_PATTERN = re.compile(
    r"^\s*(?P<value>[A-Za-z][A-Za-z .'-]{1,60})\s+from\s+",
    re.IGNORECASE,
)
_ADDRESS_LABEL_PATTERN = re.compile(
    r"\b(?:delivery\s+address|(?<!email\s)(?<!billing\s)address|"
    r"delivered\s+to|deliver\s+to|delivery\s+to|with\s+delivery\s+to|"
    r"ship\s+to|shipped\s+to|shipping\s+to|send\s+to)\b"
    r"\s*(?:is|:|-)?\s*",
    re.IGNORECASE,
)
_ADDRESS_DETAIL_BOUNDARY_PATTERN = re.compile(
    r"(?:[,;/]|\n|\.\s+)\s*"
    r"(?=(?:email|e-mail|phone|mobile|whatsapp|tel|full\s+name|my\s+name|"
    r"name|customer(?:\s+name)?|company(?:\s+name)?|account|organization|"
    r"organisation|individual|private\s+customer|corporate|budget|color|"
    r"colour|assembly|i\s+am|i'm|we\s+are|i\s+need|we\s+need|need|want|"
    r"please|proceed|can|could|would|will|do|does|did|what|which|where|"
    r"when|how|is|are|was|were|may)\b|"
    rf"{EMAIL_PATTERN.pattern}|\+\d)",
    re.IGNORECASE,
)
_ADDRESS_SEGMENT_PATTERN = re.compile(r"[^,;\n/]+")
_ADDRESS_TERM_PATTERN = re.compile(
    r"\b(?:street|st|road|rd|avenue|ave|villa|office|building|tower|suite|"
    r"unit|floor|apartment|apt|plot|warehouse|zone)\b",
    re.IGNORECASE,
)
_ADDRESS_DISTRICT_PATTERN = re.compile(
    r"\b(?:business\s+bay|dubai\s+marina|jlt|difc)\b",
    re.IGNORECASE,
)
_DETAIL_SEGMENT_PATTERN = re.compile(
    r"^(?:email|e-mail|phone|mobile|whatsapp|tel|full\s+name|my\s+name|"
    r"name|customer(?:\s+name)?|company(?:\s+name)?|account|organization|"
    r"organisation|individual|private\s+customer|corporate|budget|color|"
    r"colour|assembly)\b",
    re.IGNORECASE,
)
_GENERIC_SPACED_SKU_PATTERN = re.compile(r"\b[A-Z]{1,4}\s*[- ]\s*\d{2,8}\b")
_BUDGET_PATTERN = re.compile(
    r"\b(?:budget\s*(?P<q1>under|below|up\s+to|around|about|approx(?:imately)?)?"
    r"|(?P<q2>under|below|up\s+to|around|about|approx(?:imately)?))"
    rf"\s*(?P<currency1>{BUDGET_AED_CURRENCY_PATTERN})?\s*"
    rf"(?P<amount>{AMOUNT_TOKEN_PATTERN})\s*"
    rf"(?P<currency2>{BUDGET_AED_CURRENCY_PATTERN})?\b",
    re.IGNORECASE,
)
_REVERSE_BUDGET_PATTERN = re.compile(
    rf"\b(?P<currency1>{BUDGET_AED_CURRENCY_PATTERN})?\s*"
    rf"(?P<amount>{AMOUNT_TOKEN_PATTERN})\s*"
    rf"(?P<currency2>{BUDGET_AED_CURRENCY_PATTERN})?\s+budget\b",
    re.IGNORECASE,
)
_COLOR_PATTERN = re.compile(
    r"\b(?:color|colour)\s*(?:is|:|-)?\s*"
    r"(?P<after>black|white|grey|gray|blue|green|red|beige|brown|oak|walnut)\b"
    r"|\b(?P<before>black|white|grey|gray|blue|green|red|beige|brown|oak|walnut)"
    r"\s+(?:color|colour)\b",
    re.IGNORECASE,
)
_DELIVERY_REQUIRED_PATTERN = re.compile(
    r"\b(?:need|needs|require|requires|request|requested|include|with|want|wants)"
    r"\b.{0,40}\bdelivery\b"
    r"|\bdelivery\b.{0,24}\b(?:needed|required|please|included)\b",
    re.IGNORECASE,
)
_ASSEMBLY_REQUIRED_PATTERN = re.compile(
    r"\b(?:need|needs|require|requires|request|requested|include|with|want|wants)"
    r"\b.{0,40}\bassembly\b"
    r"|\bassembly\b.{0,24}\b(?:needed|required|please|included)\b",
    re.IGNORECASE,
)
_INDIVIDUAL_PATTERN = re.compile(
    r"\b(individual|private\s+customer|personal\s+capacity|no\s+company)\b",
    re.IGNORECASE,
)
_COMPANY_TYPE_PATTERN = re.compile(
    r"\b(company\s+customer|corporate|as\s+a\s+company)\b",
    re.IGNORECASE,
)
_PAST_ORDER_QUERY_PATTERN = re.compile(
    r"\b(?:what\s+did\s+i\s+order\s+(?:last\s+time|before)"
    r"|previous\s+order|last\s+order)\b",
    re.IGNORECASE,
)
_PAST_ORDER_REUSE_PATTERN = re.compile(
    r"\b(?:same\s+as\s+last\s+time|same\s+order|repeat\s+(?:the\s+)?last\s+order"
    r"|like\s+last\s+time)\b",
    re.IGNORECASE,
)
_ASSISTANT_GREETING_PATTERN = re.compile(
    r"^\s*(?:hi|hello|hey|dear|good\s+morning|good\s+afternoon|good\s+evening)"
    r"\s+(?:noor|siyyad|treejar|bot|assistant)\s*$",
    re.IGNORECASE,
)
_GREETING_ONLY_PATTERN = re.compile(
    r"^\s*(?:hi|hello|hey|dear|good\s+morning|good\s+afternoon|good\s+evening)\s*$",
    re.IGNORECASE,
)
_SYNTHETIC_TEST_MARKER_PATTERN = re.compile(
    r"\s*\[(?:smoke:[^\]]+|e2emarker[^\]]+|tj-[a-z0-9_-]*\d{8,}[a-z0-9_-]*)\]\s*",
    re.IGNORECASE,
)
_PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN = re.compile(
    r"\b(?:need|needs|want|wants|would\s+like|looking\s+for|quote|quotation|"
    r"chair|chairs|desk|desks|table|tables|workstation|workstations|sku|"
    r"assembly|installation)\b",
    re.IGNORECASE,
)
_FAST_FACT_KEY_ALIASES: dict[str, tuple[CustomerFactScope, str]] = {
    "delivery_address": ("current_order", "delivery.address"),
    "customer.display_name": ("persistent_profile", "customer.name"),
    "customer.primary_email": ("persistent_profile", "customer.email"),
}
_CANONICAL_FACT_SCOPES: dict[str, CustomerFactScope] = {
    "customer.name": "persistent_profile",
    "customer.email": "persistent_profile",
    "customer.phone": "persistent_profile",
    "customer.company": "persistent_profile",
    "customer.language": "persistent_profile",
    "customer.type": "current_order",
    "delivery.address": "current_order",
    "order.delivery_required": "current_order",
    "order.assembly_required": "current_order",
    "order.color_preference": "current_order",
    "order.budget": "current_order",
    "quote.status": "current_order",
    "quote.objection": "current_order",
    "past_order.query": "past_order_reference",
    "past_order.reuse_request": "past_order_reference",
}
_QUOTE_ACCEPTANCE_PATTERNS = (
    re.compile(
        r"\b(?:i\s+agree|agreed|agree|accepted|approve|approved|go\s+ahead"
        r"|proceed|ok\s+to\s+proceed|let'?s\s+proceed)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:\bموافق\b|أوافق|اوافق|تمام)"),
)
_QUOTE_REFUSAL_PATTERNS = (
    re.compile(
        r"\b(?:no\s+thanks|not\s+interested|refuse|refused|reject|rejected"
        r"|decline|declined)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:لا\s*شكرا|لا\s+شكر)"),
)
_PRICE_OBJECTION_PATTERNS = (
    re.compile(
        r"\b(?:too\s+expensive|expensive|price\s+is\s+high|price\s+is\s+too\s+high"
        r"|need\s+(?:a\s+)?discount|can\s+you\s+adjust\s+the\s+price"
        r"|cheaper\s+option)\b",
        re.IGNORECASE,
    ),
    re.compile(r"(?:غالي|مرتفع|خصم|السعر\s+مرتفع)"),
)


class ExtractedCustomerFact(BaseModel):
    scope: CustomerFactScope
    key: str
    value: Any
    confidence: CustomerFactConfidence
    source: CustomerFactSource
    evidence: str = Field(min_length=1, max_length=MAX_EVIDENCE_CHARS)
    source_message_id: str | None = None
    needs_confirmation: bool = False
    conflicts_with: str | None = None


class CustomerFactExtractionTrace(BaseModel):
    deterministic_fact_count: int = 0
    fast_model_called: bool = False
    fast_model_model: str | None = None
    fast_model_failed: bool = False
    fast_model_failure: str | None = None
    fast_model_note: str | None = None
    fast_model_skipped_reason: str | None = None


class CustomerFactExtractionResult(BaseModel):
    facts: list[ExtractedCustomerFact] = Field(default_factory=list)
    trace: CustomerFactExtractionTrace = Field(
        default_factory=CustomerFactExtractionTrace
    )


class FastCustomerFactExtractionRequest(BaseModel):
    message_text: str
    model: str
    deterministic_facts: list[ExtractedCustomerFact] = Field(default_factory=list)
    source_message_id: str | None = None
    expected_labels: list[str] = Field(default_factory=list)


class FastCustomerFactExtractionOutput(BaseModel):
    facts: list[ExtractedCustomerFact] = Field(default_factory=list)
    trace_note: str | None = None


FastCustomerFactExtractor = Callable[
    [FastCustomerFactExtractionRequest],
    Awaitable[FastCustomerFactExtractionOutput],
]

FAST_EXTRACTOR_INSTRUCTIONS = """\
Extract sales-relevant customer facts from one inbound WhatsApp message.

Return only structured facts matching the output schema. Keep evidence short.
Use scopes exactly:
- persistent_profile: customer.name, customer.email, customer.phone,
  customer.company, customer.language.
- current_order: customer.type, delivery.address, order.delivery_required,
  order.assembly_required, order.color_preference, order.budget, quote.status,
  quote.objection.
- past_order_reference: past_order.query, past_order.reuse_request.

Use these canonical dotted keys exactly. Other legitimate sales-relevant facts
may use a stable dotted key in the appropriate scope.

Do not invent facts. Mark past-order reuse as needs_confirmation=true.
"""


class PydanticAIFastCustomerFactExtractor:
    """Default live fast-model boundary, kept lazy and injectable for tests."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.openrouter_model_fast

    async def __call__(
        self,
        request: FastCustomerFactExtractionRequest,
    ) -> FastCustomerFactExtractionOutput:
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        model_settings = model_settings_for_path(
            PATH_FACT_EXTRACTION,
            model_name=self.model_name,
        )
        usage_limits = usage_limits_for_path(PATH_FACT_EXTRACTION)
        if usage_limits is None:
            raise RuntimeError("Fact extraction safety policy must be non-core")
        model = OpenAIChatModel(
            self.model_name,
            provider=OpenRouterProvider(api_key=settings.openrouter_api_key),
            settings=model_settings,
        )
        agent: Agent[None, FastCustomerFactExtractionOutput] = Agent(
            model,
            output_type=FastCustomerFactExtractionOutput,
            retries=0,
            instructions=FAST_EXTRACTOR_INSTRUCTIONS,
            model_settings=model_settings,
        )
        result = await agent.run(
            _build_fast_model_prompt(request),
            model=model,
            model_settings=model_settings,
            usage_limits=usage_limits,
        )
        return result.output


async def extract_customer_facts(
    message_text: str,
    *,
    source_message_id: str | None = None,
    fast_extractor: FastCustomerFactExtractor | None = None,
    use_fast_model: bool = True,
    expected_labels: Iterable[str] = (),
) -> CustomerFactExtractionResult:
    """Extract deterministic facts first, then optionally call a fast model."""

    message_text = _strip_synthetic_test_markers(message_text)
    deterministic_facts = _extract_deterministic_facts(
        message_text,
        source_message_id=source_message_id,
    )
    trace = CustomerFactExtractionTrace(
        deterministic_fact_count=len(deterministic_facts)
    )
    facts = list(deterministic_facts)

    if not use_fast_model:
        trace.fast_model_skipped_reason = "disabled"
        return CustomerFactExtractionResult(facts=facts, trace=trace)

    runner = fast_extractor
    if runner is None and _should_call_default_fast_model(message_text, facts):
        runner = PydanticAIFastCustomerFactExtractor()

    if runner is None:
        trace.fast_model_skipped_reason = "not_ambiguous"
        return CustomerFactExtractionResult(facts=facts, trace=trace)

    model_name = getattr(runner, "model_name", settings.openrouter_model_fast)
    request = FastCustomerFactExtractionRequest(
        message_text=_redact_fast_model_text(message_text),
        source_message_id=source_message_id,
        deterministic_facts=[_sanitize_fact_for_fast_model(fact) for fact in facts],
        expected_labels=list(expected_labels),
        model=model_name,
    )
    trace.fast_model_called = True
    trace.fast_model_model = model_name

    try:
        fast_output = await runner(request)
    except Exception as exc:  # noqa: BLE001 - extractor failure must not escape.
        trace.fast_model_failed = True
        trace.fast_model_failure = _bounded_failure(exc)
        return CustomerFactExtractionResult(facts=facts, trace=trace)

    trace.fast_model_note = _bound_text(fast_output.trace_note)
    facts.extend(
        _normalize_fast_facts(
            fast_output.facts,
            message_text=message_text,
            source_message_id=source_message_id,
        )
    )
    return CustomerFactExtractionResult(facts=_dedupe_facts(facts), trace=trace)


def _extract_deterministic_facts(
    message_text: str,
    *,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    facts.extend(_extract_email_facts(message_text, source_message_id))
    facts.extend(_extract_phone_facts(message_text, source_message_id))
    facts.extend(_extract_name_facts(message_text, source_message_id))
    facts.extend(_extract_company_facts(message_text, source_message_id))
    facts.extend(_extract_customer_type_facts(message_text, source_message_id))
    facts.extend(_extract_address_facts(message_text, source_message_id))
    facts.extend(_extract_compact_slash_quote_facts(message_text, source_message_id))
    facts.extend(_extract_order_item_facts(message_text, source_message_id))
    facts.extend(_extract_preference_facts(message_text, source_message_id))
    facts.extend(_extract_quote_status_facts(message_text, source_message_id))
    facts.extend(_extract_past_order_facts(message_text, source_message_id))
    return _dedupe_facts(facts)


def _extract_email_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    return [
        _fact(
            scope="persistent_profile",
            key="customer.email",
            value=match.group(0),
            confidence="high",
            evidence=match.group(0),
            source_message_id=source_message_id,
        )
        for match in EMAIL_PATTERN.finditer(message_text)
    ]


def _extract_phone_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    for match in PHONE_PATTERN.finditer(message_text):
        if not is_customer_phone_detail(message_text, match):
            continue
        raw_phone = match.group(0)
        digits = re.sub(r"\D", "", raw_phone)
        if len(digits) < 7:
            continue
        normalized = f"+{digits}" if raw_phone.strip().startswith("+") else digits
        facts.append(
            _fact(
                scope="persistent_profile",
                key="customer.phone",
                value=normalized,
                confidence="high",
                evidence=raw_phone,
                source_message_id=source_message_id,
            )
        )
    return facts


def is_customer_phone_detail(text: str, match: re.Match[str]) -> bool:
    """Return whether a broad phone-pattern match is customer contact data."""

    raw_phone = match.group(0).strip()
    if raw_phone.startswith("+"):
        return True
    prefix = text[max(0, match.start() - 40) : match.start()].casefold()
    return bool(
        re.search(
            r"(?:phone|mobile|tel|whatsapp)\s*[:：=-]?\s*$",
            prefix,
        )
    )


def _extract_name_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    for match in _CUSTOMER_LABEL_NAME_PATTERN.finditer(message_text):
        name = _clean_person_name(match.group("value"))
        if name:
            facts.append(
                _fact(
                    scope="persistent_profile",
                    key="customer.name",
                    value=name,
                    confidence="high",
                    evidence=match.group(0),
                    source_message_id=source_message_id,
                )
            )

    for match in _LABELED_NAME_PATTERN.finditer(message_text):
        prefix = message_text[max(0, match.start() - 24) : match.start()]
        if re.search(r"\bcompany\s*$", prefix, re.IGNORECASE):
            continue
        name = _clean_person_name(match.group("value"))
        if name:
            facts.append(
                _fact(
                    scope="persistent_profile",
                    key="customer.name",
                    value=name,
                    confidence="high",
                    evidence=match.group(0),
                    source_message_id=source_message_id,
                )
            )

    from_name = _FROM_NAME_PATTERN.search(message_text)
    if from_name:
        name = _clean_person_name(from_name.group("value"))
        if name:
            facts.append(
                _fact(
                    scope="persistent_profile",
                    key="customer.name",
                    value=name,
                    confidence="medium",
                    evidence=from_name.group(0),
                    source_message_id=source_message_id,
                )
            )

    compact_name = _compact_name_candidate(message_text)
    if compact_name:
        facts.append(
            _fact(
                scope="persistent_profile",
                key="customer.name",
                value=compact_name,
                confidence="medium",
                evidence=compact_name,
                source_message_id=source_message_id,
            )
        )

    return facts


def _extract_company_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    for match in _COMPANY_PATTERN.finditer(message_text):
        company = _clean_value(match.group("value"))
        if (
            company
            and "?" not in company
            and re.search(
                r"[^\W\d_]",
                company,
                re.UNICODE,
            )
        ):
            facts.append(
                _fact(
                    scope="persistent_profile",
                    key="customer.company",
                    value=company,
                    confidence="high",
                    evidence=match.group(0),
                    source_message_id=source_message_id,
                )
            )
    return facts


def _extract_customer_type_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    individual = _INDIVIDUAL_PATTERN.search(message_text)
    if individual:
        return [
            _fact(
                scope="current_order",
                key="customer.type",
                value="individual",
                confidence="high",
                evidence=individual.group(0),
                source_message_id=source_message_id,
            )
        ]

    company = _COMPANY_TYPE_PATTERN.search(message_text)
    if company:
        return [
            _fact(
                scope="current_order",
                key="customer.type",
                value="company",
                confidence="high",
                evidence=company.group(0),
                source_message_id=source_message_id,
            )
        ]

    return []


def _extract_address_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    candidate = _delivery_address_candidate(message_text)
    if candidate is None:
        return []
    address, evidence, labeled = candidate
    return [
        _fact(
            scope="current_order",
            key="delivery.address",
            value=_clean_value(address),
            confidence="high" if labeled else "medium",
            evidence=evidence,
            source_message_id=source_message_id,
        )
    ]


def _extract_order_item_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    if is_order_selection_blocked(message_text):
        return facts

    order_runtime = run_order_runtime(text=message_text, metadata={})
    order_snapshot = order_lines_snapshot(order_runtime.intent)
    if (
        order_runtime.decision.route == "product_selection"
        and order_runtime.decision.handled
        and order_snapshot
    ):
        facts.append(
            _fact(
                scope="current_order",
                key="order.items",
                value=order_snapshot,
                confidence="high",
                evidence=_order_items_evidence(order_snapshot),
                source_message_id=source_message_id,
            )
        )
        return facts
    if order_runtime.intent.lines:
        return facts
    return facts


def _order_items_evidence(snapshot: list[dict[str, object]]) -> str:
    parts: list[str] = []
    for item in snapshot:
        quantity = item.get("quantity")
        catalog_ref = item.get("catalog_ref") or item.get("sku") or item.get("name")
        if quantity and catalog_ref:
            parts.append(f"{quantity} x {catalog_ref}")
    return "; ".join(parts) or "order.items"


def _extract_preference_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []

    delivery_match = _DELIVERY_REQUIRED_PATTERN.search(message_text)
    if delivery_match and "delivery address" not in delivery_match.group(0).lower():
        facts.append(
            _fact(
                scope="current_order",
                key="order.delivery_required",
                value=True,
                confidence="medium",
                evidence=delivery_match.group(0),
                source_message_id=source_message_id,
            )
        )

    assembly_match = _ASSEMBLY_REQUIRED_PATTERN.search(message_text)
    if assembly_match:
        facts.append(
            _fact(
                scope="current_order",
                key="order.assembly_required",
                value=True,
                confidence="medium",
                evidence=assembly_match.group(0),
                source_message_id=source_message_id,
            )
        )

    color_match = _COLOR_PATTERN.search(message_text)
    if color_match:
        color = color_match.group("after") or color_match.group("before")
        facts.append(
            _fact(
                scope="current_order",
                key="order.color_preference",
                value=color.lower(),
                confidence="medium",
                evidence=color_match.group(0),
                source_message_id=source_message_id,
            )
        )

    budget_match = _BUDGET_PATTERN.search(message_text)
    if budget_match is None:
        budget_match = _REVERSE_BUDGET_PATTERN.search(message_text)
    if budget_match:
        facts.append(
            _fact(
                scope="current_order",
                key="order.budget",
                value=_budget_value(budget_match),
                confidence="medium",
                evidence=budget_match.group(0),
                source_message_id=source_message_id,
            )
        )

    return facts


def _extract_quote_status_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    refusal = _first_pattern_match(_QUOTE_REFUSAL_PATTERNS, message_text)
    if refusal:
        return [
            _fact(
                scope="current_order",
                key="quote.status",
                value="refused",
                confidence="high",
                evidence=refusal.group(0),
                source_message_id=source_message_id,
            )
        ]

    price_objection = _first_pattern_match(_PRICE_OBJECTION_PATTERNS, message_text)
    if price_objection:
        return [
            _fact(
                scope="current_order",
                key="quote.objection",
                value="price",
                confidence="medium",
                evidence=price_objection.group(0),
                source_message_id=source_message_id,
            )
        ]

    acceptance = _first_pattern_match(_QUOTE_ACCEPTANCE_PATTERNS, message_text)
    if acceptance:
        return [
            _fact(
                scope="current_order",
                key="quote.status",
                value="accepted",
                confidence="high",
                evidence=acceptance.group(0),
                source_message_id=source_message_id,
            )
        ]

    return []


def _extract_past_order_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    query = _PAST_ORDER_QUERY_PATTERN.search(message_text)
    if query:
        return [
            _fact(
                scope="past_order_reference",
                key="past_order.query",
                value={"reference": "last_order"},
                confidence="high",
                evidence=query.group(0),
                source_message_id=source_message_id,
            )
        ]

    reuse = _PAST_ORDER_REUSE_PATTERN.search(message_text)
    if reuse:
        return [
            _fact(
                scope="past_order_reference",
                key="past_order.reuse_request",
                value={"reference": "last_order"},
                confidence="high",
                evidence=reuse.group(0),
                source_message_id=source_message_id,
                needs_confirmation=True,
            )
        ]

    return []


def _fact(
    *,
    scope: CustomerFactScope,
    key: str,
    value: Any,
    confidence: CustomerFactConfidence,
    evidence: str,
    source_message_id: str | None,
    source: CustomerFactSource = "deterministic",
    needs_confirmation: bool = False,
) -> ExtractedCustomerFact:
    return ExtractedCustomerFact(
        scope=scope,
        key=key,
        value=value,
        confidence=confidence,
        source=source,
        evidence=_bound_text(evidence) or key,
        source_message_id=source_message_id,
        needs_confirmation=needs_confirmation,
    )


def _compact_name_candidate(message_text: str) -> str | None:
    parts = _detail_parts(message_text)
    if len(parts) < 2:
        return None

    first = _compact_name_part_candidate(parts[0])
    if not first:
        return None

    rest = " ".join(parts[1:]).lower()
    if (
        EMAIL_PATTERN.search(message_text)
        or PHONE_PATTERN.search(message_text)
        or _INDIVIDUAL_PATTERN.search(rest)
        or _COMPANY_TYPE_PATTERN.search(rest)
        or "company" in rest
        or _looks_like_address(" ".join(parts[1:]))
    ):
        return first
    return None


def _compact_name_part_candidate(value: str) -> str | None:
    candidates = [segment.strip() for segment in re.split(r"[.!?]", value)]
    candidates.append(value.strip())
    for candidate in reversed(candidates):
        if is_question_clause(candidate, len(candidate)):
            continue
        if _GREETING_ONLY_PATTERN.fullmatch(candidate):
            continue
        if _ASSISTANT_GREETING_PATTERN.fullmatch(candidate):
            continue
        if _LABELED_NAME_PATTERN.search(candidate):
            continue
        if _ADDRESS_LABEL_PATTERN.search(candidate):
            continue
        name = _clean_person_name(candidate)
        if name and _looks_like_person_name(name):
            return name
    return None


def extract_delivery_address(text: str) -> str | None:
    """Extract one specific delivery address without adjacent customer details."""

    candidate = _delivery_address_candidate(text)
    return candidate[0] if candidate else None


def _delivery_address_candidate(text: str) -> tuple[str, str, bool] | None:
    for label_match in _ADDRESS_LABEL_PATTERN.finditer(text):
        if is_question_clause(text, label_match.start()):
            continue
        raw_value = _address_before_next_detail(text[label_match.end() :])
        if not _looks_like_address(raw_value):
            continue
        evidence_end = label_match.end() + len(raw_value)
        evidence = text[label_match.start() : evidence_end].strip()
        return raw_value, evidence, True

    segments = list(_ADDRESS_SEGMENT_PATTERN.finditer(text))
    for index, segment_match in enumerate(segments):
        segment = segment_match.group(0).strip()
        embedded_label = _ADDRESS_LABEL_PATTERN.search(segment)
        if embedded_label and is_question_clause(
            text,
            segment_match.start() + embedded_label.start(),
        ):
            continue
        next_segment = (
            segments[index + 1].group(0).strip() if index + 1 < len(segments) else None
        )
        if not _is_address_start_segment(segment, next_segment):
            continue

        start = (
            segment_match.start()
            + len(segment_match.group(0))
            - len(segment_match.group(0).lstrip())
        )
        end = segment_match.end()
        for following in segments[index + 1 :]:
            following_value = following.group(0).strip()
            if _is_adjacent_customer_detail(text, following, following_value):
                break
            end = following.end()

        raw_value = text[start:end].strip(" \t\r\n,;/").rstrip(".")
        if _looks_like_address(raw_value):
            return raw_value, raw_value, False
    return None


def is_question_clause(text: str, offset: int) -> bool:
    """Return whether the sentence before ``offset`` starts as a question."""

    offset = max(0, min(offset, len(text)))
    sentence_starts = [0]
    for boundary in ("\n", ". ", "!", "?"):
        position = text.rfind(boundary, 0, offset)
        if position >= 0:
            sentence_starts.append(position + len(boundary))
    prefix = text[max(sentence_starts) : offset].strip()
    return bool(
        re.match(
            r"(?:(?:can|could|would|do|does|did|what|which|where|when|how|"
            r"is|are|was|were)\b|(?:will|may)\s+"
            r"(?:i|you|we|they|he|she|it|there|the|this|that|our|your|delivery)\b)",
            prefix,
            re.IGNORECASE,
        )
    )


def _address_before_next_detail(tail: str) -> str:
    boundary = _ADDRESS_DETAIL_BOUNDARY_PATTERN.search(tail)
    raw_value = tail[: boundary.start()] if boundary else tail
    return raw_value.strip(" \t\r\n,;/").rstrip(".")


def _is_address_start_segment(segment: str, next_segment: str | None) -> bool:
    if not segment or "?" in segment:
        return False
    if _ADDRESS_DISTRICT_PATTERN.search(segment):
        return True
    if _ADDRESS_TERM_PATTERN.search(segment) and re.search(r"\d", segment):
        return True
    if re.search(r"\b\d+[A-Za-z]?\s+[A-Za-z]", segment):
        return True
    return bool(
        re.fullmatch(r"\d+[A-Za-z]?", segment)
        and next_segment
        and _ADDRESS_TERM_PATTERN.search(next_segment)
    )


def _is_adjacent_customer_detail(
    text: str,
    match: re.Match[str],
    value: str,
) -> bool:
    if not value:
        return False
    if EMAIL_PATTERN.search(value) or _DETAIL_SEGMENT_PATTERN.search(value):
        return True
    return any(
        is_customer_phone_detail(text, phone_match)
        for phone_match in PHONE_PATTERN.finditer(
            text,
            match.start(),
            match.end(),
        )
    )


def _extract_compact_slash_quote_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    if "/" not in message_text:
        return []
    parts = _detail_parts(message_text)
    if len(parts) < 3:
        return []

    company = _compact_company_part_candidate(parts[1])
    if not company:
        return []
    return [
        _fact(
            scope="persistent_profile",
            key="customer.company",
            value=company,
            confidence="medium",
            evidence=company,
            source_message_id=source_message_id,
        )
    ]


def _compact_company_part_candidate(value: str) -> str | None:
    candidate = _clean_value(value)
    if not candidate or len(candidate) > 100:
        return None
    if EMAIL_PATTERN.search(candidate) or PHONE_PATTERN.search(candidate):
        return None
    if _looks_like_address(candidate):
        return None
    if _PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN.search(candidate):
        return None
    if not re.search(r"[^\W\d_]", candidate, flags=re.UNICODE):
        return None
    return candidate


def _detail_parts(message_text: str) -> list[str]:
    if "/" in message_text:
        return [part.strip() for part in re.split(r"/+", message_text) if part.strip()]
    return _comma_parts(message_text)


def _comma_parts(message_text: str) -> list[str]:
    return [part.strip() for part in message_text.split(",") if part.strip()]


def _looks_like_person_name(value: str) -> bool:
    if len(value) > 60:
        return False
    if re.search(r"[.!?,;:]", value):
        return False
    lowered = value.lower()
    if any(char.isdigit() for char in value):
        return False
    blocked = {
        "address",
        "chairs",
        "company",
        "delivery",
        "desks",
        "need",
        "please",
        "recommend",
        "same",
        "tables",
        "what",
    }
    return not any(word in blocked for word in lowered.split())


def _clean_person_name(value: str) -> str | None:
    cleaned = _clean_value(value)
    cleaned = re.sub(r"\b(?:individual|company|customer)\b", "", cleaned).strip()
    if not cleaned or not _looks_like_person_name(cleaned):
        return None
    return cleaned


def _looks_like_address(value: str) -> bool:
    if not value or "?" in value:
        return False
    if is_question_clause(value, len(value)):
        return False
    lowered = value.lower()
    if EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
        return False
    if _GENERIC_SPACED_SKU_PATTERN.search(value):
        return False
    if _PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN.search(value):
        return False
    normalized = re.sub(r"[\W_]+", " ", lowered).strip()
    if normalized in {
        "abu dhabi",
        "ajman",
        "dubai",
        "emirates",
        "sharjah",
        "uae",
        "united arab emirates",
    }:
        return False
    return bool(
        re.search(r"\b\d+[A-Za-z]?\s+[A-Za-z]", value)
        or (_ADDRESS_TERM_PATTERN.search(value) and re.search(r"\d", value))
        or _ADDRESS_DISTRICT_PATTERN.search(value)
    )


def is_specific_delivery_address(address: str | None) -> bool:
    """Return whether an address is more specific than a city or country."""

    value = address.strip() if isinstance(address, str) else ""
    if not value:
        return False
    if "?" in value or not re.search(r"[^\W\d_]", value):
        return False
    normalized = re.sub(r"[\W_]+", " ", value.casefold()).strip()
    generic_addresses = {
        "uae",
        "u a e",
        "united arab emirates",
        "emirates",
        "dubai",
        "abu dhabi",
        "sharjah",
        "ajman",
        "ras al khaimah",
        "fujairah",
        "umm al quwain",
    }
    if normalized in generic_addresses:
        return False
    tokens = [token for token in normalized.split() if token]
    return len(tokens) >= 2 or bool(re.search(r"\d", value))


def _clean_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n:;-")
    return cleaned.rstrip(".")


def _strip_synthetic_test_markers(text: str) -> str:
    return _SYNTHETIC_TEST_MARKER_PATTERN.sub(" ", text).strip()


def _budget_value(match: re.Match[str]) -> dict[str, Any]:
    amount_text = match.group("amount")
    normalized_amount = canonical_amount(amount_text)
    assert normalized_amount is not None
    amount = float(normalized_amount) if "." in amount_text else int(normalized_amount)
    qualifier = match.groupdict().get("q1") or match.groupdict().get("q2")
    if qualifier:
        qualifier = re.sub(r"\s+", " ", qualifier.lower())
    currency = match.groupdict().get("currency1") or match.groupdict().get("currency2")
    normalized_currency = _normalize_currency(currency)
    return {
        "amount": amount,
        "currency": normalized_currency,
        "qualifier": qualifier or "budget",
    }


def _normalize_currency(value: str | None) -> str | None:
    if value is None:
        return None
    lowered = value.lower()
    if lowered in {"dhs", "dirham", "dirhams"}:
        return "AED"
    return value.upper()


def _first_pattern_match(
    patterns: Iterable[re.Pattern[str]],
    message_text: str,
) -> re.Match[str] | None:
    for pattern in patterns:
        match = pattern.search(message_text)
        if match:
            return match
    return None


def _should_call_default_fast_model(
    message_text: str,
    deterministic_facts: list[ExtractedCustomerFact],
) -> bool:
    if not message_text.strip():
        return False
    if not deterministic_facts:
        return True
    lowered = message_text.lower()
    ambiguous_markers = (" from ", "same as", "last time", "before", "budget")
    return any(marker in lowered for marker in ambiguous_markers)


def _normalize_fast_facts(
    facts: list[ExtractedCustomerFact],
    *,
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    normalized: list[ExtractedCustomerFact] = []
    for fact in facts:
        raw_key = fact.key.strip()
        alias = _FAST_FACT_KEY_ALIASES.get(raw_key.casefold())
        key = alias[1] if alias else raw_key
        scope = alias[0] if alias else _CANONICAL_FACT_SCOPES.get(key, fact.scope)
        if scope == "current_order" and key in {"order.item", "order.items"}:
            continue

        value = fact.value
        evidence = _bound_text(fact.evidence) or key
        if key == "delivery.address":
            grounded_address = extract_delivery_address(message_text)
            if grounded_address is None:
                if not isinstance(value, str) or not _source_contains_value(
                    message_text,
                    value,
                ):
                    continue
                grounded_address = value
            if not _looks_like_address(grounded_address):
                continue
            value = _clean_value(grounded_address)
            evidence = _bound_text(grounded_address) or key
        elif alias and key in {"customer.name", "customer.email"}:
            if not isinstance(value, str) or not _source_contains_value(
                message_text,
                value,
            ):
                continue

        normalized.append(
            ExtractedCustomerFact(
                scope=scope,
                key=key,
                value=value,
                confidence=fact.confidence,
                source="fast_model",
                evidence=evidence,
                source_message_id=fact.source_message_id or source_message_id,
                needs_confirmation=fact.needs_confirmation,
                conflicts_with=fact.conflicts_with,
            )
        )
    return normalized


def _source_contains_value(source: str, value: str) -> bool:
    normalized_source = re.sub(r"\s+", " ", source).casefold()
    normalized_value = re.sub(r"\s+", " ", value).strip().casefold()
    return bool(normalized_value and normalized_value in normalized_source)


def _sanitize_fact_for_fast_model(fact: ExtractedCustomerFact) -> ExtractedCustomerFact:
    if fact.key == "delivery.address":
        return fact.model_copy(
            update={
                "value": "[REDACTED_ADDRESS]",
                "evidence": "[REDACTED_ADDRESS]",
            }
        )
    return fact.model_copy(
        update={
            "value": _redact_fast_model_value(fact.value),
            "evidence": _redact_fast_model_text(fact.evidence),
        }
    )


def _redact_fast_model_value(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_fast_model_text(value)
    if isinstance(value, list):
        return [_redact_fast_model_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_fast_model_value(item) for key, item in value.items()}
    return value


def _redact_fast_model_text(text: str) -> str:
    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)

    def redact_phone(match: re.Match[str]) -> str:
        if is_customer_phone_detail(redacted, match):
            return "[REDACTED_PHONE]"
        return match.group(0)

    redacted = PHONE_PATTERN.sub(redact_phone, redacted)

    address = extract_delivery_address(redacted)
    if address:
        redacted = redacted.replace(address, "[REDACTED_ADDRESS]", 1)
    return redacted


def _dedupe_facts(
    facts: Iterable[ExtractedCustomerFact],
) -> list[ExtractedCustomerFact]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[ExtractedCustomerFact] = []
    for fact in facts:
        marker = (fact.scope, fact.key, _json_identity(fact.value))
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(fact)
    return deduped


def _json_identity(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _bounded_failure(exc: Exception) -> str:
    return _bound_text(f"{exc.__class__.__name__}: {exc}") or exc.__class__.__name__


def _bound_text(value: str | None, *, limit: int = MAX_EVIDENCE_CHARS) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _build_fast_model_prompt(request: FastCustomerFactExtractionRequest) -> str:
    deterministic = [
        fact.model_dump(mode="json") for fact in request.deterministic_facts
    ]
    payload = {
        "message_text": request.message_text,
        "source_message_id": request.source_message_id,
        "expected_labels": request.expected_labels,
        "deterministic_facts": deterministic,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
