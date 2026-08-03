"""Fixed synthetic cases for Noor's two-route OpenRouter model battle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class SalesCase:
    case_id: str
    category: str
    system_prompt: str
    user_prompt: str
    tools: tuple[dict[str, Any], ...] = ()
    tool_results: dict[str, Any] = field(default_factory=dict)
    expected_tools: tuple[str, ...] = ()
    expected_tool_arguments: dict[str, dict[str, Any]] = field(default_factory=dict)
    required_phrases: tuple[str, ...] = ()
    critical_required_phrases: tuple[str, ...] = ()
    forbidden_phrases: tuple[str, ...] = ()
    expected_language: str | None = None
    conversation: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class SystemCase:
    case_id: str
    category: str
    system_prompt: str
    user_prompt: str
    schema: dict[str, Any]
    expected_fields: dict[str, Any]
    tools: tuple[dict[str, Any], ...] = ()
    expected_tool: str = ""
    critical_fields: tuple[str, ...] = ()


def _tool(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }


CATALOG_SEARCH_TOOL = _tool(
    "search_catalog",
    "Search the fixed Treejar product catalog evidence.",
    {
        "query": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 2},
    },
    ["query", "limit"],
)
COMPLETE_CATALOG_SEARCH_TOOL = _tool(
    "search_catalog",
    "Search fixed catalog evidence for a complete multi-family solution.",
    {
        "query": {"type": "string"},
        "limit": {"type": "integer", "minimum": 1, "maximum": 6},
    },
    ["query", "limit"],
)
STOCK_TOOL = _tool(
    "check_stock",
    "Check current synthetic inventory stock for one SKU.",
    {"sku": {"type": "string"}},
    ["sku"],
)
INVENTORY_RATE_TOOL = _tool(
    "get_inventory_rate",
    "Get the authoritative operational sales rate for one SKU.",
    {"sku": {"type": "string"}},
    ["sku"],
)
ESCALATE_TOOL = _tool(
    "escalate_to_manager",
    "Escalate a request that needs a human commercial decision.",
    {
        "reason_code": {
            "type": "string",
            "enum": ["discount_approval", "custom_project"],
        },
        "summary": {"type": "string"},
    },
    ["reason_code", "summary"],
)
QUOTE_DRAFT_TOOL = _tool(
    "prepare_quote_draft",
    "Prepare a non-binding quote draft for manager review; it does not send or create an order.",
    {
        "sku": {"type": "string"},
        "quantity": {"type": "integer", "minimum": 1},
        "customer_company": {"type": "string"},
    },
    ["sku", "quantity", "customer_company"],
)

_SALES_BASE = """\
You are Noor, Treejar's UAE office-furniture sales assistant. Reply in the
customer's language and use only facts in this case or returned by tools.
Never invent price, stock, discount, delivery, payment, warranty, or product
claims. Catalog evidence is descriptive; an operational inventory rate is
authoritative for quotations. Do not say an order or quotation was created
unless a tool explicitly confirms it. Be concise, helpful, and end with a
concrete low-pressure next step. Use at most two product options.
"""


SALES_CASES: tuple[SalesCase, ...] = (
    SalesCase(
        case_id="sales-01",
        category="faq_guidance",
        system_prompt=_SALES_BASE
        + """
Evidence: The Axis ergonomic chair has a 5-year manufacturer warranty.
Treejar can arrange a product specialist callback, but no callback time is
guaranteed in this case.
""",
        user_prompt="Hi, what warranty comes with the Axis chair?",
        required_phrases=("Axis", "5-year", "Treejar"),
        forbidden_phrases=("lifetime warranty", "callback today"),
    ),
    SalesCase(
        case_id="sales-02",
        category="product_recommendation",
        system_prompt=_SALES_BASE
        + """
The customer explicitly requested a catalog lookup. Call search_catalog once
with query exactly "ergonomic chair" and limit 2, then recommend from its
result only.
""",
        user_prompt=(
            "Please search for an ergonomic chair for long workdays. "
            "Use no more than two options."
        ),
        tools=(CATALOG_SEARCH_TOOL,),
        tool_results={
            "search_catalog": {
                "products": [
                    {
                        "name": "Axis Ergo",
                        "sku": "AX-E1",
                        "catalog_price_aed": 1450,
                        "features": ["adjustable lumbar", "mesh back"],
                    },
                    {
                        "name": "Nova Task",
                        "sku": "NV-T2",
                        "catalog_price_aed": 980,
                        "features": ["seat-depth adjustment", "fabric back"],
                    },
                ]
            }
        },
        expected_tools=("search_catalog",),
        expected_tool_arguments={
            "search_catalog": {"query": "ergonomic chair", "limit": 2}
        },
        required_phrases=("Axis Ergo", "Nova Task", "1450", "980"),
        forbidden_phrases=("stock is confirmed", "delivery is free"),
    ),
    SalesCase(
        case_id="sales-03",
        category="product_comparison",
        system_prompt=_SALES_BASE
        + """
