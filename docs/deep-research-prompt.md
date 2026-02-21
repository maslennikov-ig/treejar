# Deep Research Prompt: AI Sales Bot for Office Furniture (WhatsApp)

## Your Role

You are a senior software architect conducting deep technology research for a production project. Your goal is to find the **most powerful, mature, and production-ready** libraries, frameworks, SDKs, boilerplate repositories, and SaaS tools that we can use as building blocks — so we write as little custom code as possible.

For each finding, evaluate: maturity, maintenance status, GitHub stars, last release date, async Python support, documentation quality, and production readiness.

---

## Project Context

### What We're Building

An **AI-powered sales assistant** for a B2B office furniture company (Treejar) operating in UAE, Saudi Arabia, Qatar, and Oman. The bot communicates with customers via **WhatsApp**, consults them on products, checks real-time stock and pricing, creates commercial proposals (quotations), manages CRM records, and can escalate to human managers.

### Business Domain

- **Industry**: Office furniture wholesale/retail (B2B + B2C)
- **Geography**: UAE, Saudi Arabia, Qatar, Oman (MENA region)
- **Languages**: English + Arabic (Gulf dialect)
- **Catalog size**: ~1,000 SKUs (expanding to 1,500)
- **Daily conversations**: 10-20 now, scaling to 100-200 in 6 months
- **Sales cycle**: Days to weeks (not impulse purchases)
- **Average deal**: Multiple products, custom quotes with discounts

### Key User Flows

1. **New lead arrives via WhatsApp** → Bot greets, identifies language (EN/AR), asks clarifying questions about needs → Searches product catalog via RAG → Shows products with photos and prices → Creates quotation (SaleOrder PDF via Zoho) → Sends to customer
2. **Returning customer** → Bot identifies by phone number via Zoho CRM → Loads full history (past orders, preferences, segment/pricing tier) → Personalized recommendations and pricing
3. **Escalation** → Bot detects complex request/complaint → Transfers full conversation context to human manager
4. **Quality control** → Separate AI bot scores every conversation using a 15-rule checklist (0-2 points each, max 30) → Weekly reports
5. **Follow-ups** → Automated follow-up messages at 24h, 3 days, 7 days after quote

### Sales Methodology (Built Into Bot)

The bot must follow a structured sales conversation flow:
- Stage 1: Greeting + introduction + ask customer's name
- Stage 2: Active listening, ask clarifying questions ("What is it for? What problem does it solve?")
- Stage 3: "Drill and hole" principle — sell solutions, not products
- Stage 4: Propose comprehensive solution (beyond initial request), offer package discounts
- Stage 5: Collect company details (name, position, email)
- Stage 6: Create and send quotation with multiple options (different designs, price ranges)
- Stage 7: Close deal or schedule follow-up

### Integrations Required

| System | Purpose | API Type |
|--------|---------|----------|
| **Wazzup** (wazzup24.com) | WhatsApp gateway — send/receive messages, media | REST API + Webhooks |
| **Zoho CRM** | Contacts, deals/pipeline, interaction history | REST API + OAuth2 |
| **Zoho Inventory** | Products, stock levels, prices, SaleOrder/quotation creation + PDF | REST API + OAuth2 |
| **OpenRouter** (openrouter.ai) | LLM access (DeepSeek, Claude, GPT models) | OpenAI-compatible API |
| **Qdrant** | Vector database for product search (RAG) | gRPC + REST |
| **treejartrading.ae** | Product data import (Tilda CMS, CSV export) | CSV/API |
| **bazara.ae** | Product data + photos import (Shopify) | CSV/API |

### Confirmed Technical Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.13 |
| Web framework | FastAPI | 0.129 |
| ORM | SQLAlchemy | 2.0.46 (async) |
| Migrations | Alembic | 1.18.4 |
| Database | PostgreSQL | 17 |
| Vector DB | Qdrant | 1.16.3 |
| Cache/Queue | Redis | 8.0 |
| HTTP client | httpx | 0.28.1 |
| Containers | Docker + Compose | v28 |
| LLM access | OpenRouter via openai SDK | — |

### What We've Already Decided

- **OpenRouter** for LLM (not direct Claude/OpenAI API) — provides model switching capability
- **Qdrant** for vector search (self-hosted)
- **`openai` Python SDK** with `base_url="https://openrouter.ai/api/v1"` for LLM calls
- **Custom httpx async clients** for Wazzup API and Zoho Inventory (no SDKs available)
- **`zohocrmsdk8-0`** for Zoho CRM (official SDK, sync, wrapped in threadpool)
- **`sqladmin`** for admin panel v1 (mounted in FastAPI)
- **`BAAI/bge-m3`** via FastEmbed for embeddings (free, local, multilingual)

