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
    forbidden_phrases: tuple[str, ...] = ()
    expected_language: str | None = None


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


def validate_case_sets() -> None:
    """Fail early when the accepted suite shape or strictness drifts."""

    if len(SALES_CASES) != 12:
        raise ValueError(f"Expected 12 sales cases, got {len(SALES_CASES)}")
    if len(SYSTEM_CASES) != 24:
        raise ValueError(f"Expected 24 system cases, got {len(SYSTEM_CASES)}")
    all_ids = [case.case_id for case in (*SALES_CASES, *SYSTEM_CASES)]
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
    for case in SYSTEM_CASES:
        if case.tools and not case.expected_tool:
            raise ValueError(f"{case.case_id}: tool case lacks expected_tool")
        if not case.tools and not case.schema:
            raise ValueError(f"{case.case_id}: structured case lacks schema")