Evidence:
- Axis Ergo (AX-E1): adjustable lumbar, mesh back, catalog price AED 1450.
- Nova Task (NV-T2): seat-depth adjustment, fabric back, catalog price AED 980.
No stock or delivery evidence is available.
""",
        user_prompt="Compare Axis Ergo and Nova Task for me in a short answer.",
        required_phrases=("Axis Ergo", "Nova Task", "1450", "980"),
        forbidden_phrases=("stock is confirmed", "delivery is tomorrow"),
    ),
    SalesCase(
        case_id="sales-04",
        category="current_stock",
        system_prompt=_SALES_BASE
        + """
Current stock must be checked. Call check_stock once with SKU "AX-E1".
""",
        user_prompt="Do you have AX-E1 in stock right now?",
        tools=(STOCK_TOOL,),
        tool_results={
            "check_stock": {
                "sku": "AX-E1",
                "available_quantity": 7,
                "warehouse": "Dubai",
                "as_of": "2026-07-27T10:00:00Z",
            }
        },
        expected_tools=("check_stock",),
        expected_tool_arguments={"check_stock": {"sku": "AX-E1"}},
        required_phrases=("AX-E1", "7", "Dubai"),
        forbidden_phrases=("8 units", "guaranteed tomorrow"),
    ),
    SalesCase(
        case_id="sales-05",
        category="quote_boundary",
        system_prompt=_SALES_BASE
        + """
The customer supplied enough information for a non-binding draft. Call
prepare_quote_draft exactly once with SKU "NV-T2", quantity 12, and customer
company "Orbit Labs". Explain that manager review is still required.
""",
        user_prompt=("Orbit Labs needs 12 of NV-T2. Please prepare the quote draft."),
        tools=(QUOTE_DRAFT_TOOL,),
        tool_results={
            "prepare_quote_draft": {
                "draft_id": "SYNTH-DRAFT-12",
                "status": "pending_manager_review",
                "order_created": False,
            }
        },
        expected_tools=("prepare_quote_draft",),
        expected_tool_arguments={
            "prepare_quote_draft": {
                "sku": "NV-T2",
                "quantity": 12,
                "customer_company": "Orbit Labs",
            }
        },
        required_phrases=("SYNTH-DRAFT-12", "manager review"),
        forbidden_phrases=("order confirmed", "quotation sent"),
    ),
    SalesCase(
        case_id="sales-06",
        category="discount_escalation",
        system_prompt=_SALES_BASE
        + """
No discount is pre-approved. Call escalate_to_manager once using reason_code
"discount_approval" and summary exactly "Customer requests 15% discount for
30 Axis Ergo chairs".
""",
        user_prompt="Can you approve 15% off 30 Axis Ergo chairs now?",
        tools=(ESCALATE_TOOL,),
        tool_results={
            "escalate_to_manager": {
                "accepted": True,
                "reference": "SYNTH-ESC-15",
                "decision": "pending",
            }
        },
        expected_tools=("escalate_to_manager",),
        expected_tool_arguments={
            "escalate_to_manager": {
                "reason_code": "discount_approval",
                "summary": "Customer requests 15% discount for 30 Axis Ergo chairs",
            }
        },
        required_phrases=("15%", "SYNTH-ESC-15", "pending"),
        forbidden_phrases=("discount is approved", "discount is confirmed"),
    ),
    SalesCase(
        case_id="sales-07",
        category="arabic_response",
        system_prompt=_SALES_BASE
        + """
Reply only in Arabic. Evidence: Nova Task costs AED 980 in the catalog. Stock
and delivery are unknown.
""",
        user_prompt="كم سعر كرسي Nova Task؟ أجب بالعربية.",
        required_phrases=("Nova Task", "980", "درهم"),
        forbidden_phrases=("المخزون مؤكد", "التوصيل مجاني"),
        expected_language="ar",
    ),
    SalesCase(
        case_id="sales-08",
        category="weak_catalog_match",
        system_prompt=_SALES_BASE
        + """
Call search_catalog exactly once with query "soundproof pod 120x120" and limit
2. If there is no result, say so and ask one useful clarification. Do not
substitute a product.
""",
        user_prompt="I need a soundproof pod exactly 120x120 cm. What do you have?",
        tools=(CATALOG_SEARCH_TOOL,),
        tool_results={"search_catalog": {"products": []}},
        expected_tools=("search_catalog",),
        expected_tool_arguments={
            "search_catalog": {"query": "soundproof pod 120x120", "limit": 2}
        },
        required_phrases=("120x120",),
        forbidden_phrases=("perfect match is available",),
    ),
    SalesCase(
        case_id="sales-09",
        category="option_cap",
        system_prompt=_SALES_BASE
        + """
Evidence:
- Axis Ergo, AED 1450, adjustable lumbar.
- Nova Task, AED 980, seat-depth adjustment.
- Pico Basic, AED 620, fixed lumbar.
The user explicitly wants exactly two options. Choose the first two evidence
items and do not mention Pico Basic.
""",
        user_prompt="Give me exactly two chair options for a 10-person office.",
        required_phrases=("Axis Ergo", "Nova Task"),
        forbidden_phrases=("Pico Basic", "stock is confirmed"),
    ),
    SalesCase(
        case_id="sales-10",
        category="authoritative_rate",
        system_prompt=_SALES_BASE
        + """
