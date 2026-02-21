# DeepThink Prompt: Architecture Analysis for AI Sales Bot

## Your Task

You are a senior software architect with 15+ years of experience building production AI systems, conversational bots, and e-commerce integrations. You are NOT searching the web — you are **thinking deeply** about architecture decisions, trade-offs, risks, and design patterns for this project.

Analyze the project below. For each area, think through multiple approaches, evaluate trade-offs, identify risks we haven't considered, and recommend the optimal architecture. Challenge our assumptions. Tell us what we're getting wrong.

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
- **Team**: Solo developer (with AI coding assistant), 13-week timeline, 600K RUB budget

### Key User Flows

1. **New lead via WhatsApp** → Bot greets → Identifies language (EN/AR) → Asks clarifying questions → RAG search on product catalog → Shows products with photos + prices → Creates quotation (SaleOrder PDF via Zoho Inventory) → Sends to customer
2. **Returning customer** → Identifies by phone via Zoho CRM → Loads full history (orders, preferences, pricing tier) → Personalized recommendations + pricing
3. **Escalation** → Detects complex request/complaint → Transfers full context to human manager
4. **Quality control** → Separate AI bot scores every conversation using 15-rule checklist (0-2 each, max 30) → Weekly reports
5. **Follow-ups** → Automated at 24h, 3 days, 7 days after quote

### Sales Conversation Stages

The bot follows a structured methodology:
1. Greeting + introduction + ask name
2. Active listening, clarifying questions ("What is it for? What problem does it solve?")
3. "Drill and hole" principle — sell solutions, not products
4. Comprehensive solution beyond initial request, package discounts
5. Collect company details (name, position, email)
6. Create quotation with multiple options (designs, price ranges)
7. Close deal or schedule follow-up

### Integrations

| System | Purpose | API |
|--------|---------|-----|
| **Wazzup** (wazzup24.com) | WhatsApp gateway | REST + Webhooks |
| **Zoho CRM** | Contacts, deals, history | REST + OAuth2 |
| **Zoho Inventory** | Products, stock, prices, SaleOrder + PDF | REST + OAuth2 |
| **OpenRouter** | LLM access (DeepSeek, Claude, GPT) | OpenAI-compatible |
| **Qdrant** | Vector DB for product search | gRPC + REST |
| **2 websites** | Product data import (Tilda CSV, Shopify CSV) | CSV |

### Current Technical Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Python 3.13 | FastAPI 0.129 + async SQLAlchemy 2.0.46 + asyncpg | Modern async stack |
| PostgreSQL 17 | Primary DB | LTS, reliable |
| Qdrant 1.16 | Vector search for products | Self-hosted, fast |
| Redis 8.0 | Cache, sessions, job queue | Unified modules |
| `openai` SDK | LLM calls via OpenRouter `base_url` | Stable, async, streaming |
| `BAAI/bge-m3` via FastEmbed | Embeddings (local, multilingual) | Free, EN/AR support |
| `zohocrmsdk8-0` | Zoho CRM (sync, via threadpool) | Official SDK |
| Custom httpx clients | Wazzup + Zoho Inventory | No SDKs exist |
| `sqladmin` | Admin panel v1 | Zero frontend build |
| Docker Compose | All 6 services | Dev + production |

---

## Think Deeply About These Questions

### 1. Architecture: Monolith vs Microservices vs Modular Monolith

We planned a single FastAPI app with all logic. For a solo developer on a 13-week timeline with 10-200 daily conversations:

- Is a monolith the right call, or should we separate the WhatsApp webhook handler from the AI processing pipeline?
- Should the AI processing be synchronous (within the webhook response) or asynchronous (queue + worker)?
- WhatsApp has a 20-second timeout for webhook acknowledgment. If AI response generation takes 5-15 seconds, how should we architect the response flow?
- What happens if the LLM is slow or down? How do we handle graceful degradation?

Think through the request lifecycle: Wazzup webhook → our server → LLM → Wazzup send message. What are the failure modes?

### 2. Conversation State Management

This is the hardest problem. Conversations span days/weeks across multiple WhatsApp messages. The bot must:
- Remember what stage of the sales flow it's in
- Track what products were discussed
- Know if it's waiting for customer data (company name, email)
- Handle context switching ("actually, I also need chairs")
- Resume after days of silence

Questions:
- Should we use a **finite state machine** (explicit stages) or let the **LLM manage the flow** via prompting?
- How much conversation history should we send to the LLM? Last N messages? Summary + recent? Full history?
- Where to store conversation state: PostgreSQL (durable) vs Redis (fast) vs both?
- How do we handle the **context window limit** when a conversation has 200+ messages over 2 weeks?
- What is the optimal prompt architecture? System prompt + conversation summary + last N messages + tool results?

### 3. RAG Strategy for Product Catalog

Our catalog is 1,000-1,500 structured products (not unstructured documents). Each has: SKU, name (EN/AR), description, category, price, stock, images, specs.

Questions:
- Is pure vector search (RAG) the right approach, or should we use **structured queries** (SQL-like filtering) + vector search as a hybrid?
- When a customer says "I need 10 black executive chairs under 500 AED", should we: (a) embed the query and search Qdrant, (b) extract filters (color=black, category=chairs, price<500) and query PostgreSQL, (c) both in parallel?
- Should the LLM decide what tool to use (vector search vs structured query vs CRM lookup), or should we have a deterministic routing layer?
- How often should we re-embed products? On every Zoho Inventory sync? On schedule?
- With only 1,000-1,500 products, do we even need RAG? Would a well-structured prompt with category-based filtering be sufficient?

