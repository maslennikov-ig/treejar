# Code Review Report: Quotation Generation Feature

**Scope**: Review of the `quotation-generation` feature implementation, specifically focusing on `src/llm/engine.py`, `src/services/pdf/generator.py`, and integration with Wazzup & Zoho Inventory.

## High-Level Summary
The implementation successfully integrates WeasyPrint and Jinja2 for PDF generation and wires them up to the new `create_quotation` LLM tool. The system now queries Zoho Inventory for bulk stock, builds a draft order, injects real data into an HTML template, generates the PDF bytes, and sends the media directly via Wazzup.

The code is generally clean, well-tested, and functional, but there are several maintainability and robustness areas that could be improved before considering this production-ready. 

---

## Findings by Severity

### 🔴 Blocking (Must Fix)
None found in the immediate critical path. The basic functionality works and all tests pass (including recent linter auto-fixes).

### 🟡 Important (Should Fix)
1. **Error Handling & Retries**: 
   - Operations like `create_sale_order` and `send_media` are wrapped in minimal `try...except Exception` blocks, returning simple strings to the LLM agent on failure. Hard failures here will drop the context.
   - **Suggestion**: Use specific exception catching (e.g., `httpx.HTTPError`) or integrated automated retry mechanisms. Consider letting the LLM know *why* exactly the API call failed (e.g., network error vs validation error).

2. **Hardcoded Values**:
   - The PDF context in `create_quotation` contains hardcoded data:
     - `trn: "100418386400003"`
     - `customer_id = "temp_draft_customer_id"`
     - `manager: { ... }` (Syed Amanullah) 
   - **Suggestion**: Shift these configuration values out into application settings, the `.env` configuration (via `src.core.config.settings`), or fetch them dynamically from the database/CRM.

3. **Dependency Injection & Testing Isolation**:
   - The method performs delayed imports (`from src.services.pdf.generator import generate_pdf`). While this is sometimes useful to avoid circular dependencies, it is generally discouraged, as it hides structural dependencies.
   - **Suggestion**: If it must rely on `generate_pdf`, pass the PDF generator service into `SalesDeps` instead, isolating the implementation from the LLM engine for cleaner tests and DI.

### 🟢 Minor / Best Practices (Nice to Have)
1. **Logging Improvements**: 
   - `logger.info(f"LLM Tool called: create_quotation(items={items})")` is good, but capturing detailed metrics like PDF generation duration or total API request time could prove valuable in the long term.

2. **Type Safety**:
   - `QuotationItem` uses `sku: str` and `quantity: int`. Since quantities shouldn't be negative, it could benefit from a Pydantic `Field(ge=1)` validation directly inside the tool argument. Validations at the LLM integration layer prevent incorrect arguments.

---

## Action Plan (Beads Tasks)

Based on this review, here are the proposed Beeds tasks (`bd`) to dispatch to sub-agents:

1. **Extract Hardcoded Variables (Cleanup)**: Extract hardcoded TRN, manager details, and temp customer IDs from `engine.py` into proper configuration structures (`config.settings`).
2. **Refactor PDF Generation DI (Architectural)**: Modify `SalesDeps` to inject a `PDFService` protocol instead of relying on delayed imports in `engine.py`. Update tests accordingly.
3. **Enhance Error Handling (Robustness)**: Update exception handlers in `create_quotation` to catch specific errors and provide detailed context to the LLM.

Let me know if you would like me to create these tasks using the `bd` system and dispatch the sub-agents to implement the fixes!
