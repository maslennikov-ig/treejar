"""Pure customer fact extraction boundary for the memory layer."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable, Iterable
from typing import TYPE_CHECKING, Any, Literal, cast

from pydantic import BaseModel, Field

from src.core.config import settings
from src.llm.pii import EMAIL_PATTERN, PHONE_PATTERN

if TYPE_CHECKING:
    from pydantic_ai.settings import ModelSettings

CustomerFactScope = Literal[
    "persistent_profile",
    "current_order",
    "past_order_reference",
]
CustomerFactConfidence = Literal["high", "medium", "low"]
CustomerFactSource = Literal["deterministic", "fast_model"]

MAX_EVIDENCE_CHARS = 160
FAST_MODEL_MAX_TOKENS = 700
FAST_MODEL_TIMEOUT_SECONDS = 30.0
FAST_MODEL_OUTPUT_TOKEN_LIMIT = 700
FAST_MODEL_TOTAL_TOKEN_LIMIT = 3000

_COMPANY_PATTERN = re.compile(
    r"\b(?:company\s+name|company|account|organization|organisation)"
    r"\s*(?:is|:|-)?\s*(?P<value>[^,.;\n]+)",
    re.IGNORECASE,
)
_LABELED_NAME_PATTERN = re.compile(
    r"\b(?:my\s+name\s+is|name\s*(?:is|:|-))\s*"
    r"(?P<value>[A-Za-z][A-Za-z .'-]{1,60})",
    re.IGNORECASE,
)
_FROM_NAME_PATTERN = re.compile(
    r"^\s*(?P<value>[A-Za-z][A-Za-z .'-]{1,60})\s+from\s+",
    re.IGNORECASE,
)
_ADDRESS_PATTERN = re.compile(
    r"\b(?:delivery\s+address|address|deliver\s+to|ship\s+to)"
    r"\s*(?:is|:|-)?\s*(?P<value>[^,.;\n]+)",
    re.IGNORECASE,
)
_SKU_ITEM_PATTERN = re.compile(
    r"\b(?P<quantity>\d+)\s*(?:x|pcs?|pieces?|units?)?\s+"
    r"(?P<sku>[A-Z]{2,}\s*[- ]?\s*\d{2,}(?:\s+[A-Z0-9-]+)?)\b"
)
_PLAIN_QUANTITY_PATTERN = re.compile(
    r"\b(?P<quantity>\d+)\s+"
    r"(?P<description>chairs?|desks?|tables?|workstations?|pods?|items?)\b",
    re.IGNORECASE,
)
_GENERIC_SPACED_SKU_PATTERN = re.compile(r"\b[A-Z]{1,4}\s*[- ]\s*\d{2,8}\b")
_SKU_NUMERIC_PREFIX_STOPWORDS = frozenset(
    {
        "and",
        "buy",
        "for",
        "from",
        "have",
        "like",
        "need",
        "take",
        "want",
        "with",
    }
)
_BUDGET_PATTERN = re.compile(
    r"\b(?:budget\s*(?P<q1>under|below|up\s+to|around|about|approx(?:imately)?)?"
    r"|(?P<q2>under|below|up\s+to|around|about|approx(?:imately)?))"
    r"\s*(?P<currency1>AED|DHS|dirhams?)?\s*"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<currency2>AED|DHS|dirhams?)?\b",
    re.IGNORECASE,
)
_REVERSE_BUDGET_PATTERN = re.compile(
    r"\b(?P<currency1>AED|DHS|dirhams?)?\s*"
    r"(?P<amount>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<currency2>AED|DHS|dirhams?)?\s+budget\b",
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
_PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN = re.compile(
    r"\b(?:need|needs|want|wants|would\s+like|looking\s+for|quote|quotation|"
    r"chair|chairs|desk|desks|table|tables|workstation|workstations|sku|"
    r"assembly|installation)\b",
    re.IGNORECASE,
)
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
- persistent_profile: stable customer name, email, phone, company, language.
- current_order: current quote/order facts, selected items, delivery address,
  delivery/assembly/color/budget preferences, quote status.
- past_order_reference: questions or requests about previous orders.

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
        from pydantic_ai import Agent, UsageLimits
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openrouter import OpenRouterProvider

        model_settings = cast(
            "ModelSettings",
            {
                "max_tokens": FAST_MODEL_MAX_TOKENS,
                "timeout": FAST_MODEL_TIMEOUT_SECONDS,
            },
        )
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
            usage_limits=UsageLimits(
                request_limit=1,
                output_tokens_limit=FAST_MODEL_OUTPUT_TOKEN_LIMIT,
                total_tokens_limit=FAST_MODEL_TOTAL_TOKEN_LIMIT,
            ),
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
        message_text=message_text,
        source_message_id=source_message_id,
        deterministic_facts=facts,
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


def _extract_name_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    for match in _LABELED_NAME_PATTERN.finditer(message_text):
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
        if company:
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
    facts: list[ExtractedCustomerFact] = []
    for match in _ADDRESS_PATTERN.finditer(message_text):
        address = _clean_value(match.group("value"))
        if address:
            facts.append(
                _fact(
                    scope="current_order",
                    key="delivery.address",
                    value=address,
                    confidence="high",
                    evidence=match.group(0),
                    source_message_id=source_message_id,
                )
            )

    compact_address = _compact_address_candidate(message_text)
    if compact_address:
        facts.append(
            _fact(
                scope="current_order",
                key="delivery.address",
                value=compact_address,
                confidence="medium",
                evidence=compact_address,
                source_message_id=source_message_id,
            )
        )

    return facts


def _extract_order_item_facts(
    message_text: str,
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    facts: list[ExtractedCustomerFact] = []
    for match in _SKU_ITEM_PATTERN.finditer(message_text):
        facts.append(
            _fact(
                scope="current_order",
                key="order.item",
                value={
                    "sku": _normalize_sku(match.group("sku")),
                    "quantity": int(match.group("quantity")),
                },
                confidence="high",
                evidence=match.group(0),
                source_message_id=source_message_id,
            )
        )

    for match in _PLAIN_QUANTITY_PATTERN.finditer(message_text):
        if _plain_quantity_is_sku_numeric_component(message_text, match):
            continue
        facts.append(
            _fact(
                scope="current_order",
                key="order.item",
                value={
                    "description": match.group("description").lower(),
                    "quantity": int(match.group("quantity")),
                },
                confidence="medium",
                evidence=match.group(0),
                source_message_id=source_message_id,
            )
        )

    return facts


def _plain_quantity_is_sku_numeric_component(
    message_text: str,
    match: re.Match[str],
) -> bool:
    prefix = message_text[max(0, match.start() - 12) : match.start()]
    prefix_match = re.search(
        r"(?<![A-Z])(?P<prefix>[A-Z]{1,4})\s*[- ]\s*$",
        prefix,
        flags=re.IGNORECASE,
    )
    if prefix_match is None:
        return False
    if prefix_match.group("prefix").casefold() in _SKU_NUMERIC_PREFIX_STOPWORDS:
        return False

    window = message_text[
        max(0, match.start() - 12) : min(len(message_text), match.end() + 12)
    ]
    return _GENERIC_SPACED_SKU_PATTERN.search(window) is not None


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
    parts = _comma_parts(message_text)
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
        or _looks_like_address(" ".join(parts[1:]))
    ):
        return first
    return None


def _compact_name_part_candidate(value: str) -> str | None:
    candidates = [segment.strip() for segment in re.split(r"[.!?]", value)]
    candidates.append(value.strip())
    for candidate in reversed(candidates):
        if _ASSISTANT_GREETING_PATTERN.fullmatch(candidate):
            continue
        if _LABELED_NAME_PATTERN.search(candidate):
            continue
        name = _clean_person_name(candidate)
        if name and _looks_like_person_name(name):
            return name
    return None


def _compact_address_candidate(message_text: str) -> str | None:
    if _ADDRESS_PATTERN.search(message_text):
        return None
    for part in _comma_parts(message_text):
        candidate = _clean_value(part)
        if _looks_like_address(candidate):
            return candidate
    return None


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
    lowered = value.lower()
    if EMAIL_PATTERN.search(value) or PHONE_PATTERN.search(value):
        return False
    if _GENERIC_SPACED_SKU_PATTERN.search(value):
        return False
    if _PRODUCT_OR_REQUEST_ADDRESS_BLOCKER_PATTERN.search(value):
        return False
    normalized = re.sub(r"[\W_]+", " ", lowered).strip()
    if normalized in {"dubai", "uae", "united arab emirates"}:
        return False
    return bool(
        re.search(r"\b\d+[A-Za-z]?\s+[A-Za-z]", value)
        or "dubai marina" in lowered
        or "business bay" in lowered
    )


def _clean_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" \t\r\n:;-")
    return cleaned.rstrip(".")


def _normalize_sku(value: str) -> str:
    return re.sub(r"[\s-]+", " ", value).strip().upper()


def _budget_value(match: re.Match[str]) -> dict[str, Any]:
    amount_text = match.group("amount").replace(",", "")
    amount = float(amount_text) if "." in amount_text else int(amount_text)
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
    source_message_id: str | None,
) -> list[ExtractedCustomerFact]:
    normalized: list[ExtractedCustomerFact] = []
    for fact in facts:
        normalized.append(
            ExtractedCustomerFact(
                scope=fact.scope,
                key=fact.key,
                value=fact.value,
                confidence=fact.confidence,
                source="fast_model",
                evidence=_bound_text(fact.evidence) or fact.key,
                source_message_id=fact.source_message_id or source_message_id,
                needs_confirmation=fact.needs_confirmation,
                conflicts_with=fact.conflicts_with,
            )
        )
    return normalized


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