---

## Research Areas

### Area 1: Complete AI Sales Bot / Conversational Commerce Frameworks

Search for **production-ready frameworks or platforms** specifically built for AI sales assistants, conversational commerce, or customer service bots. Not just chatbot builders, but systems with:
- Conversation state/stage management (sales funnel stages)
- Product catalog integration with semantic search
- CRM integration capabilities
- Multi-language support
- WhatsApp channel support
- Quote/proposal generation

Look at:
- Open-source projects on GitHub (any language — we can adapt patterns)
- Commercial platforms with self-hosted options (Botpress, Rasa, Typebot, etc.)
- Vertical SaaS for sales automation (that expose APIs)
- AI agent frameworks with sales-specific modules

Key question: **Is there a 70-80% ready solution we can extend, rather than building from scratch?**

### Area 2: Conversation Orchestration & Agent Frameworks

Beyond basic LLM calls, we need **stateful conversation management** across WhatsApp sessions. Research:

- **PydanticAI** — structured outputs, dependency injection, tool calling, OpenRouter support
- **LangGraph** — stateful agent graphs, conversation flow management
- **AutoGen** / **CrewAI** — multi-agent orchestration (e.g., separate "Sales Agent" + "Quality Agent" + "CRM Agent")
- **Mirascope** — lightweight alternative to LangChain for structured LLM interactions
- **Instructor** — structured output extraction from LLMs
- **Magentic** — function-call based LLM integration
- **Burr** — state machine for AI applications
- **Any newer frameworks released in 2025-2026** that we might not know about

Key questions:
- Which framework is best for **managing a multi-stage sales conversation** that persists across WhatsApp messages over days/weeks?
- Which supports **tool calling** (search products, check stock, create CRM record) most cleanly?
- Which has the best **OpenRouter / multi-model** support?

### Area 3: RAG for Product Catalogs (E-commerce RAG)

Standard RAG (document chunks + semantic search) may not be optimal for a **structured product catalog**. Research:

- **Hybrid retrieval** (semantic + keyword/BM25) for product codes, brand names, exact matches
- **Structured RAG** — combining vector search with SQL filters (price range, category, stock > 0)
- **Qdrant's built-in features** we might not be using: payload filtering, quantization, sparse vectors, hybrid search, recommendation API
- **Product search engines** — Typesense, Meilisearch, OpenSearch — should we use one alongside Qdrant?
- **E-commerce-specific RAG solutions** or libraries
- **Embedding models** best suited for product catalogs + multilingual (EN/AR):
  - BAAI/bge-m3 (our current choice)
  - Jina Embeddings v3 (8192 tokens, 89 languages, task-specific LoRA)
  - Cohere embed-v4
  - Any newer models in 2025-2026

Key question: **What is the best architecture for searching 1,000-1,500 products where users ask in free text (EN or AR) but also need exact SKU/brand matching and price/stock filtering?**

### Area 4: Zoho Integration Ecosystem

Deep dive into Zoho integration:

- **Zoho Flow** — can it handle webhook → CRM/Inventory automation without custom code?
- **Zoho Catalyst** (serverless functions) — can we run bot logic inside Zoho's cloud?
- **Zoho SalesIQ** — Zoho's own chatbot platform. Can it integrate with WhatsApp + custom AI?
- **Zoho Deluge scripts** — in-CRM automation language
- **Unified Zoho API** — is there a single OAuth2 token for both CRM + Inventory?
- **Community integrations** — any Python libraries that handle Zoho OAuth2 token refresh elegantly (the refresh_token → access_token dance)
- **Zoho Inventory SaleOrder → PDF** — exact API workflow to create a quotation and get the PDF URL

Key question: **Can we leverage Zoho's own automation to reduce custom code for CRM/Inventory operations?**

### Area 5: WhatsApp Business API & Wazzup Alternatives

While we've committed to Wazzup, research the landscape:

- **Wazzup API** — full capabilities (media handling, templates/HSM, read receipts, typing indicators, group chats). Any undocumented features?
- **WABA (WhatsApp Business API) directly via Meta** — is it worth considering going direct? Pros/cons vs Wazzup
- **Alternative gateways**: 360dialog, Twilio, MessageBird, Gupshup — feature comparison with Wazzup
- **WhatsApp Business Platform features** we should leverage: catalog messages, interactive buttons, list messages, product messages, flows
- **WhatsApp Commerce** — Meta's native shopping features within WhatsApp. Can the bot use WhatsApp catalog/cart natively?

