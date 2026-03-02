# Generating branded PDFs in Python: a definitive architectural guide

**WeasyPrint is the strongest choice for a startup generating branded quotations and sales orders in Python/FastAPI**, offering the best balance of CSS Paged Media support, manageable resource consumption, and template-based design workflow. It handles running headers/footers, product images in table rows, Cyrillic text, and multi-page table splitting — all critical requirements — while fitting inside a **250–400 MB Docker image** versus Playwright's 1.2–1.5 GB. For teams wanting to avoid infrastructure entirely, PDFShift ($24/month for 2,500 documents) provides Chromium-quality rendering via API with zero server management. Direct drawing libraries like FPDF2 offer the lightest footprint (~100 MB Docker) but sacrifice the HTML/CSS design workflow that makes pixel-perfect branding achievable by any frontend developer.

This analysis evaluates five distinct approaches across resource efficiency, output quality, developer experience, and total cost of ownership for a B2B platform generating hundreds to thousands of product-catalog PDFs monthly.

---

## The resource and quality tradeoff across all five approaches

Every PDF generation strategy occupies a point on the spectrum between rendering fidelity and infrastructure cost. The table below captures the critical metrics that drive architectural decisions:

| Metric | Playwright | WeasyPrint | ReportLab | FPDF2 | SaaS (PDFShift) |
|---|---|---|---|---|---|
| **Docker image size** | 1.2–1.5 GB | 250–400 MB | 150–200 MB | 100–130 MB | 0 (API call) |
| **RAM per PDF render** | 500–700 MB peak | 20–40 MB typical | ~21 MB (text) | ~15–25 MB | N/A |
| **Generation speed** | 1–3s (warm browser) | 0.5–3s | <100ms (simple) | <100ms (simple) | 1.5–5s (network) |
| **CSS Paged Media** | ~35% of spec | ~75% of spec | None (programmatic) | None (programmatic) | 90%+ (DocRaptor) |
| **Images in table rows** | ✅ Native HTML | ✅ Native HTML | ✅ Flowable API | ✅ Cell API | ✅ Native HTML |
| **Cyrillic/Russian** | ✅ With fonts | ✅ With fonts | ✅ TTF embedding | ✅ TTF embedding | ✅ |
| **Async FastAPI fit** | Native async API | `run_in_threadpool` | Sync + threadpool | Sync + threadpool | Native async HTTP |
| **Monthly cost (infra)** | $10–20 VPS | $5–15 VPS | $5 VPS | $5 VPS | $24–300 SaaS |

**The standout insight**: WeasyPrint occupies a unique sweet spot — it consumes **one-third the Docker space** of Playwright, provides **far superior print CSS support** (running headers, page counters, margin boxes), and accepts standard HTML/CSS templates that any web developer can maintain. Its main weakness is performance on very large documents (50+ pages), which is rarely relevant for quotations and sales orders.

---

## Headless browsers deliver fidelity at a heavy infrastructure cost

Playwright with Chromium renders PDFs identically to Chrome's print engine — every CSS feature that works in a browser works in the PDF. This makes it seductive for teams with existing HTML templates. However, the operational burden is substantial.

**A single Chromium instance idles at ~65 MB but peaks at 500–700 MB during rendering.** On a 4-core machine, you can realistically handle 4–8 concurrent PDF renders before saturating CPU. Memory leaks are a documented, recurring concern: GitHub issue #15400 reports the Playwright Node process consuming **400 MB+ within 20 minutes** of continuous use, and issue #38489 (February 2026) reports instances consuming **~20 GB RAM** after switching to Chrome for Testing binaries. Production deployments require aggressive process recycling.

The Docker image is the heaviest of all options. Even installing only Chromium via `playwright install --with-deps chromium` on a `python:3.12-slim` base yields **1.2–1.5 GB**. Multi-stage distroless builds can trim this, but Chromium's binary alone is 400–500 MB. You must also configure `--shm-size=1gb` in Docker (the default 64 MB `/dev/shm` causes crashes) and install Cyrillic font packages like `fonts-noto` or `fonts-dejavu-core`.

