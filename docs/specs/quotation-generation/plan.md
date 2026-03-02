# Quotation Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement WeasyPrint-based PDF generation for Quotations, save as Draft Sale Orders in Zoho, and send via WhatsApp.

**Architecture:** A FastAPI service using WeasyPrint in a threadpool to generate PDFs from Jinja2 templates. WeasyPrint handles HTML/CSS to PDF with Cyrillic support and table page-breaks. The LLM tool `create_quotation` acts as the orchestrator.

**Tech Stack:** WeasyPrint, Jinja2, FastAPI, Zoho Inventory API, Wazzup API.

---

### Task 1: Docker and System Dependencies

**Files:**
- Modify: `Dockerfile`
- Modify: `pyproject.toml` (or `requirements.txt`)

**Step 1: Write the failing test**
(No direct python test for Dockerfile, but a test to import weasyprint)
```python
def test_weasyprint_installed():
    import weasyprint
    assert weasyprint.__version__ is not None
```

**Step 2: Run test to verify it fails**
Expected: FAIL, module not found.

**Step 3: Write minimal implementation**
- Add `weasyprint` and `jinja2` to python dependencies.
- Add `apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 harfbuzz fonts-noto` to Dockerfile.

**Step 4: Run test to verify it passes**
Expected: PASS after rebuild/install.

**Step 5: Commit**
`git commit -m "build: add weasyprint and jinja2 dependencies"`

---

### Task 2: PDF Generator Service

**Files:**
- Create: `src/services/pdf/generator.py`
- Create: `tests/services/test_pdf_generator.py`

**Step 1: Write the failing test**
```python
@pytest.mark.asyncio
async def test_generate_pdf():
    from src.services.pdf.generator import generate_pdf
    pdf_bytes = await generate_pdf("<h1>Hello</h1>")
    assert pdf_bytes.startswith(b"%PDF-")
```

**Step 2: Run test to verify it fails**
Expected: FAIL

**Step 3: Write minimal implementation**
```python
import asyncio
from weasyprint import HTML

async def generate_pdf(html_content: str) -> bytes:
    def _render():
        return HTML(string=html_content).write_pdf()
    return await asyncio.to_thread(_render)
```

**Step 4: Run test to verify it passes**
Expected: PASS

**Step 5: Commit**
`git commit -m "feat: add async pdf generator service using weasyprint"`

---

### Task 3: Jinja2 Quotation Template

**Files:**
- Create: `src/templates/quotation/template.html`
- Create: `src/templates/quotation/style.css`
- Modify: `src/services/pdf/generator.py` (add template rendering method)
- Create: `tests/services/test_quotation_template.py`

**Step 1: Write the failing test**
```python
def test_render_quotation_template():
    from src.services.pdf.generator import render_quotation_html
    html = render_quotation_html(context={"company_name": "Test Co"})
    assert "Test Co" in html
```

**Step 2: Run test to verify it fails**
Expected: FAIL

**Step 3: Write minimal implementation**
Implement Jinja2 `Environment(loader=FileSystemLoader(...))`. Render HTML template matching the sample structures. Include `@page` CSS.

**Step 4: Run test to verify it passes**
Expected: PASS

**Step 5: Commit**
`git commit -m "feat: add jinja2 quotation template and styles"`

---

### Task 4: Zoho Inventory Draft Sale Order

**Files:**
- Modify: `src/integrations/inventory/zoho_inventory.py`
- Modify: `tests/integrations/test_zoho_inventory.py`

**Step 1: Write the failing test**
```python
@pytest.mark.asyncio
async def test_create_draft_sale_order():
    # mock http client
    provider = ZohoInventoryProvider(...)
    result = await provider.create_sale_order(customer_id="123", items=[...], status="draft")
    assert result.status == "draft"
```

**Step 2: Run test to verify it fails**
Expected: FAIL

**Step 3: Write minimal implementation**
Add `create_sale_order` method to `ZohoInventoryProvider` hitting `POST /api/v1/salesorders` with `status="draft"`.

**Step 4: Run test to verify it passes**
Expected: PASS

**Step 5: Commit**
`git commit -m "feat: add create draft sale order to inventory provider"`

---

### Task 5: The `create_quotation` LLM Tool

**Files:**
- Modify: `src/llm/tools.py`
- Modify: `tests/llm/test_tools.py`

**Step 1: Write the failing test**
```python
@pytest.mark.asyncio
async def test_create_quotation_tool():
    # mock dependencies (inventory, wazzup, pdf generator)
    result = await create_quotation(...)
    assert "PDF sent successfully" in result
```

**Step 2: Run test to verify it fails**
Expected: FAIL

**Step 3: Write minimal implementation**
Implement the tool logic: fetch item details (and base64 encode images), create draft sale order, render HTML, generate PDF, send via wazzup `send_media`.

**Step 4: Run test to verify it passes**
Expected: PASS

**Step 5: Commit**
`git commit -m "feat: add create_quotation llm tool"`