The catalog displays AED 1200 for SKU DK-4, but a quote requires the current
operational rate. Call get_inventory_rate exactly once with SKU "DK-4" and use
the returned rate as authoritative.
""",
        user_prompt="What price should go on a quote for one DK-4 desk?",
        tools=(INVENTORY_RATE_TOOL,),
        tool_results={
            "get_inventory_rate": {
                "sku": "DK-4",
                "currency": "AED",
                "rate": 1300,
                "source": "synthetic_inventory",
            }
        },
        expected_tools=("get_inventory_rate",),
        expected_tool_arguments={"get_inventory_rate": {"sku": "DK-4"}},
        required_phrases=("DK-4", "1300", "AED"),
        forbidden_phrases=("AED 1200", "order created"),
    ),
    SalesCase(
        case_id="sales-11",
        category="missing_stock",
        system_prompt=_SALES_BASE
        + """
Call check_stock exactly once with SKU "PX-9". A null quantity means current
stock is unconfirmed, not zero and not available.
""",
        user_prompt="Can you guarantee 20 units of PX-9 are available?",
        tools=(STOCK_TOOL,),
        tool_results={
            "check_stock": {
                "sku": "PX-9",
                "available_quantity": None,
                "status": "unconfirmed",
            }
        },
        expected_tools=("check_stock",),
        expected_tool_arguments={"check_stock": {"sku": "PX-9"}},
        required_phrases=("PX-9", "unconfirmed"),
        forbidden_phrases=("20 units are available", "we guarantee 20"),
    ),
    SalesCase(
        case_id="sales-12",
        category="next_step",
        system_prompt=_SALES_BASE
        + """
Evidence: Axis Ergo has adjustable lumbar and mesh back. No price, stock,
delivery, or discount evidence is available. The customer has not stated
quantity or preferred color.
        """,
        user_prompt="The Axis sounds suitable. What do you need from me next?",
        required_phrases=("quantity", "color"),
        forbidden_phrases=("stock is confirmed",),
    ),
)


CORE_HARD_CASES: tuple[SalesCase, ...] = (
    SalesCase(
        case_id="S01",
        category="catalog_coverage",
        system_prompt=_SALES_BASE
        + """
The customer needs a coherent twenty-person open-office package covering task
chairs, shared desks, and storage within AED 30,000. Call search_catalog once
with query exactly "twenty-person open office chairs desks storage" and limit
6. Recommend a complete set from the synthetic catalog facts, explain the
coverage and total, and ask one useful product question. Do not replace the
recommendation with a bare fact dump.
""",
        conversation=(
            {
                "role": "user",
                "content": "We are furnishing a twenty-person open office.",
            },
            {
                "role": "assistant",
                "content": "Which furniture families and budget should I cover?",
            },
        ),
        user_prompt="Task chairs, shared desks, and storage; AED 30,000 total.",
        tools=(COMPLETE_CATALOG_SEARCH_TOOL,),
        tool_results={
            "search_catalog": {
                "products": [
                    {
                        "sku": "AX-E1",
                        "family": "task chair",
                        "price_aed": 800,
                        "quantity": 20,
                    },
                    {
                        "sku": "DK-4",
                        "family": "shared desk",
                        "price_aed": 4000,
                        "quantity": 2,
                    },
                    {
                        "sku": "ST-2",
                        "family": "storage",
                        "price_aed": 1500,
                        "quantity": 2,
                    },
                ],
                "total_aed": 27000,
            }
        },
        expected_tools=("search_catalog",),
        expected_tool_arguments={
            "search_catalog": {
                "query": "twenty-person open office chairs desks storage",
                "limit": 6,
            }
        },
        required_phrases=("AX-E1", "DK-4", "ST-2", "27,000", "coverage"),
        critical_required_phrases=("AX-E1", "DK-4", "ST-2"),
        forbidden_phrases=("chair only", "over budget", "quotation created"),
        expected_language="en",
    ),
    SalesCase(
        case_id="S02",
        category="arabic_configuration",
        system_prompt=_SALES_BASE
        + """
Reply only in Arabic. The fixed evidence contains a meeting-room set: twelve
NV-T2 chairs at AED 500 each and one MT-12 table at AED 6,000, total AED
12,000. The budget is AED 15,000. Cover both families. Call search_catalog once
with query exactly "Arabic meeting room for twelve" and limit 4.
""",
        conversation=(
            {"role": "user", "content": "أحتاج أثاث غرفة اجتماعات لاثني عشر شخصاً."},
            {"role": "assistant", "content": "ما الميزانية الإجمالية؟"},
        ),
        user_prompt="الميزانية 15,000 درهم، وأجب بالعربية.",
        tools=(COMPLETE_CATALOG_SEARCH_TOOL,),
        tool_results={
            "search_catalog": {
                "products": [
                    {"sku": "NV-T2", "family": "chair", "price_aed": 500},
                    {"sku": "MT-12", "family": "table", "price_aed": 6000},
                ],
                "total_aed": 12000,
            }
        },
        expected_tools=("search_catalog",),
        expected_tool_arguments={
            "search_catalog": {"query": "Arabic meeting room for twelve", "limit": 4}
        },
        required_phrases=("NV-T2", "MT-12", "12,000", "درهم"),
        critical_required_phrases=("NV-T2", "MT-12"),
        forbidden_phrases=("over budget", "English only"),
        expected_language="ar",
    ),
    SalesCase(
        case_id="S03",
        category="stock_conflict",
        system_prompt=_SALES_BASE
        + """