**Page break handling in tables is Chrome's Achilles' heel.** Chromium bug #99124 documents that `page-break-inside: avoid` is ignored on `<tr>` and `<td>` elements because they are not block-level. The workaround — wrapping cell content in `<div>` elements and applying `break-inside: avoid` there — works but adds template complexity. `<thead>` with `display: table-header-group` does correctly repeat headers on each page.

Chrome 131 (October 2024) added support for the **16 CSS page margin boxes** (`@top-left`, `@bottom-center`, etc.) and `counter(page)`/`counter(pages)`, making it the only browser supporting these features. However, Chrome still lacks `string-set` (running headers from document content), footnotes, and `target-counter()` — features WeasyPrint and Prince XML handle natively. A critical gotcha: **headless Chrome silently refuses to fetch images referenced in `@page` CSS rules**, requiring base64 data URIs for logos in margin boxes.

The async integration with FastAPI is genuinely good. Playwright's `async_api` is truly non-blocking for I/O, and the recommended pattern — a singleton browser launched at FastAPI startup with per-request browser contexts controlled by an `asyncio.Semaphore` — works well for moderate concurrency. But the CPU-bound nature of rendering means async doesn't reduce actual resource consumption per PDF.

**Best fit**: Teams already deeply invested in complex HTML/CSS/JS templates who need exact browser rendering fidelity and can allocate 2+ GB RAM to PDF infrastructure.

---

## WeasyPrint is purpose-built for printed documents from HTML

WeasyPrint implements the CSS Paged Media specification more completely than any other open-source tool. This is its defining advantage for generating branded business documents. It supports **running elements** (`position: running(name)` + `content: element(name)`), allowing arbitrary HTML — logos, company addresses, page numbers — to be placed into margin boxes. It supports `string-set` for running headers that automatically update with section titles. It supports `@page :first`, `:left`, `:right`, and even `@page :nth(2n+1)` selectors.

Since version 53, WeasyPrint uses its own PDF generator (`pydyf`) instead of Cairo, reducing system dependencies. A Debian-slim Docker image with WeasyPrint, Pango, HarfBuzz, and Cyrillic fonts lands at **250–400 MB** — a third of Playwright's footprint. Alpine-based builds can reach ~105 MB but risk subtle rendering differences from musl libc and require careful font management.

**Memory is the primary operational concern.** Each PDF generation adds 20–40 MB to RSS for simple documents, and this memory is not fully reclaimed by garbage collection. Large table documents are worse: **5,000 table rows consumed ~1.4 GB on first render and ~2.1 GB cumulatively on second render**. The mitigation strategy is straightforward for a FastAPI deployment: run Gunicorn with multiple Uvicorn workers and set `max_requests` to recycle workers periodically. For quotations typically containing 10–50 line items, the 20–40 MB per render is entirely manageable.

Tables automatically split across pages, and `<thead>` elements repeat on each new page. However, **`break-inside: avoid` on `<tr>` elements has a documented regression** since commit 222677d — table cells now split between pages, and the avoid directive is sometimes ignored. Testing your specific table layout is essential. Block-level layouts with `<div>` wrappers tend to be more reliable for page-break control than pure `<table>` elements.

Image handling is flexible. WeasyPrint fetches HTTPS URLs natively (S3 presigned URLs work), supports data URIs for embedded images, and allows custom `url_fetcher` callables for advanced scenarios like direct S3 SDK integration. The `cache` parameter enables image caching across document generations — critical for a product catalog where the same product images appear in many quotations.

For FastAPI, use `await run_in_threadpool(generate_pdf_sync, data)` since WeasyPrint's `write_pdf()` is synchronous and CPU-bound. The Python GIL means true parallelism requires multiple worker processes, but for a startup generating hundreds of PDFs daily, a 2–4 worker Gunicorn setup on a $10/month VPS handles the load comfortably.

WeasyPrint is **very actively maintained**: version 68.1 shipped February 2026, with 9 releases in the past 12 months and 596,700 weekly PyPI downloads. The maintainer organization (CourtBouillon) offers professional support. The library also supports **PDF/A archival format**, **CMYK colors**, and **Factur-X/ZUGFeRD electronic invoice standards** — relevant for European B2B invoicing.

**Best fit**: The strongest overall choice for branded business documents — quotations, invoices, sales orders — where CSS-based template design, print-quality layout features, and moderate resource consumption matter most.

---

## Direct drawing libraries trade design flexibility for raw performance