Key question: **Are there WhatsApp-native commerce features (interactive product lists, cart, catalog) that would make the bot more powerful than plain text messages?**

### Area 6: Quotation / Proposal Generation

The bot needs to create professional commercial proposals:

- Can Zoho Inventory's **SaleOrder API** generate branded PDFs directly? What does the workflow look like?
- **Alternative PDF generation**: WeasyPrint, FPDF2, ReportLab, Puppeteer/Playwright for HTML→PDF
- **Proposal/quote SaaS** with APIs: PandaDoc, Proposify, Qwilr — any that integrate with Zoho?
- **Template engines** for dynamic documents: Jinja2 + HTML → PDF

Key question: **What is the simplest path to send a professional branded PDF quotation to a WhatsApp customer, with product images, prices, and company branding?**

### Area 7: Quality Assurance & Conversation Analytics

The project requires an AI quality control system that evaluates every bot conversation:

- **LLM-as-a-judge** frameworks and patterns
- **Conversation analytics platforms**: Observe.ai, Symbl.ai, AssemblyAI — any with self-hosted or API-based evaluation?
- **Custom scoring rubrics** with LLMs — best practices for consistent automated evaluation
- **Ragas** — RAG evaluation framework (relevant for measuring retrieval quality)
- **LangSmith / LangFuse / Helicone / Braintrust** — LLM observability and evaluation platforms
- **Guardrails AI** — input/output validation for LLM responses

Key question: **What is the best approach to automatically score conversations on a 15-rule rubric and generate weekly quality reports?**

### Area 8: Voice Message Handling

Customers send voice messages in WhatsApp. The bot needs to:

- Transcribe Arabic (Gulf dialect) + English voice messages
- Respond appropriately (text response to voice input)

Research:
- **Whisper** (OpenAI) — latest version, Arabic quality, self-hosted vs API
- **Deepgram** — real-time transcription, Arabic support
- **AssemblyAI** — transcription quality for Arabic
- **Google Speech-to-Text** — Arabic dialect support
- **Faster-Whisper** — optimized self-hosted Whisper inference

Key question: **What is the most accurate and cost-effective way to transcribe Gulf Arabic voice messages?**

### Area 9: Admin Panel & Monitoring

- **sqladmin** vs **starlette-admin** vs **FastAPI-Admin** — detailed comparison for our use case (view conversations, edit prompts, see metrics)
- **Grafana + Prometheus** for monitoring (response times, LLM costs, error rates)
- **LangFuse** — LLM observability (track every prompt, tokens, cost, latency)
- **Streamlit** — could it work as a quick admin panel for prompt editing and conversation review?
- **Chainlit** — chat interface for testing/debugging the bot

Key question: **What is the fastest path to a working admin panel where the client can view conversations, edit bot prompts, and see basic metrics?**

### Area 10: Full-Stack Templates & Reference Architectures

Find the **best production-ready FastAPI + async SQLAlchemy + Docker boilerplates** that are closest to our needs:

- Must include: async SQLAlchemy 2.0+, Alembic migrations, Pydantic v2, PostgreSQL, Redis, Docker Compose, background job processing
- Nice to have: Qdrant integration, OpenAI/LLM integration, WebSocket support, rate limiting, JWT auth
- Look at repos from late 2024 - 2026

Specific repos to evaluate:
- `benavlabs/FastAPI-boilerplate` (1.8k stars) — async, ARQ jobs, rate limiting
- `fastapi/full-stack-fastapi-template` (34k stars) — official
- `jonra1993/fastapi-alembic-sqlmodel-async` (1.3k stars) — includes LangChain
- Any **newer repos from 2025-2026** that combine FastAPI + LLM + RAG

Key question: **What is the best starting template that gives us 40-60% of the infrastructure code out of the box?**

---

## Output Format

For each research area, provide:

1. **Top 3-5 findings** ranked by relevance to our project
2. For each finding:
   - Name, URL, GitHub stars (if applicable)
   - Last release date and maintenance status
   - Key features relevant to our use case
   - Async Python support (critical requirement)
   - License
   - **Verdict**: USE / CONSIDER / SKIP with clear reasoning
3. **Architecture recommendation** — how the findings fit together
4. **"Hidden gems"** — lesser-known but powerful tools we might have missed
5. **Anti-patterns to avoid** — common mistakes in projects like this

## Final Deliverable

At the end, provide a **consolidated recommended stack** showing:
- Every library/service we should use
- Why it beats the alternatives
- How they all connect together (architecture diagram in text)
- Total dependency count and complexity assessment
- Risk assessment: what are the weakest links?