Catalog copy contains a stale quantity of 22 for AX-E1. The only authoritative
current snapshot is the check_stock result. Call check_stock once for AX-E1,
state one current stock number, its warehouse and timestamp, and do not repeat
the stale catalog quantity.
""",
        conversation=(
            {"role": "user", "content": "The catalog page says 22 AX-E1 chairs."},
            {"role": "assistant", "content": "I will check the current snapshot."},
        ),
        user_prompt="What is the verified stock now?",
        tools=(STOCK_TOOL,),
        tool_results={
            "check_stock": {
                "sku": "AX-E1",
                "available_quantity": 7,
                "warehouse": "Dubai",
                "as_of": "2026-08-03T10:00:00Z",
            }
        },
        expected_tools=("check_stock",),
        expected_tool_arguments={"check_stock": {"sku": "AX-E1"}},
        required_phrases=("AX-E1", "7", "Dubai", "verified"),
        critical_required_phrases=("AX-E1", "7"),
        forbidden_phrases=("22 chairs", "catalog stock"),
        expected_language="en",
    ),
    SalesCase(
        case_id="S04",
        category="quote_consent_gate",
        system_prompt=_SALES_BASE
        + """
The customer is comparing AX-E1 after receiving verified catalog facts, but
has explicitly refused a quotation. Use the facts to give a concise model-owned
recommendation and answer the comparison question. Do not prepare a quote,
collect customer details, or replace the answer with a bare list of facts.
""",
        conversation=(
            {"role": "user", "content": "AX-E1 looks suitable. Would you quote it?"},
            {"role": "assistant", "content": "I can prepare a quotation if you want."},
        ),
        user_prompt="No quotation. Just explain why AX-E1 fits long workdays.",
        tools=(QUOTE_DRAFT_TOOL,),
        tool_results={
            "prepare_quote_draft": {"status": "forbidden_without_explicit_consent"}
        },
        required_phrases=("AX-E1", "long workdays", "next"),
        critical_required_phrases=("AX-E1",),
        forbidden_phrases=(
            "quotation is on hold",
            "company name",
            "phone",
            "email",
            "address",
        ),
        expected_language="en",
    ),
    SalesCase(
        case_id="S05",
        category="twelve_seat_configuration",
        system_prompt=_SALES_BASE
        + """
The customer needs a complete twelve-seat workstation configuration within AED
20,000. The fixed evidence contains twelve AX-E1 chairs at AED 1,000 each and
three DK-4 four-person desks at AED 2,000 each, total AED 18,000. Call
search_catalog once with query exactly "twelve-seat workstation configuration"
and limit 4. Cover all twelve seats and both furniture families.
""",
        conversation=(
            {"role": "user", "content": "We need workstations for twelve people."},
            {"role": "assistant", "content": "What is the total budget?"},
        ),
        user_prompt="AED 20,000 for the complete twelve-seat setup.",
        tools=(COMPLETE_CATALOG_SEARCH_TOOL,),
        tool_results={
            "search_catalog": {
                "products": [
                    {
                        "sku": "AX-E1",
                        "family": "chair",
                        "quantity": 12,
                        "unit_price_aed": 1000,
                    },
                    {
                        "sku": "DK-4",
                        "family": "four-person desk",
                        "quantity": 3,
                        "unit_price_aed": 2000,
                    },
                ],
                "covered_seats": 12,
                "total_aed": 18000,
            }
        },
        expected_tools=("search_catalog",),
        expected_tool_arguments={
            "search_catalog": {
                "query": "twelve-seat workstation configuration",
                "limit": 4,
            }
        },
        required_phrases=("AX-E1", "DK-4", "12", "18,000", "within budget"),
        critical_required_phrases=("AX-E1", "DK-4", "12"),
        forbidden_phrases=("partial", "over budget", "chair only"),
        expected_language="en",
    ),
    SalesCase(
        case_id="S08",
        category="requirement_correction",
        system_prompt=_SALES_BASE
        + """