ReportLab and FPDF2 generate PDFs by programmatically drawing elements at coordinates, bypassing HTML/CSS entirely. This eliminates browser dependencies and produces the lightest Docker images, but shifts the design burden from CSS styling to Python layout code.

**ReportLab** is the elder statesman — 20+ years in production at financial institutions, with a mature Platypus layout engine. Its `Table` class supports images as flowable objects inside cells, automatic page splitting with `repeatRows` for header repetition, and granular `TableStyle` control over borders, backgrounds, and cell formatting. A benchmark rendering Homer's Odyssey (~700K characters) completed in **351ms with C acceleration**, using ~21 MB RAM — dramatically faster than any HTML-based approach. Docker images run **150–200 MB** since the C extensions are optional and pre-built wheels are pure Python.

The downside is verbosity. A branded invoice with headers, footers, tables with product images, and financial calculations requires **120–250 lines of Python** depending on complexity. Every layout decision — font sizes, column widths, spacing, color codes — lives in Python code rather than a CSS file. Changing a brand color means modifying Python, not editing a stylesheet. Thread safety is a concern: the global `pdfmetrics` font registry has reported `TTFError` exceptions under concurrent load. Register all fonts at startup, create fresh document objects per request.

**FPDF2** is the modern, lighter alternative. It is **100% pure Python** with zero system dependencies — the Docker image footprint is just **100–130 MB**. Its `pdf.table()` context manager offers a remarkably clean API: images in cells via `row.cell(img="path")`, automatic page breaks with repeated headings via `repeat_headings=ON_TOP_OF_EVERY_PAGE`, and colspan/rowspan support. A typical branded invoice requires **40–70 lines of Python**, roughly 40% less than ReportLab. The library explicitly documents FastAPI integration patterns and states the FPDF class is thread-safe with per-request instances.

FPDF2's Cyrillic support is excellent — the official tutorial is available in Russian, and TrueType font embedding with automatic subsetting works cleanly. Community momentum is strong: 1,100+ GitHub stars, 1,300+ unit tests, 50+ contributors, and it joined the `py-pdf` organization (alongside `pypdf`) in 2023. The LGPL v3.0 license requires distributing modifications if you modify the library itself, though using it as-is in a commercial product is fine.

Both libraries handle the core use case — tables with product images, branded headers/footers, financial totals — but the **design iteration cycle is fundamentally slower** than HTML/CSS. Tweaking a table's visual appearance means editing Python code, re-running the generation, and viewing the output. With WeasyPrint or Playwright, a designer can adjust CSS in a browser's DevTools and see results instantly.

**Best fit**: FPDF2 for serverless/Lambda deployments where Docker size is critical, or for teams that prefer code-driven layouts and want maximum performance. ReportLab for enterprise environments with existing ReportLab investment or need for charting capabilities.

---

## SaaS options range from impractical to compelling

**Zoho Inventory is not the right tool for PDF generation.** While its API supports creating Sales Orders with line items, tax calculations, and template selection, the PDF template editor **cannot natively embed product images inside item table rows** — the critical requirement. The item table is limited to text columns (name, description, quantity, rate). Custom HTML templates in Zoho CRM offer more flexibility, but Zoho Inventory's editor is constrained. API rate limits (100 requests/minute, 2,500–10,000/day by plan) and pricing ($59–299/month) make it expensive purely as a PDF rendering service. The vendor lock-in is high: templates are proprietary and non-portable. Only consider Zoho if you are already adopting it as your actual ERP.

**Dedicated PDF SaaS services are more compelling.** Three stand out:

- **DocRaptor** uses Prince XML — the engine built by the CSS specification author. It offers the **best CSS Paged Media support available** (running headers, footnotes, cross-references, mixed page sizes). Output is print-grade quality used by Shopify and HubSpot. Pricing runs $75–149/month for 1,500–5,000 documents, with 30 simultaneous concurrent requests and a **99.99% uptime SLA**. The trade-off is cost at scale: 10,000 PDFs/month approaches $300+.
- **PDFShift** uses headless Chromium and offers the best value: **$24/month for 2,500 documents** with up to 50 parallel conversions, 1.5-second average latency, and direct S3 delivery. It handles all HTML/CSS/JS that Chrome supports. GDPR-compliant (French company, EU servers).
- **PDFMonkey** provides a visual template dashboard plus API at **€15/month for 3,000 documents**. Templates support Tailwind CSS, Google Fonts, and QR codes. Best for teams wanting a visual editor alongside API access.