### 4. LLM Strategy and Prompt Engineering

We use OpenRouter which gives access to 400+ models.

Questions:
- Should we use **one model for everything**, or different models for different tasks (e.g., cheap model for intent classification, powerful model for response generation, fast model for quality scoring)?
- What is the optimal **model selection** for: (a) Arabic + English bilingual sales conversation, (b) structured data extraction (product search params), (c) quality scoring?
- How do we handle **model switching** gracefully? If DeepSeek is down, auto-fallback to Claude?
- What is the cost per conversation? Estimate tokens for a typical 20-message sales conversation with RAG context.
- How do we prevent **hallucinations** about products? The bot must never invent prices, stock levels, or product features.
- Should we use **tool calling** (function calling) or **prompt-based extraction** for structured actions (search products, create CRM record, generate quote)?

### 5. Zoho Integration Complexity

Zoho CRM + Zoho Inventory are the backbone. Both use OAuth2 with refresh tokens.

Questions:
- The official CRM SDK is **synchronous**. Using `run_in_threadpool` adds overhead. Is there a better pattern? Should we just use raw httpx for CRM too?
- How do we handle **OAuth2 token refresh** across concurrent requests? Token expires → multiple requests try to refresh simultaneously → race condition?
- Zoho has **API rate limits** (100 req/min). With 200 conversations/day, each potentially doing 3-5 API calls (contact lookup, deal create, stock check, SaleOrder) — do we hit limits?
- Should we **cache Zoho data** in PostgreSQL and sync periodically, or make real-time API calls? What about stale prices/stock?
- The SaleOrder → PDF flow: does Zoho generate the PDF instantly, or is there a delay? How do we send the PDF to WhatsApp?

### 6. Multi-Language (Arabic) Challenges

Gulf Arabic has specific challenges:

Questions:
- LLMs vary dramatically in Arabic quality. Which models on OpenRouter handle Gulf Arabic best?
- Should the system prompt be in English (with Arabic instructions) or in Arabic?
- How do we handle **code-switching** (customer mixes Arabic and English in one message)?
- Arabic is RTL. Does this affect any of our text processing, search, or display?
- Voice messages in Arabic: Whisper's Arabic quality varies by dialect. How critical is voice transcription for the MVP?

### 7. Error Handling and Resilience

The bot is a customer-facing system that handles real money. Failures are visible.

Questions:
- What happens when: Zoho is down? OpenRouter is slow? Qdrant returns no results? Wazzup webhook fails?
- Should we have **circuit breakers** for each external service?
- How do we handle **duplicate webhooks** from Wazzup? (At-least-once delivery)
- What is the **retry strategy** for failed LLM calls? Retry same model? Fallback to different model?
- Should we have a **dead letter queue** for messages we couldn't process?
- How do we ensure we **never lose a customer message**, even during downtime?

### 8. Testing Strategy for an AI System

Traditional unit tests don't cover LLM behavior.

Questions:
- How do we test that the bot gives **correct product recommendations**?
- How do we test that the bot follows the **sales methodology stages** correctly?
- How do we test **Arabic responses** quality without Arabic-speaking testers?
- Should we use **LLM-based testing** (one model evaluates another model's output)?
- What are the **critical test scenarios** for the MVP demo at week 3?
- How do we create a **regression test suite** that catches prompt changes breaking behavior?

### 9. Security and Privacy

Customer data flows through multiple systems (WhatsApp → Wazzup → our server → Zoho → LLM provider).

Questions:
- Customer phone numbers, company details, and order amounts pass through OpenRouter to the LLM. What are the **data privacy implications** for MENA region? Any UAE/KSA data residency requirements?
- Should we **redact sensitive data** before sending to the LLM?
- How do we secure the webhook endpoint? Wazzup sends a webhook to our public URL — how do we verify authenticity?
- Zoho OAuth2 tokens must be stored securely. Where and how?
- The admin panel will have access to all conversations. What authentication/authorization do we need?

### 10. What We're Not Seeing

Based on your experience with similar projects:

- What are the **top 3 things that go wrong** in AI chatbot projects like this?
- What **features will the client inevitably request** that we haven't planned for?
- What is the **biggest technical risk** in our current architecture?
- If you had to **cut scope** to deliver on time, what would you cut and what is absolutely essential?
- What would you do **differently** from our plan?
- Are there any **fundamental assumptions** we're making that could be wrong?

---

## Output Format

For each of the 10 questions above, provide:

1. **Your analysis** — think through all angles, don't just give the first answer
2. **Recommended approach** — what you'd actually build
3. **Why not the alternatives** — briefly explain why other approaches are worse
4. **Risk level** (Low / Medium / High) — how badly can this go wrong
5. **Key decision** — the one thing we must get right

At the end, provide:

### Summary: Architecture Decision Record

A consolidated list of the **10 most important architecture decisions** for this project, each with:
- Decision
- Context (why this decision matters)
- Options considered
- Chosen option and rationale
- Consequences (positive and negative)

### Priority-Ordered Risk Register

Top 10 risks, ordered by (impact × likelihood), with mitigation strategies.

### Critical Path

What are the 5 things that, if done wrong, will cause the project to fail? In order of importance.
