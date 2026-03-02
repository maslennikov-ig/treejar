# Quotation Generation Specification

**Goal:** Generate beautiful, branded PDF quotations using WeasyPrint and Jinja2 templates, save them as Draft Sales Orders in Zoho Inventory, and send them to the customer via WhatsApp (Wazzup).

## Context & Architecture Decision
Following deep research on Python PDF generation, we have abandoned Zoho Inventory's built-in PDF generator due to its inability to embed product images natively in table rows. 
Instead, we adopt **WeasyPrint**, which offers excellent CSS Paged Media support, moderate resource consumption (250-400MB Docker footprint), and native HTML/CSS design workflow.

## Core Components

### 1. PDF Infrastructure (WeasyPrint)
- **Library:** `weasyprint`, `jinja2`.
- **System Dependencies:** Dockerfile must include `libpango-1.0-0`, `libpangoft2-1.0-0`, `harfbuzz`, `fonts-noto` (for Cyrillic text).
- **Service Layer:** `src/services/pdf/generator.py` encapsulating `weasyprint.HTML(string=...).write_pdf()`. Since WeasyPrint is CPU-bound, generation MUST run in `fastapi.concurrency.run_in_threadpool`.

### 2. Quotation Template (Jinja2)
- **Files:** `src/templates/quotation/template.html` and `src/templates/quotation/style.css`.
- **Design Elements (Based on successful samples):**
  - **Header:** Skyland & Treejar logos, Quote Number, TRN, Date.
  - **Customer Info:** Name, Company, Email, Address.
  - **Item Table:** Photo (Reference Image), SKU/Code, Description (with warranty/dimensions), QTY, Unit Price, Total Price.
  - **Pagination:** `<thead style="display: table-header-group">` to repeat column headers on every page. Use `@page` for bottom-center page numbers and margin-bottom.
  - **Summary:** TOTAL, VAT (5%), GRAND TOTAL.
  - **Footer:** Terms & Conditions (Delivery: 2-8 days, Payment terms, Validity 15 days), Manager contact info.

### 3. Zoho Inventory Integration Updates
- `InventoryProvider` must support creating a Sale Order with status `draft`.
- Mapping items: The Draft Sale Order in Zoho ensures items are linked correctly to the warehouse, even if the PDF is generated locally.

### 4. LLM Tool: `create_quotation`
- **Purpose:** Extracts confirmed order details from the dialogue, triggers generation, and sends the PDF.
- **Workflow:**
  1. Parse intent and extract items (SKUs, quantities), customer name, email, company.
  2. Call `InventoryProvider` to fetch rich product details (prices, valid image URLs, full descriptions).
  3. Call `InventoryProvider.create_sale_order(..., status="draft")` to register the quote in Zoho.
  4. Generate PDF bytes using `pdf_generator.generate_quotation_pdf(context)`.
  5. Fetch/Cache product images: Ensure image URLs are embedded in the HTML or pre-downloaded to a temp directory so WeasyPrint can fetch them.
  6. Call `MessagingProvider.send_media(..., file_bytes)` to send the PDF via WhatsApp.
  7. Return success message to LLM to continue the conversation seamlessly.

### 5. Caching Strategy
- Zoho product image URLs can be passed directly to WeasyPrint if they are public. If they require auth, images must be fetched using `httpx` and passed as `data:image/jpeg;base64,...` URIs into the Jinja2 context to avoid authentication failures in WeasyPrint's default URL fetcher.

## Metrics & Observability
- Track PDF generation time (should be < 3 seconds).
- Log any WeasyPrint warnings (especially missing fonts or broken image links).