The hybrid approach maximizes flexibility: maintain Jinja2 HTML/CSS templates in your FastAPI repository, render data into HTML server-side, and send the rendered HTML to PDFShift or DocRaptor for PDF conversion. Your templates are version-controlled and portable — switching providers means changing one API call. At 1,000 PDFs/month, PDFShift costs $24 versus $5–15 for a self-hosted VPS, but eliminates all infrastructure maintenance. The break-even point where self-hosting becomes clearly cheaper is around **5,000 PDFs/month** when factoring in engineering time.

**Data privacy is the primary SaaS concern.** Every document's HTML — containing customer names, pricing, product details — passes through third-party servers. DocRaptor and PDFShift both claim no document retention and offer encryption in transit and at rest, with SOC2/HIPAA compliance. For highly sensitive B2B pricing data, self-hosted generation eliminates this concern entirely.

---

## Definitive recommendation for a B2B startup

The optimal architecture depends on your team's current stage and priorities. Here is a tiered recommendation:

**Phase 1 (MVP, <1,000 PDFs/month): PDFShift SaaS + Jinja2 templates.** Store HTML/CSS templates in your FastAPI repo. Render data with Jinja2. Send rendered HTML to PDFShift's API ($24/month). Zero infrastructure to manage. Full Chromium rendering quality. Product images in table rows work natively. When you outgrow PDFShift or need data privacy, migrate to Phase 2 — your templates are portable HTML/CSS.

**Phase 2 (Growth, 1,000–10,000 PDFs/month): Self-hosted WeasyPrint.** Deploy WeasyPrint in your existing FastAPI container or as a sidecar service. Your Jinja2 templates from Phase 1 transfer directly — WeasyPrint renders the same HTML/CSS. Add `position: running()` for branded headers/footers with logos, `counter(page)` for page numbering, and `@page` margin boxes for precise print layout. Run 2–4 Gunicorn workers with `max_requests=500` for memory recycling. Total infrastructure cost: **$10–20/month additional** on your existing VPS. Generation speed: 0.5–3 seconds per document.

**Phase 3 (Scale, 10,000+ PDFs/month): WeasyPrint + task queue.** Move PDF generation to Celery workers or a dedicated microservice. This isolates memory-intensive rendering from your API servers and enables horizontal scaling. The same WeasyPrint templates and code from Phase 2 carry over. Budget $40–80/month for dedicated PDF worker instances.

**Avoid Playwright** unless you specifically need JavaScript execution in templates (charts, dynamic content). The 1.2–1.5 GB Docker image, 500–700 MB RAM per render, and documented memory leaks make it disproportionately expensive for structured business documents that don't need JS.

**Avoid ReportLab/FPDF2 as primary** unless your team strongly prefers code-driven layouts. The design iteration cycle is slower, brand changes require code modifications, and the development overhead exceeds the infrastructure savings for most teams. FPDF2 is worth considering for serverless (AWS Lambda) deployments where the 100 MB footprint is critical.

**Avoid Zoho** as a PDF generation tool — it's an ERP that happens to produce PDFs, not a PDF generation solution, and it cannot embed product images in table rows.

## Conclusion

The PDF generation landscape for Python breaks cleanly into two philosophies: **template-driven** (HTML/CSS rendered to PDF) and **code-driven** (programmatic drawing). For branded B2B documents requiring pixel-perfect design with product images, the template-driven approach wins on maintainability and design velocity. Among template-driven options, **WeasyPrint uniquely combines open-source accessibility with the deepest CSS Paged Media implementation**, supporting running headers, margin boxes, and page counters that Chromium only partially implements. Its 250–400 MB Docker footprint, 0.5–3 second generation times, and active maintenance (9 releases in 12 months, ~600K weekly downloads) make it production-ready for the described B2B use case. Start with PDFShift SaaS if you want zero infrastructure overhead today, then graduate to self-hosted WeasyPrint when volume, privacy, or cost demands it — your HTML/CSS templates transfer seamlessly between the two.