The latest request corrects the quantity from 20 to 12 and defers a quotation.
Use quantity 12, keep SKU AX-E1, and ask only one product-relevant next question.
""",
        conversation=(
            {"role": "user", "content": "We may need 20 AX-E1 chairs."},
            {"role": "assistant", "content": "Shall I prepare a quotation for 20?"},
        ),
        user_prompt="Make that 12. Do not prepare a quotation yet.",
        required_phrases=("12", "AX-E1", "next"),
        critical_required_phrases=("12", "AX-E1"),
        forbidden_phrases=("20 chairs", "company name", "address"),
        expected_language="en",
    ),
)


def _strict_object(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_FACT_SCHEMA = _strict_object(
    {
        "language": {"type": "string", "enum": ["en", "ar"]},
        "facts": {
            "type": "array",
            "items": _strict_object(
                {
                    "key": {"type": "string"},
                    "value": {"type": ["string", "integer", "null"]},
                    "scope": {
                        "type": "string",
                        "enum": [
                            "persistent_profile",
                            "current_order",
                            "past_order_reference",
                        ],
                    },
                    "needs_confirmation": {"type": "boolean"},
                }
            ),
        },
    }
)
_RED_FLAG_SCHEMA = _strict_object(
    {
        "flags": {
            "type": "array",
            "items": _strict_object(
                {
                    "code": {
                        "type": "string",
                        "enum": [
                            "missing_identity",
                            "hard_deflection",
                            "unverified_commitment",
                            "ignored_question",
                            "bad_tone",
                        ],
                    },
                    "evidence": {"type": "string"},
                }
            ),
        },
        "recommended_action": {"type": "string"},
    }
)
_FAQ_SCHEMA = _strict_object(
    {
        "customer_message": {"type": "string"},
        "kb_candidate": {
            "type": ["object", "null"],
            "properties": {
                "question": {"type": "string"},
                "answer": {"type": "string"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "language": {"type": "string"},
            },
            "required": ["question", "answer", "confidence", "language"],
            "additionalProperties": False,
        },
    }
)
_SUMMARY_SCHEMA = _strict_object(
    {
        "customer": {"type": "string"},
        "stage": {
            "type": "string",
            "enum": ["qualifying", "solution", "quoting", "closing"],
        },
        "selected_sku": {"type": ["string", "null"]},
        "quantity": {"type": ["integer", "null"]},
        "next_action": {"type": "string"},
    }
)
_TRANSLATION_SCHEMA = _strict_object(
    {
        "language": {"type": "string", "enum": ["en", "ar"]},
        "translation": {"type": "string"},
        "preserved_numbers": {
            "type": "array",
            "items": {"type": "string"},
        },
    }
)

_SYSTEM_BASE = """\
Follow the task exactly. Use only the supplied synthetic text. Do not infer
missing facts. Return only the requested structured result.
"""


SYSTEM_CASES: tuple[SystemCase, ...] = (
    SystemCase(
        "system-fact-01",
        "fact_extraction",
        _SYSTEM_BASE
        + "Extract facts in mention order. Stable identity uses persistent_profile.",
        "Message: My name is Maya and I work at Orbit Labs. Please reply in English.",
        _FACT_SCHEMA,
        {
            "language": "en",
            "facts.$length": 2,
            "facts[0].key": "name",
            "facts[0].value": "Maya",
            "facts[0].scope": "persistent_profile",
            "facts[0].needs_confirmation": False,
            "facts[1].key": "company",
            "facts[1].value": "Orbit Labs",
        },
    ),
    SystemCase(
        "system-fact-02",
        "fact_extraction",
        _SYSTEM_BASE + "Extract facts in mention order.",
        "Message: أحتاج 12 كرسي NV-T2 باللون الأزرق.",
        _FACT_SCHEMA,
        {
            "language": "ar",
            "facts.$length": 3,
            "facts[0].key": "quantity",
            "facts[0].value": 12,
            "facts[0].scope": "current_order",
            "facts[0].needs_confirmation": False,
            "facts[1].key": "sku",
            "facts[1].value": "NV-T2",
            "facts[2].key": "color",
            "facts[2].value": "الأزرق",
        },
    ),
    SystemCase(
        "system-fact-03",
        "fact_extraction",
        _SYSTEM_BASE + "A request to reuse a previous-order detail needs confirmation.",
        "Message: Use the same delivery address as my previous order.",
        _FACT_SCHEMA,
        {
            "language": "en",
            "facts.$length": 1,
            "facts[0].key": "delivery_address",
            "facts[0].value": None,
            "facts[0].scope": "past_order_reference",
            "facts[0].needs_confirmation": True,
        },
    ),
    SystemCase(
        "system-fact-04",
        "fact_extraction",
        _SYSTEM_BASE + "Do not extract assumptions or questions as confirmed facts.",
        "Message: Is AED 8,000 enough? I have not chosen a quantity yet.",
        _FACT_SCHEMA,
        {
            "language": "en",
            "facts.$length": 1,
            "facts[0].key": "budget",
            "facts[0].value": {"$number": 8000},
            "facts[0].scope": "current_order",
            "facts[0].needs_confirmation": True,
        },
    ),
    SystemCase(
        "system-red-01",
        "red_flags",
        _SYSTEM_BASE
        + "Return only explicit critical flags. Exact evidence is the shortest supporting quote.",
        "Customer: Is it in stock?\nAssistant: Yes, 50 units are definitely available.\nEvidence supplied to assistant: none.",
        _RED_FLAG_SCHEMA,
        {
            "flags.$length": 1,
            "flags[0].code": "unverified_commitment",
            "flags[0].evidence": {
                "$contains_all": ["50", "definitely available"],
            },
        },
    ),
    SystemCase(
        "system-red-02",
        "red_flags",
        _SYSTEM_BASE + "Return no flags when no critical issue is explicit.",
        "Customer: I need six chairs.\nAssistant: I can help. Which style and budget range do you prefer?",
        _RED_FLAG_SCHEMA,
        {"flags.$length": 0},
    ),
    SystemCase(
        "system-red-03",
        "red_flags",
        _SYSTEM_BASE + "Exact evidence is the shortest supporting quote.",
        "Customer: What is the warranty?\nAssistant: Talk to a manager. I cannot help.",
        _RED_FLAG_SCHEMA,
        {
            "flags.$length": 1,
            "flags[0].code": "hard_deflection",
            "flags[0].evidence": {"$contains_all": ["Talk to a manager"]},
        },
    ),
    SystemCase(
        "system-red-04",
        "red_flags",
        _SYSTEM_BASE + "Exact evidence is the shortest supporting quote.",
        "Customer: Please explain delivery.\nAssistant: Stop asking and read the website.",
        _RED_FLAG_SCHEMA,
        {
            "flags.$length": 1,
            "flags[0].code": "bad_tone",
            "flags[0].evidence": {"$contains_all": ["Stop asking"]},
        },
    ),
    SystemCase(
        "system-faq-01",
        "faq_candidate",
        _SYSTEM_BASE
        + "Generalize reusable facts. Use confidence exactly 0.95 for explicit reusable policy.",
        "Question: What is the Axis warranty?\nManager draft: Axis chairs include a 5-year manufacturer warranty.\nCustomer language: en",
        _FAQ_SCHEMA,
        {
            "customer_message": {
                "$contains_all": ["Axis", "5-year", "warranty"],
            },
            "kb_candidate.question": {"$contains_all": ["Axis", "warranty"]},
            "kb_candidate.answer": {
                "$contains_all": ["Axis", "5-year", "warranty"],
            },
            "kb_candidate.confidence": 0.95,
            "kb_candidate.language": "en",
        },
    ),
    SystemCase(
        "system-faq-02",
        "faq_candidate",
        _SYSTEM_BASE + "Set kb_candidate to null for a one-off commercial promise.",
        "Question: Can I get a discount?\nManager draft: For this project only, Victor approved 12% until Friday.\nCustomer language: en",
        _FAQ_SCHEMA,
        {
            "customer_message": {
                "$contains_all": ["project", "Victor", "12%", "Friday"],
            },
            "kb_candidate": None,
        },
    ),
    SystemCase(
        "system-faq-03",
        "faq_candidate",
        _SYSTEM_BASE
        + "Translate the customer message to Arabic but keep the FAQ candidate in English. Use confidence exactly 0.9.",
        "Question: هل تقدمون خدمة التركيب؟\nManager draft: Assembly is available as an optional paid service.\nCustomer language: ar",
        _FAQ_SCHEMA,
        {
            "customer_message": {
                "$contains_all": ["التركيب", "اختيارية", "مدفوعة"],
            },
            "kb_candidate.answer": {
                "$contains_all": ["Assembly", "optional", "paid"],
            },
            "kb_candidate.confidence": 0.9,
            "kb_candidate.language": "en",
        },
    ),
    SystemCase(
        "system-faq-04",
        "faq_candidate",
        _SYSTEM_BASE + "Set kb_candidate to null when the draft is uncertain.",
        "Question: How long is delivery?\nManager draft: I think it may be around a week, but I need to check.\nCustomer language: en",
        _FAQ_SCHEMA,
        {
            "customer_message": {"$contains_all": ["week", "check"]},
            "kb_candidate": None,
        },
    ),
    SystemCase(
        "system-summary-01",
        "summary",
        _SYSTEM_BASE + "Use the latest explicit state.",
        "Maya from Orbit Labs selected AX-E1, quantity 20. Noor will prepare a draft quote next.",
        _SUMMARY_SCHEMA,
        {
            "customer": "Maya",
            "stage": "quoting",
            "selected_sku": "AX-E1",
            "quantity": 20,
            "next_action": {"$contains_all": ["prepare", "draft quote"]},
        },
    ),
    SystemCase(
        "system-summary-02",
        "summary",
        _SYSTEM_BASE + "Do not invent identity, SKU, or quantity.",
        "The customer wants ergonomic seating and is comparing mesh versus fabric. Ask for team size next.",
        _SUMMARY_SCHEMA,
        {
            "customer": "unknown",
            "stage": "qualifying",
            "selected_sku": None,
            "quantity": None,
            "next_action": {"$contains_all": ["ask", "team size"]},
        },
    ),
    SystemCase(
        "system-summary-03",
        "summary",
        _SYSTEM_BASE + "Use the latest explicit state.",
        "Ahmed considered NV-T2, then chose AX-E1 for 8 people. Next: confirm preferred color.",
        _SUMMARY_SCHEMA,
        {
            "customer": "Ahmed",
            "stage": "solution",
            "selected_sku": "AX-E1",
            "quantity": 8,
            "next_action": {"$contains_all": ["confirm", "color"]},
        },
        critical_fields=("language", "selected_sku", "quantity"),
    ),
    SystemCase(
        "system-summary-04",
        "summary",
        _SYSTEM_BASE + "Use the latest explicit state.",
        "Lina approved the draft for 4 DK-4 desks. The manager must send the final quotation.",
        _SUMMARY_SCHEMA,
        {
            "customer": "Lina",
            "stage": "closing",
            "selected_sku": "DK-4",
            "quantity": 4,
            "next_action": {"$contains_all": ["manager", "final quotation"]},
        },
    ),
    SystemCase(
        "system-translation-01",
        "translation",
        _SYSTEM_BASE
        + "Translate to Arabic exactly and list preserved numbers as strings.",
        "Translate: The price is AED 1,450 and the warranty is 5 years.",
        _TRANSLATION_SCHEMA,
        {
            "language": "ar",
            "translation": {
                "$contains_all": ["1,450", "درهم", "ضمان", "5"],
            },
            "preserved_numbers.$length": 2,
            "preserved_numbers[0]": {"$contains_all": ["1,450"]},
            "preserved_numbers[1]": "5",
        },
    ),
    SystemCase(
        "system-translation-02",
        "translation",
        _SYSTEM_BASE
        + "Translate to English exactly and list preserved numbers as strings.",
        "Translate: يتوفر 7 كراسٍ في مستودع دبي.",
        _TRANSLATION_SCHEMA,
        {
            "language": "en",
            "translation": {
                "$contains_all": ["7", "chairs", "Dubai", "warehouse"],
            },
            "preserved_numbers.$length": 1,
            "preserved_numbers[0]": "7",
        },
    ),
    SystemCase(
        "system-translation-03",
        "translation",
        _SYSTEM_BASE + "Translate to Arabic exactly. Preserve SKU and number.",
        "Translate: Please confirm 12 units of NV-T2.",
        _TRANSLATION_SCHEMA,
        {
            "language": "ar",
            "translation": {
                "$contains_all": ["تأكيد", "12", "وحدة", "NV-T2"],
            },
            "preserved_numbers.$length": 1,
            "preserved_numbers[0]": "12",
        },
    ),
    SystemCase(
        "system-translation-04",
        "translation",
        _SYSTEM_BASE + "Translate to English exactly. Preserve the percentage and day.",
        "Translate: الخصم 10% صالح لمدة 3 أيام.",
        _TRANSLATION_SCHEMA,
        {
            "language": "en",
            "translation": {
                "$contains_all": ["10%", "discount", "3", "days"],
            },
            "preserved_numbers.$length": 2,
            "preserved_numbers[0]": "10%",
            "preserved_numbers[1]": {"$contains_all": ["3"]},
        },
    ),
    SystemCase(
        "system-tool-01",
        "tool_arguments",
        _SYSTEM_BASE
        + 'Use the appropriate tool with query "ergonomic chair" and limit 2.',
        "Find up to two ergonomic chairs in the catalog.",
        {},
        {"query": "ergonomic chair", "limit": 2},
        tools=(CATALOG_SEARCH_TOOL, STOCK_TOOL),
        expected_tool="search_catalog",
    ),
    SystemCase(
        "system-tool-02",
        "tool_arguments",
        _SYSTEM_BASE + 'Use the appropriate tool for SKU "AX-E1".',
        "Check the current stock for AX-E1.",
        {},
        {"sku": "AX-E1"},
        tools=(STOCK_TOOL, CATALOG_SEARCH_TOOL),
        expected_tool="check_stock",
    ),
    SystemCase(
        "system-tool-03",
        "tool_arguments",
        _SYSTEM_BASE
        + 'Use the appropriate tool with reason_code "discount_approval" and summary exactly "Customer requests 15% discount".',
        "Escalate the customer's 15% discount request.",
        {},
        {
            "reason_code": "discount_approval",
            "summary": "Customer requests 15% discount",
        },
        tools=(ESCALATE_TOOL, STOCK_TOOL),
        expected_tool="escalate_to_manager",
    ),
    SystemCase(
        "system-tool-04",
        "tool_arguments",
        _SYSTEM_BASE
        + 'Use the appropriate tool with SKU "NV-T2", quantity 12, and customer_company "Orbit Labs".',
        "Prepare a non-binding quote draft for Orbit Labs.",
        {},
        {"sku": "NV-T2", "quantity": 12, "customer_company": "Orbit Labs"},
        tools=(QUOTE_DRAFT_TOOL, ESCALATE_TOOL),
        expected_tool="prepare_quote_draft",
    ),
)


_BACKGROUND_SUMMARY_SCHEMA = _strict_object(
    {
        "language": {"type": "string", "enum": ["en", "ar"]},
        "selected_sku": {"type": ["string", "null"]},
        "quantity": {"type": ["integer", "null"]},
        "next_action": {"type": "string"},
    }
)
_BACKGROUND_EXTRACTION_SCHEMA = _strict_object(
    {
        "language": {"type": "string", "enum": ["ru"]},
        "sku": {"type": "string"},
        "quote_consent": {
            "type": "string",
            "enum": ["not_requested", "deferred", "declined", "granted"],
        },
    }
)
_BACKGROUND_CONSENT_SCHEMA = _strict_object(
    {
        "quote_consent": {
            "type": "string",
            "enum": ["not_requested", "deferred", "declined", "granted"],
        },
        "collect_details": {"type": "boolean"},
    }
)
_BACKGROUND_CUSTOMER_SCHEMA = _strict_object(
    {
        "customer_type": {"type": "string", "enum": ["company", "individual"]},
        "company": {"type": ["string", "null"]},
        "budget_aed": {"type": ["integer", "null"]},
        "address": {"type": ["string", "null"]},
    }
)
_BACKGROUND_EVALUATOR_SCHEMA = _strict_object(
    {
        "flags": {
            "type": "array",
            "items": {"type": "string"},
        },
        "applicable_rules": {
            "type": "array",
            "items": {"type": "string"},
        },
        "score_out_of_30": {"type": "number", "minimum": 0, "maximum": 30},
    }
)


BACKGROUND_HARD_CASES: tuple[SystemCase, ...] = (
    SystemCase(
        "bg-en-summary-correction",
        "summary",
        _SYSTEM_BASE + "Use the latest explicit correction.",
        (
            "Conversation: customer first requested 20 AX-E1 chairs, then corrected "
            "the quantity to 12. Next action is to confirm color."
        ),
        _BACKGROUND_SUMMARY_SCHEMA,
        {
            "language": "en",
            "selected_sku": "AX-E1",
            "quantity": 12,
            "next_action": {"$contains_all": ["confirm", "color"]},
        },
    ),
    SystemCase(
        "bg-ar-summary",
        "summary",
        _SYSTEM_BASE + "Summarize the explicit Arabic request without translating it.",
        "العميل اختار NV-T2 وعدد 8. الخطوة التالية تأكيد اللون.",
        _BACKGROUND_SUMMARY_SCHEMA,
        {
            "language": "ar",
            "selected_sku": "NV-T2",
            "quantity": 8,
            "next_action": {"$contains_all": ["اللون"]},
        },
        critical_fields=("language", "selected_sku", "quantity"),
    ),
    SystemCase(
        "bg-ru-exact-sku-no-quote",
        "fact_extraction",
        _SYSTEM_BASE + "Extract the exact SKU and explicit quotation refusal.",
        "Нужен именно CH 616 NEW black. Коммерческое предложение не делайте.",
        _BACKGROUND_EXTRACTION_SCHEMA,
        {
            "language": "ru",
            "sku": "CH 616 NEW black",
            "quote_consent": "declined",
        },
        critical_fields=("language", "sku", "quote_consent"),
    ),
    SystemCase(
        "bg-quote-consent",
        "fact_extraction",
        _SYSTEM_BASE
        + "A request to discuss a quotation later is deferred, not granted.",
        "The products look suitable, but let's discuss a quotation later.",
        _BACKGROUND_CONSENT_SCHEMA,
        {"quote_consent": "deferred", "collect_details": False},
        critical_fields=("quote_consent", "collect_details"),
    ),
    SystemCase(
        "bg-customer-facts",
        "fact_extraction",
        _SYSTEM_BASE
        + "A budget is not an address and a named company is not an individual.",
        "Orbit 12 LLC has a budget of AED 12,000. No delivery address was given.",
        _BACKGROUND_CUSTOMER_SCHEMA,
        {
            "customer_type": "company",
            "company": "Orbit 12 LLC",
            "budget_aed": 12000,
            "address": None,
        },
        critical_fields=("customer_type", "company", "budget_aed", "address"),
    ),
    SystemCase(
        "bg-red-flags-evaluator",
        "red_flags",
        _SYSTEM_BASE
        + "Score only applicable rules. The invented stock is a critical flag.",
        (
            "Customer asks for AX-E1 stock. Assistant claims 50 units without a "
            "stock tool. Applicable rules: catalog_grounding and factual_trust."
        ),
        _BACKGROUND_EVALUATOR_SCHEMA,
        {
            "flags.$length": 1,
            "flags[0]": "invented_stock",
            "applicable_rules.$length": 2,
            "score_out_of_30": 0,
        },
        critical_fields=(
            "flags.$length",
            "flags[0]",
            "applicable_rules.$length",
        ),
    ),
)


def validate_case_sets() -> None:
    """Fail early when the accepted suite shape or strictness drifts."""

    if len(SALES_CASES) != 12:
        raise ValueError(f"Expected 12 sales cases, got {len(SALES_CASES)}")
    if len(SYSTEM_CASES) != 24:
        raise ValueError(f"Expected 24 system cases, got {len(SYSTEM_CASES)}")
    all_ids = [
        case.case_id
        for case in (
            *SALES_CASES,
            *SYSTEM_CASES,
            *CORE_HARD_CASES,
            *BACKGROUND_HARD_CASES,
        )
    ]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Case IDs must be unique")
    expected_categories = {
        "fact_extraction",
        "red_flags",
        "faq_candidate",
        "summary",
        "translation",
        "tool_arguments",
    }
    actual_categories = {case.category for case in SYSTEM_CASES}
    if actual_categories != expected_categories:
        raise ValueError(
            f"System categories mismatch: expected {expected_categories}, "
            f"got {actual_categories}"
        )
    for case in (*SYSTEM_CASES, *BACKGROUND_HARD_CASES):
        if case.tools and not case.expected_tool:
            raise ValueError(f"{case.case_id}: tool case lacks expected_tool")
        if not case.tools and not case.schema:
            raise ValueError(f"{case.case_id}: structured case lacks schema")
    if {case.case_id for case in CORE_HARD_CASES} != {
        "S01",
        "S02",
        "S03",
        "S04",
        "S05",
        "S08",
    }:
        raise ValueError("Core hard fixture IDs must remain S01-S05 and S08")
    if len(BACKGROUND_HARD_CASES) != 6:
        raise ValueError("Expected 6 differentiating background fixtures")
    if not all(case.conversation for case in CORE_HARD_CASES):
        raise ValueError("Every core hard fixture must exercise multi-turn context")
