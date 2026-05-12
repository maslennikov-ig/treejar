# Hybridize, don't rewrite: a LangGraph + Parlant playbook for the furniture sales agent

**Recommendation up front: hybridize.** Keep the custom Python core (Wazzup adapter, Zoho integrations, quotation PDF generator, audit logs) and replace the brittle in-house dialogue routing with **LangGraph as the durable orchestration backbone**, plus **Parlant** as a lighter alternative to evaluate against it in a 1-week PoC. Do **not** adopt Rasa CALM (commercial paywall, $35k/yr floor), CrewAI (natural-language delegation breaks determinism), AutoGen/AG2 (3-way fork instability), or any commercial WhatsApp "AI agent" product (none cover Zoho Inventory + multilingual EN/RU/AR + KП generation). The failure modes you describe — tool-call ordering, lost product selection, broken quote resumption, messy escalation — are exactly the problems LangGraph's typed `StateGraph` + `PostgresSaver` checkpointing solve structurally, and exactly the problems Parlant's observation-gated tool calling + Journey state-diagrams solve declaratively. Both keep your Python, your model freedom (OpenRouter), and your existing adapters. The remaining custom-system rot is symptomatic of *no first-class state primitive* — once you have one, most of the bespoke routing rules disappear.

---

## 1. Executive summary

Your symptom list is a textbook case of "custom agent rot": every dialogue bug becomes another `if/elif` in a router until the system is a behavioral spaghetti only the original author can debug. The frontier-model layer is not the problem — your core needs are **durable per-thread state, structurally-gated tool calls, and explicit phase transitions**. These are framework-level concerns, not prompting concerns.

**The decision:** keep the parts that encode your business (Zoho, quotation, Wazzup, audit), replace the parts that encode generic agent infrastructure (router, memory, tool ordering, escalation transitions). The framework that wins on production evidence is **LangGraph 1.0**: it is the only orchestration framework with named, large-scale, multi-turn transactional production deployments (Klarna handling 2/3 of CS at $40M+ savings, AppFolio Realm-X, Replit Agent, Uber, LinkedIn, Elastic SecOps, Minimal e-commerce, Rakuten), first-class checkpointers (`PostgresSaver`) keyed by `thread_id` (= WhatsApp phone number) that directly solve "remember the chair Ahmed selected three days ago," and existing prior art for WhatsApp + LangGraph stacks (Twilio's official inventory-bot tutorial; the `lgesuellip/langgraph-whatsapp-agent` and `lucasboscatti/Whatsapp-Langgraph-Agent-Integration` reference repos).

**The challenger to test in parallel:** **Parlant** (Apache-2.0, 17.8k stars, Python-native, no open-core paywall). Its primitives — Observations, Guidelines, Journeys (state-diagram SOPs), Canned Responses, Tools — map almost 1:1 to your problem. Tools only enter the LLM context when their bound observation fires, which **structurally prevents** the "wrong-tool / photos-before-text" class of bug at the prompt level rather than the orchestration level. JPMorgan and Oracle engineers publicly endorse it; Revenued ships its Sales Copilot on it. The risk is youth: smaller community, v3.0 (Aug 2025) is still recent.

**What to reject and why:**
- **Rasa CALM** is the most architecturally rigorous competitor (explicit flow-lifecycle events: started/interrupted/resumed/cancelled), but **CALM is gated behind Rasa Pro** — Developer Edition caps at 1,000 conversations/month, then jumps to **$35,000/year** Growth tier. The pricing pushback on Rasa's own forums is real, and you forfeit the OSS-first ergonomics that justify the YAML DSL pain.
- **CrewAI** uses natural-language delegation between agents — every coordination step is an LLM call, which is the *opposite* of the determinism you need to fix photo-before-text and quote-resume. Industry pattern is "prototype with CrewAI, productionize with LangGraph."
- **AutoGen / AG2** is mid-fork: AutoGen 0.2 → MS Agent Framework, AG2 community fork, AutoGen 0.4 in maintenance. Don't bet a 6+ month build on this.
- **OpenAI Agents SDK** has shipped 12 minor versions in 12 months and durability requires a separate Temporal integration. Re-evaluate late 2026.
- **Mastra, Inngest Agent Kit, Vercel AI SDK** are TypeScript only.
- **Commercial sales-AI products** (Cresta, Drift/Salesloft, Fin, Regie, Lavender, AiSDR, 11x.ai, Conversica, Air AI, Bland AI) do not fit: wrong channel (mostly email/voice/web-chat), no Zoho-Inventory binding, no multilingual EN/RU/AR quotation PDFs, and the AI-SDR class has well-documented 70–80% churn and a recent 11x.ai investor scandal plus Drift OAuth-token breach (Aug 2025). Augment humans, don't replace them.
- **WhatsApp-platform AI agents** (Wati KnowBot, Gallabox GPT, Manychat AI, Chatfuel Fuely, Interakt, AiSensy, Twilio AI Assistants) cannot call your custom Python webhooks for catalog/RAG/quotation in the way your business requires. Wati's AI ingests only PDF/URLs (max 50). Twilio AI Assistants are still Developer Preview / Alpha. Use these platforms purely as **transport**, with your Python brain attached via webhook.

**Net architectural shift:** custom Python → **LangGraph state graph + Postgres checkpointer + mem0 long-term memory + LiteLLM router behind OpenRouter** for the brain; **Wazzup remains transport** (with 360dialog as a documented backup BSP); **Zoho Inventory/CRM, КП generator, audit logs, escalation queue stay custom** because they encode your business, not your dialogue.

---

## 2. Shortlisted candidates

### Agent orchestration
1. **LangGraph** — https://github.com/langchain-ai/langgraph — MIT, ~14–25k ★, v1.0 stable Oct 2025. `StateGraph`, `PostgresSaver`/`RedisSaver` checkpointers, `langgraph-supervisor`, time-travel/forking. Largest production case-study set of any framework.
2. **Pydantic AI** — https://github.com/pydantic/pydantic-ai — MIT, pre-1.0. Type-safe DI (`RunContext[Deps]`), lowest migration cost from plain Python, but you build durability yourself.
3. **Burr** — https://github.com/apache/burr (formerly DAGWorks-Inc/burr) — Apache 2.0, now Apache Incubating. Explicit state machines, fork/rewind, immutable state. Smaller ecosystem; architecturally pristine.
4. **OpenAI Agents SDK** — https://github.com/openai/openai-agents-python — MIT, but pre-1.0 with breaking releases; Temporal needed for durability. Hold.

### Conversational platforms (LLM-first dialogue management)
5. **Parlant** — https://github.com/emcie-co/parlant — Apache-2.0, ~17.8k ★. Observations + Guidelines + Journeys + Canned Responses; observation-gated tools structurally prevent wrong-tool calls.
6. **Rasa CALM** — https://github.com/RasaHQ/rasa-calm-demo + https://rasa.com/docs/rasa-pro/calm/ — Rasa Pro license, $35k/yr Growth tier. Most rigorous flow-lifecycle semantics; commercial gating.
7. **Botpress** (cloud) — https://botpress.com — visual + LLM, 1B+ msgs claimed. Step less deterministic than CALM/Parlant.

### Memory / state
8. **mem0** — https://github.com/mem0ai/mem0 — Apache-2.0, ~50k+ ★. Easiest drop-in; `custom_fact_extraction_prompt` for RU/AR. Standard scope (≈49% LongMemEval) is below Zep's, but adequate for sales sessions.
9. **Zep / Graphiti** — https://github.com/getzep/zep + https://github.com/getzep/graphiti — Graphiti Apache-2.0 (self-host viable; Zep Community Edition deprecated). Best-in-class temporal validity windows for "what was true when?"; multilingual is on roadmap.
10. **LangMem** — https://github.com/langchain-ai/langmem — MIT. Native partner to LangGraph for `SummarizationNode` (long-thread compression).

### WhatsApp transport (keep current; have a documented backup)
- **Wazzup24** — https://wazzup24.com — keep as primary. Native Zoho CRM bridge.
- **Twilio Conversations** — https://www.twilio.com — gold-standard transport reliability if international scale forces a swap.
- **360dialog** — https://360dialog.com — pure BSP, thin markup; doc-grade Zoho integrations.

### Reference repos to mine for code patterns
- **filip-michalsky/SalesGPT** — https://github.com/filip-michalsky/SalesGPT — stage-aware sales agent + RAG; the canonical OSS sales-stage state machine (basis for the SPIN/BANT prompt blocks below).
- **lgesuellip/langgraph-whatsapp-agent** — https://github.com/lgesuellip/langgraph-whatsapp-agent — LangGraph + Twilio WhatsApp + MCP, multi-agent supervisor.
- **lucasboscatti/Whatsapp-Langgraph-Agent-Integration** — https://github.com/lucasboscatti/Whatsapp-Langgraph-Agent-Integration — LangGraph + FastAPI + Postgres-backed memory + voice transcription.
- **Twilio "Smart Inventory Chatbot" tutorial** — https://www.twilio.com/en-us/blog/developers/community/how-to-build-a-smart-inventory-chatbot-on-whatsapp-with-langchai
- **worldbank/WhatsApp-RAG-Example** — https://github.com/worldbank/WhatsApp-RAG-Example — clean RAG-over-catalog reference.

### Prompt / playbook libraries
- **f/awesome-chatgpt-prompts** — https://github.com/f/awesome-chatgpt-prompts (~143k ★).
- **ai-boost/awesome-prompts** — https://github.com/ai-boost/awesome-prompts.
- **Sandler "20 Tested ChatGPT Prompts"** — https://themcaa.org/wp-content/uploads/protected/Sandler_ChatGPT_Prompts_for_Salespeople.pdf — upfront contract templates.
- **Momentum MEDDPICC Call Review prompt** — https://www.momentum.io/prompts/meddpicc-call-review-prompt — full prompt + scoring rubric.
- **Huthwaite SPIN AI prompts** — https://www.huthwaiteinternational.com/blog/ai-spin-prompts.

---

## 3. Comparison table

| Name | Category | Conv. quality reputation | B2B sales fit | WhatsApp | Multi-turn state | Tool calling | CRM/Inv. potential | RAG | Human handoff | EN/RU/AR | Auditability | Customization | License | Lock-in | GitHub activity | Production adoption | Security | Migration effort |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **LangGraph** | Orchestration | Strong (Klarna, AppFolio, Replit, LinkedIn) | High | Via Twilio/Wazzup adapter | First-class `PostgresSaver` checkpoints | Deterministic via graph nodes | Excellent (any Python lib) | Excellent | Native via supervisor / handoff edges | LLM-dependent (frontier models OK) | LangSmith / OTel | Very high | MIT | Low (escapable, self-host) | ~14–25k ★, v1.0 Oct 2025 | Klarna-scale + many | Self-host any cloud | **Medium-high** (graph rewrite) |
| **Parlant** | Conv. platform | Positive but young | High (designed for it) | DIY adapter (~50 LOC) | Journeys + Variables | Observation-gated (anti-hallucination) | Native `@p.tool` Python | Built-in retrievers | Guideline + canned response | LLM-dependent | OTel-compatible | High via Python SDK | Apache-2.0 | Very low | ~17.8k ★, v3.0 Aug 2025 | JPMorgan/Oracle quotes; Revenued | Self-host | **Low-medium** |
| **Rasa CALM** | Conv. platform | Strong (T-Mobile, N26, Lemonade) | High | Native Twilio; Wazzup DIY | Flow lifecycle (start/interrupt/resume/cancel) | Commands → flows → actions | rasa-sdk Python actions | `SearchAndReply` | `HumanHandoff` command | LLM-dependent; no native translation | Studio + reviews | Medium (YAML DSL) | **Source-available, Pro-only** | Medium-high (CALM YAML lock-in) | Active; Pro-gated | Pro customers | Self-host | High (rewrite as flows) |
| **Botpress (cloud)** | Conv. platform | OK (Kia, EA, Husqvarna) | Medium | Native | Flow + Autonomous Node | OK | JS code blocks | Yes | Built-in | Strong | Built-in | Medium (low-code) | Proprietary cloud (v12 OSS AGPL) | High (cloud SaaS) | 1B+ msgs claim | Many | SOC 2 | High |
| **Pydantic AI** | Orchestration | Limited evidence | Medium | DIY | `message_history` + your DB | Decorator tools | Excellent | Bring your own | DIY | LLM-dependent | Logfire/OTel | High | MIT | Low | Active, pre-1.0 | Demo-heavy | Self-host | **Lowest** |
| **Burr** | Orchestration | Niche but praised | Medium | DIY | Explicit FSM, fork/rewind | Deterministic | Excellent | DIY | DIY | LLM-dependent | Built-in | Very high | Apache 2.0 (Incubating) | Very low | Smaller | Peanut Robotics + smaller users | Self-host | Low-medium |
| **OpenAI Agents SDK** | Orchestration | Mixed (12 versions/yr) | Medium | DIY | Sessions (Redis) | Handoffs + tools | Good | DIY | Native handoffs | LLM-dependent | OpenAI tracing | Medium | MIT | High (OpenAI shape) | Pre-1.0 | Limited public | Self-host | Low |
| **CrewAI** | Orchestration | Mediocre debugging | **Low** for transactional | DIY | Memory but no checkpoints | NL delegation = non-deterministic | Good | OK | OK | LLM-dependent | Weak logging | Medium | MIT | Low | ~44k ★ | DocuSign, Gelato — content/lead enrichment | Self-host | Low |
| **AutoGen / AG2** | Orchestration | Conversational not transactional | Low | DIY | Group chat | Non-deterministic | OK | OK | OK | LLM-dependent | Weak | Medium | Apache 2.0 | Medium (3-way fork) | High but unstable | Code/research, not sales | Self-host | Medium |
| **mem0** | Memory | Easy drop-in; benchmark hype | High | n/a | Persistent facts | n/a | Vector store | Yes | n/a | Custom prompt → RU/AR | Per-user store | High | Apache-2.0 | Low | ~50k ★ | YC-backed, broad community | Self-host | **Low** |
| **Zep / Graphiti** | Memory | Strongest temporal reasoning | Very high (quote history) | n/a | Bi-temporal graph | n/a | Graph relations | Yes | n/a | LLM-dependent (multi roadmap) | Multi-tenant native | Medium | Graphiti Apache-2.0; **Zep CE deprecated** | Medium (cloud), Low (Graphiti) | ~20k ★ | ArtPrize + finance/healthcare | SOC 2 / HIPAA cloud | Medium |
| **Letta** | Memory | "Powerful but not polished" | Medium | n/a | Self-editing memory blocks | Tool-using agent | Possible | Vector | n/a | LLM-dependent | Agent Dev Env | Medium | Apache-2.0 | Low | ~18k ★ | Limited B2B sales | Self-host | Medium-high |
| **Wati** | WhatsApp platform | OK transport, weak AI | Low (as brain) | Native Meta BSP | Flow builder | Webhooks | **Native Zoho CRM** | PDF/URL only | Built-in | UI in EN/zh/PT/ES | Logs | Low (no-code) | Proprietary | High | SaaS | Mid-market | SOC 2 | Low (transport only) |
| **Respond.io** | WhatsApp platform | Best native AI in category | Medium (B2C-tuned) | Native | AI Agent + workflows | HTTP step Advanced+ | Zoho via Zapier | RAG-based | Native | Strong (30+ langs) | Logs | Medium | Proprietary | High | SaaS | Automax, GetTUTOR (B2C) | SOC 2 | Low (transport) |
| **Wazzup** | WhatsApp transport | n/a — transport only | High for CIS | Native | n/a | n/a | **Native Zoho** | n/a | Manual | RU native | Logs | n/a | Proprietary | Medium | SaaS | CIS market default | Standard | None (current) |
| **Twilio Conversations** | WhatsApp transport | Gold-standard transport | High | Native | n/a | n/a | DIY | n/a | DIY | Language-agnostic | Logs | Very high (API) | Proprietary | Low (standard API) | Mature | Massive | SOC 2/ISO/HIPAA | Low |
| **360dialog** | WhatsApp transport | Solid BSP | High | Native | n/a | n/a | Via middleware | n/a | DIY | Language-agnostic | Logs | High (API) | Proprietary | Low | Mature | Wide | SOC 2 | Low |

---

## 4. Recommended target architecture

```
                                         ┌────────────────────────────────────┐
                                         │   WhatsApp customer (EN / RU / AR) │
                                         └──────────────┬─────────────────────┘
                                                        │
                                                        ▼
                              ┌─────────────────────────────────────────────┐
                              │  Wazzup24  (transport + Zoho CRM bridge)    │  KEEP
                              │  Backup BSP: 360dialog or Twilio Conv.      │
                              └──────────────┬──────────────────────────────┘
                                             │  webhook (HTTP, JSON)
                                             ▼
                              ┌─────────────────────────────────────────────┐
                              │  FastAPI gateway  (your code)               │  KEEP
                              │  - signature verify, rate-limit, dedup      │
                              │  - normalize {phone, lang, msg, media[]}    │
                              │  - enqueue (Redis Streams) → ack 200        │
                              └──────────────┬──────────────────────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────────────────────┐
                              │  LangGraph agent loop (Python)              │  REPLACE custom router
                              │  StateGraph nodes:                          │
                              │    [intake] → [phase_router]                │
                              │       ├─ discovery_subgraph (SPIN-light)    │
                              │       ├─ selection_subgraph (catalog/RAG)   │
                              │       ├─ quote_subgraph (КП builder)        │
                              │       └─ escalation_subgraph (handoff)      │
                              │  Conditional edges = pure Python            │
                              │  Tools: send_text, send_media, search_cat,  │
                              │    check_stock, build_quote, send_pdf,      │
                              │    create_zoho_lead, escalate_to_human      │
                              │                                             │
                              │  Checkpointer: PostgresSaver                │
                              │  thread_id = whatsapp_phone_number          │
                              │  → durable, resumable across days/weeks     │
                              └────┬────────┬─────────┬─────────┬──────────┘
                                   │        │         │         │
                  ┌────────────────┘        │         │         └────────────┐
                  ▼                         ▼         ▼                      ▼
       ┌──────────────────┐     ┌──────────────────┐ ┌────────────────┐  ┌──────────────────┐
       │  LiteLLM router  │     │  Catalog RAG     │ │ mem0 (long-    │  │ Manager queue    │
       │  → OpenRouter    │     │  pgvector or     │ │ term memory)   │  │ (Postgres + WS)  │
       │  (Claude / GPT / │     │  Qdrant +        │ │ user_id =      │  │ → operator UI    │
       │  Gemini / Llama) │     │  Zoho Inventory  │ │ phone_number   │  │ KEEP             │
       └──────────────────┘     │  sync job        │ │ custom RU/AR   │  └──────────────────┘
                                └─────┬────────────┘ │ extraction     │
                                      │              │ prompt         │
                                      ▼              └────────────────┘
                              ┌──────────────────┐
                              │  Zoho Inventory/ │  KEEP
                              │  Zoho CRM        │
                              │  (your adapters) │
                              └─────┬────────────┘
                                    │
                                    ▼
                              ┌──────────────────┐
                              │  КП / proforma   │  KEEP
                              │  PDF generator   │
                              │  (WeasyPrint /   │
                              │  ReportLab,      │
                              │  multilingual    │
                              │  templates       │
                              │  EN/RU/AR        │
                              │  pre-translated) │
                              └──────────────────┘

       ┌─────────────────────────────────────────────────────────────────┐
       │  Cross-cutting:                                                 │
       │   - Audit log (your Postgres "events" table)         KEEP       │
       │   - LangSmith (or OTel + Langfuse) for traces        ADD        │
       │   - Promptfoo + DeepEval regression suite            ADD        │
       │   - Admin/operator panel                              KEEP      │
       └─────────────────────────────────────────────────────────────────┘
```

**How this maps to your failure modes:**
- *Photos before text* → eliminated structurally. `send_text` and `send_media` are separate tool nodes; the graph specifies edges (`send_text` → `send_media` mandatory in `selection_subgraph`); the LLM never decides ordering.
- *Repeated photo after selection* → `state["selected_product_sku"]` is set in `selection_subgraph`; `phase_router` checks it; once non-null, the graph cannot re-enter discovery without an explicit "browse other options" intent edge.
- *Lost context for quotation* → `PostgresSaver` checkpoints every node. If the customer goes silent for 3 days and resumes, `thread_id = phone_number` rehydrates the exact `state` (`selected_product_sku`, `qty`, `delivery_city`, `quote_draft_id`, `language`).
- *Quote requires deterministic recovery* → `quote_subgraph` is a small linear FSM with explicit retry edges per tool failure. LLM only fills slots; it does not "decide" to call `build_quote` — the graph does, when slots are full.
- *Phase handoff* → `phase_router` is one Python function reading `state["phase"]`; transitions are explicit, observable, and unit-testable.

---

## 5. What to keep custom (and why)

1. **Wazzup adapter** — your customers' WhatsApp numbers, templates, and message IDs are already onboarded; Wazzup's Zoho-CRM bridge gives free contact/lead sync that no replacement matches for CIS. Replacement risk > replacement upside.
2. **Zoho CRM and Zoho Inventory adapters** — these encode *your* SKU model, pricing tiers, stock locations, dealer hierarchies. No framework can autogenerate this; LangGraph just calls them as tools.
3. **Quotation / КП PDF generation** — locale-correct currency, RTL Arabic layout, your legal boilerplate, signature blocks, regional VAT rules, your branding. Off-the-shelf "quote" features in Wati/Respond.io won't render Russian + Arabic side-by-side or apply your discount logic.
4. **Audit log table** — already integrated with your operator panel; replacing it with LangSmith would create a second source of truth and a compliance gap.
5. **Operator/admin tools** — your humans already know them. The escalation subgraph just writes to your queue.
6. **FastAPI webhook gateway** — signature verification, idempotency, dedup, rate-limit. Boring, working code; no benefit to migrating.
7. **Multilingual template registry (EN/RU/AR)** — WhatsApp templates must be pre-approved per language; you already own this catalog.
8. **Pricing / discount engine** — business logic, not dialogue. Stays a pure Python module called as a tool.

---

## 6. What to replace or simplify

| Current custom code | Replace with | Why |
|---|---|---|
| Hand-rolled "phase router" with growing if/elif | **LangGraph `StateGraph` + conditional edges** | Single source of truth for phase; visualizable; unit-testable nodes |
| Per-bug "send text before image" patches | **Two separate tool nodes (`send_text`, `send_media`) wired in fixed order** | Removes the class of bug; LLM cannot reorder a graph it doesn't author |
| Ad-hoc dict / Redis keys for "selected product" | **Typed `StateGraph` schema (TypedDict / Pydantic)** with explicit fields (`selected_sku`, `qty`, `delivery_city`, `quote_draft_id`, `language`, `phase`) | Compile-time discipline; LangSmith traces show every state mutation |
| Re-entrant prompts that re-recommend after selection | **`phase_router` guard: if `selected_sku is not None`, edge → `selection_confirm` not `discovery`** | Structural prevention; not a prompt rule the LLM might violate |
| Long conversation drift / context blow-up | **LangMem `SummarizationNode` at >N turns** rolling into `state["summary"]` | Token budget control + persistent semantic recall |
| Long-term cross-session memory ("Ahmed wanted Aeron last week") | **mem0** with `user_id = phone`, custom RU/AR fact-extraction prompt | Drop-in; Apache-2.0; cheaper than Zep for sales-session scope |
| Custom "did the user ask for a manager?" regex/classifier | **LangGraph `escalate_to_human` tool with a single guideline-style description** + sentiment signal | LLM picks tool only when clearly justified; deterministic fallback on keywords still in-graph |
| OpenAI client glue with model fallback try/except | **LiteLLM in front of OpenRouter** | Single OpenAI-compatible URL; per-route model choice (cheap model for stage classification, frontier for free-text) |
| In-memory session state lost on restart | **`PostgresSaver` checkpointer** | Process restart, deploy, or 3-day customer pause all rehydrate cleanly |
| Manual logging of every tool call | **LangSmith or OTel + Langfuse traces** alongside your audit log | Per-step latency, token, error visibility; keep audit log for compliance |
| Free-text "do you confirm?" steps | **WhatsApp interactive list/button templates** at confirmation moments | Vonage/Twilio interactive messaging; structural confirm vs free-text drift |

---

## 7. One-week proof-of-concept plan

**Goal:** prove either LangGraph (primary) or Parlant (challenger) eliminates all four failure modes against a realistic furniture quotation scenario, in your own codebase, before committing to a full migration.

**Scenario fixture** (use this throughout): An Arabic-speaking buyer asks about ergonomic chairs for a 12-person Dubai office; switches to Russian mid-thread; chooses a model; goes silent for 36 hours; returns and asks for a quote in EN; modifies quantity twice; requests a manager when asked about delivery to a remote site.

### Day 1 — Scaffold and shared harness
- Stand up a separate `poc/` repo with two stacks side-by-side: `poc/langgraph/` and `poc/parlant/`.
- Implement a **shared adapter layer** (Python module): `wazzup_adapter`, `zoho_inventory_stub` (mocked with a 50-SKU furniture catalog JSON), `zoho_crm_stub`, `pdf_quote_stub`, `audit_log_stub`, `escalation_stub`. Both stacks consume identical adapters so the comparison is purely orchestration.
- Provision Postgres (Docker) for `PostgresSaver` and a Qdrant container for the catalog index.
- Wire LiteLLM → OpenRouter; pick `claude-sonnet-4` for free-text and `gpt-4o-mini` for stage classification.
- **Deliverable:** Both stacks accept a normalized inbound message and return a stub reply end-to-end.

### Day 2 — LangGraph build
- Define `StateGraph` schema (Pydantic): `phase`, `language`, `customer_profile`, `selected_sku`, `qty`, `delivery`, `quote_draft_id`, `summary`, `messages`.
- Implement four subgraphs: `discovery`, `selection`, `quote`, `escalation`. Add `phase_router` conditional edges.
- Wire tools as nodes: `search_catalog`, `check_stock`, `build_quote`, `send_text`, `send_media`, `escalate_to_human`. **Force** `send_text → send_media` ordering in `selection`.
- Configure `PostgresSaver`; key `thread_id = phone_number`.
- **Deliverable:** Manual runthrough of scenario completes without the four bugs.

### Day 3 — Parlant build (challenger)
- Define an `Agent` with: Observations (`customer_asking_pricing`, `product_selected`, `quote_in_progress`, `customer_requesting_human`), Guidelines binding tools to observations, Journeys for `discovery → selection → quote → handoff`, Canned Responses for confirmations and КП preview text.
- Wrap the same adapters as `@p.tool` decorators; bind to the matching observation.
- Wire OpenRouter via `base_url` override.
- **Deliverable:** Parallel scenario passes; bot uses canned response for the price confirmation moment.

### Day 4 — Memory layer + multilingual
- Add **mem0** to both stacks (`user_id = phone`). Provide `custom_fact_extraction_prompt` in EN with explicit instructions to extract facts when input is RU or AR. Run scenario with the 36-hour pause simulated by truncating the in-memory thread state and rehydrating only via mem0 + checkpointer.
- Add **LangMem `SummarizationNode`** in LangGraph stack only.
- Pre-translate three KП templates (EN/RU/AR) and the four escalation/confirmation WhatsApp templates.
- **Deliverable:** After the simulated 36-hour pause, both bots correctly recall `selected_sku`, `qty=12`, `delivery=Dubai`, and resume the quote without re-asking.

### Day 5 — Eval harness
- Build a 30-conversation golden set (15 EN, 10 RU, 5 AR) covering the four failure modes plus three new edge cases (stock-out, price challenge, partial quantity).
- Stand up **Promptfoo + DeepEval** with G-Eval-style rubrics: *(a) Captured BANT? (b) Followed upfront contract? (c) Sent text before media? (d) Resumed correctly after pause? (e) Escalated cleanly? (f) Did Zoho CRM get the right slot values? (g) Did the quote PDF amount equal catalog × qty?*
- Run both stacks; compute pass rate, token cost, p50/p95 latency.
- **Deliverable:** A scorecard table comparing LangGraph vs Parlant per metric.

### Day 6 — Stress and operability
- Inject failure: drop a tool call (simulated Zoho 500), kill the process mid-quote, restart. Verify checkpoint rehydration in LangGraph; verify Parlant journey resumption.
- Test concurrency: 50 simulated WhatsApp threads, mixed-language, parallel.
- Measure: per-thread isolation, no cross-tenant leakage, audit-log completeness, LangSmith trace completeness.
- **Deliverable:** Operations report — restart-survival, concurrency, observability.

### Day 7 — Decision document
- Write an internal recommendation: which stack to migrate, in what order, with a phased plan (read-only "shadow mode" first → 10% traffic → 100%).
- Identify what custom code is **deleted** (the routing rules), what is **kept** (Zoho/Wazzup/PDF/audit).
- Propose a 4-week production migration plan if PoC passed; or a 1-week tightening of current system if it didn't.

**Pass criteria:** Chosen stack must (1) eliminate all four named failure modes in the eval, (2) survive process restart with zero state loss, (3) keep p95 latency under 4s, (4) maintain ≥85% on the eval rubric. If neither passes, the decision is *not* "stay custom forever" — it's "fix custom incrementally with a typed state object and a Postgres checkpointer module before re-evaluating frameworks in 2 months."

---

## 8. Red flags

- **Rasa CALM pricing trap.** The Developer Edition's 1,000-conversation cap (or 100 employee-facing) is a marketing funnel, not a production tier. The next step is **$35,000/year** for 500K conversations, with widely reported community pushback. Adopt only if you'd buy the Pro license anyway and want vendor support; otherwise the YAML rewrite cost has no payoff.
- **CrewAI for transactional sales.** Praised for content/lead-enrichment pipelines, mediocre for deterministic dialogue. Multiple production teams report debugging hell — "logging is a huge pain… normal print and log functions don't work well inside Task." Industry pattern is to prototype here and productionize on LangGraph; skip the prototype waste.
- **AutoGen / AG2 fork instability.** AutoGen 0.2 is the historical version, AG2 (ag2ai) is the community fork, AutoGen 0.4 is being absorbed into Microsoft Agent Framework (combining AutoGen + Semantic Kernel). Three-way uncertainty for a 6+ month commitment.
- **OpenAI Agents SDK velocity.** 12 minor releases in 12 months, pre-1.0, durability requires a separate Temporal integration. Vendor lock to OpenAI's Responses API shape. Re-evaluate late 2026.
- **TypeScript-only frameworks (Mastra, Inngest Agent Kit, Vercel AI SDK).** Mastra has the strongest case-study set after LangGraph (Replit, Marsh McLennan, Factorial), and Inngest's durability model is arguably best-in-class. Disqualified by your Python requirement; revisit only if you contemplate a stack switch.
- **Letta as "just a memory layer."** Letta wants to be the agent runtime; using it solely for memory is fighting its design. Use mem0 or Zep instead unless you'd commit to Letta as the orchestrator.
- **Zep Community Edition deprecated.** Self-hosted Zep is gone; only Graphiti (the engine) remains OSS. If you need full self-hosted long-term memory, plan for Graphiti + Neo4j/FalkorDB ops.
- **Mem0 SOTA marketing.** Independent LongMemEval places mem0 (~49%) below Zep/Graphiti (~63–71%). The "SOTA" headline is overstated; for a sales bot it's still the right pragmatic choice, but don't accept their benchmark on faith. Pricing trap: graph features start at **$249/mo Pro** vs $19/mo Standard.
- **Wati's native AI agent.** Limited to PDF/URL knowledge sources (max 50 URLs Pro/Business), no external API/tool integration in the AI agent. The "Astra" upgrade is a separate add-on (~+$100/mo). Use Wati for transport + Zoho-CRM-Marketplace integration only; never as your brain.
- **Twilio AI Assistants** still labeled "Developer Preview / Alpha" in 2026. Do not depend on it as the sole production agent. Twilio Conversations API itself (transport) is rock-solid.
- **AI-SDR vendor scandals.** **11x.ai** under heavy scrutiny: TechCrunch reported inflated ARR practices, ZoomInfo legal action over disputed customer claims, 70–80% churn from former staff, valuation analyses estimating ~$31M true value vs $350M Series B post-money. **Drift / Salesloft** suffered an OAuth-token breach (Aug 2025) propagating into Salesforce/Google Workspace integrations. **Air AI** has 1.5/5 Trustpilot with refund-fraud allegations. Avoid the entire "replace your salesperson" segment.
- **Klarna reversal lesson.** Klarna's CEO publicly admitted the AI-only push optimized cost over quality and is now hybridizing back to humans. *Don't optimize for deflection — optimize for resolution rate, repeat-inquiry rate, CSAT, and quote-to-order conversion.*
- **Baileys-based WhatsApp bots.** Many `whatsapp-ai-` GitHub repos use Baileys (WhatsApp Web reverse-engineered). For B2B at scale this violates WhatsApp ToS and risks number bans. Stay on official WABA via Wazzup/360dialog/Twilio.
- **Voiceflow.** No native WhatsApp (third-party FlowBridge only); BYO LLM gated to Enterprise; recent Trustpilot critical reviews on widget bugs and slow support; the platform itself acknowledges B2C-volume limitations.
- **Flowise acquired by Workday (Aug 2025).** Long-term OSS commitment is now uncertain.
- **Furniture-vertical case-study gap.** Steelcase, Herman Miller, Haworth, and Hoff have **no public LLM sales-agent deployments**. IKEA's "Anna" was shut down for inability to answer direct questions. Don't expect a vertical playbook to copy — use IKEA Billie's *operational* lessons (47% inquiries handled, hybrid with reskilled humans, €1.3B remote-design uplift) and the BCG CPG WhatsApp cases (+11% sales in a month, +25% customer-facing time) as the closest evidentiary anchors.

---

## 9. Search appendix — repositories, docs, threads, papers, benchmarks

### Orchestration frameworks
- LangGraph: https://github.com/langchain-ai/langgraph · case studies: https://docs.langchain.com/oss/python/langgraph/case-studies · WhatsApp tutorial: https://www.twilio.com/en-us/blog/developers/community/how-to-build-a-smart-inventory-chatbot-on-whatsapp-with-langchai · multi-tenant sales template: https://github.com/yerdaulet-damir/langgraph-sales-agent · WhatsApp+LangGraph+Postgres reference: https://github.com/lucasboscatti/Whatsapp-Langgraph-Agent-Integration · LangGraph+MCP+WhatsApp: https://github.com/lgesuellip/langgraph-whatsapp-agent · supervisor: https://github.com/langchain-ai/langgraph-supervisor-py
- Pydantic AI: https://github.com/pydantic/pydantic-ai · 4-framework comparison: https://oss.vstorm.co/blog/same-chat-app-4-frameworks/
- Burr: https://github.com/apache/burr · https://burr.apache.org/ · https://blog.dagworks.io/p/burr-develop-stateful-ai-applications
- OpenAI Agents SDK: https://github.com/openai/openai-agents-python · Temporal integration: https://temporal.io/blog/announcing-openai-agents-sdk-integration
- CrewAI: https://github.com/crewAIInc/crewAI · AG2: https://github.com/ag2ai/ag2 · AutoGen: https://github.com/microsoft/autogen
- Mastra: https://github.com/mastra-ai/mastra · Factorial case: https://mastra.ai/blog/factorial-case-study · Inngest Agent Kit: https://github.com/inngest/agent-kit · Vercel AI SDK: https://github.com/vercel/ai
- DSPy: https://github.com/stanfordnlp/dspy · Atomic Agents: https://github.com/BrainBlend-AI/atomic-agents

### Conversational platforms
- Rasa CALM concepts: https://rasa.com/docs/rasa-pro/calm/ · flows reference: https://rasa.com/docs/rasa-pro/concepts/flows/ · CALM demo: https://github.com/RasaHQ/rasa-calm-demo · CALM-vs-LangGraph head-to-head: https://github.com/RasaHQ/calm-langgraph-customer-service-comparison · pricing pushback: https://forum.rasa.com/t/more-information-about-pricing/64535 · CALM Cookbook (community): https://medium.com/@profrodai/building-the-rasa-calm-cookbook-an-opinionated-guide-for-the-vibecoder-era-0ae93a1dd333
- Parlant: https://github.com/emcie-co/parlant · guidelines: https://www.parlant.io/docs/concepts/customization/guidelines/ · v3.0: https://github.com/emcie-co/parlant/releases · third-party overview: https://skywork.ai/blog/parlant-an-overview/
- Botpress v12: https://github.com/botpress/v12 · review: https://chatimize.com/reviews/botpress/
- Voiceflow critical reviews: https://www.trustpilot.com/review/www.voiceflow.com · Dialogflow CX + LLM critique: https://www.width.ai/post/dialogflow-chatbots-with-llms · Bot Framework → Agents SDK migration: https://learn.microsoft.com/en-us/azure/bot-service/bot-service-overview

### Memory / state
- mem0: https://github.com/mem0ai/mem0 · Zep: https://github.com/getzep/zep · Graphiti: https://github.com/getzep/graphiti · LangMem: https://github.com/langchain-ai/langmem · Letta: https://github.com/letta-ai/letta · Cognee: https://github.com/topoteretes/cognee · Reflexion: https://github.com/noahshinn/reflexion · MemoryBank (AAAI 2024): https://arxiv.org/abs/2305.10250

### WhatsApp transport / commerce
- Wazzup: https://wazzup24.com · Twilio Conversations: https://www.twilio.com/messaging/whatsapp · 360dialog: https://www.360dialog.com · Wati: https://www.wati.io · Respond.io: https://respond.io · Trengo: https://trengo.com · Gallabox: https://gallabox.com · Interakt: https://www.interakt.shop · DoubleTick: https://doubletick.io
- OSS WhatsApp helpdesk: https://github.com/chatwoot/chatwoot · Evolution API: https://github.com/EvolutionAPI/evolution-api · Typebot: https://github.com/baptisteArno/typebot.io
- WhatsApp interactive messaging (Vonage): https://www.vonage.com/resources/articles/whatsapp-interactive-messaging/ · VoltAgent WhatsApp recipe: https://voltagent.dev/recipes-and-guides/whatsapp-ai-agent/ · Towards Data Science WhatsApp+GPT-4o end-to-end: https://towardsdatascience.com/creating-a-whatsapp-ai-agent-with-gpt-4o-f0bc197d2ac0/

### Sales-bot reference repos
- SalesGPT: https://github.com/filip-michalsky/SalesGPT (and LangChain docs cookbook: https://python.langchain.com.cn/docs/use_cases/agents/sales_agent_with_context)
- Customer-support LangGraph: https://github.com/emarco177/langgraph-customer-support · Medical-clinic agent: https://github.com/Nachoeigu/agentic-customer-service-medical-clinic · World Bank WhatsApp RAG: https://github.com/worldbank/WhatsApp-RAG-Example · ChatFAQ (FSM+RAG): https://github.com/ChatFAQ/ChatFAQ · GenAI_Agents reference notebooks: https://github.com/NirDiamant/GenAI_Agents

### Sales playbooks / prompt patterns
- Huthwaite SPIN AI prompts: https://www.huthwaiteinternational.com/blog/ai-spin-prompts · Relevance AI SPIN template: https://relevanceai.com/templates/spin-selling-daa30 · Thinkific 60+ ChatGPT sales prompts: https://www.thinkific.com/blog/chatgpt-for-sales/
- Momentum MEDDPICC prompt: https://www.momentum.io/prompts/meddpicc-call-review-prompt · Oliv MEDDIC: https://www.oliv.ai/blog/meddic-sales-methodology · Coffee.ai MEDDIC: https://www.coffee.ai/articles/meddic-meddpicc-sales-qualification/
- Sandler 20 ChatGPT prompts: https://themcaa.org/wp-content/uploads/protected/Sandler_ChatGPT_Prompts_for_Salespeople.pdf · Sandler pre-call: https://sandler.com/blog/sandler-hot-take-mark-mcgraw-chatgpt-prompt/
- Challenger overview: https://www.salesenablementcollective.com/what-is-the-challenger-sales-methodology/ · Sales playbook examples (SPIN/Challenger/MEDDIC/Sandler/GAP): https://salesmotion.io/blog/sales-playbook-examples · BANT vs MEDDIC vs SPIN vs Challenger: https://www.saber.app/blog/sales-qualification-frameworks-comparison
- Awesome-prompts: https://github.com/f/awesome-chatgpt-prompts · https://github.com/ai-boost/awesome-prompts · https://github.com/promptslab/Awesome-Prompt-Engineering

### Implementation patterns (FSM + LLM, handoff, confirmation)
- StateFlow paper: https://arxiv.org/abs/2403.11322 · Thinker / SMAG: https://arxiv.org/pdf/2503.21036 · AMOR: https://arxiv.org/pdf/2402.01469 · FASTRIC: https://arxiv.org/pdf/2512.18940 · MooreLLM: https://pypi.org/project/MooreLLM/ · LLM-State-Machine: https://github.com/jsz-05/LLM-State-Machine
- OpenAI Cookbook handoffs: https://developers.openai.com/cookbook/examples/orchestrating_agents · Vida AI 3-layer handoff model: https://vida.io/blog/ai-agent-human-handoff · Escalation protocol: https://tianpan.co/blog/2026-04-10-escalation-protocol-agent-to-human-handoffs · LiveKit voice handoff: https://livekit.com/blog/handoff-pattern-voice-agents · AG2 conditional handoffs: https://docs.ag2.ai/latest/docs/user-guide/advanced-concepts/orchestration/group-chat/handoffs/

### Real-world LLM sales/commerce case studies
- Klarna AI assistant (initial): https://www.klarna.com/international/press/klarna-ai-assistant-handles-two-thirds-of-customer-service-chats-in-its-first-month/ · Klarna reversal post-mortem: https://internative.net/insights/blog/klarna-ai-reversal-postmortem
- IKEA Billie + remote design: https://www.ingka.com/newsroom/ai-and-remote-selling-bring-ikea-design-expertise-to-the-many/ · Billie business case: https://www.robertjuliansmith.com/en/blog/ikea-billie-ai-chatbot-business-case/
- Wildberries AI shopping assistant: https://laotiantimes.com/2025/07/08/wildberries-begins-testing-ai-shopping-assistant-on-its-marketplace/ · Mercado Libre GenAds (AWS): https://aws.amazon.com/solutions/case-studies/mercado-libre-mutt-data/ · Mercado Libre WhatsApp NPS: https://www.qualtrics.com/customers/mercado-libre/
- Yellow.ai furniture brand: https://yellow.ai/case-study/multinational-furniture-brand-drives-seamless-automation-with-zendesk-integration/ · Haptik B2B WhatsApp roundtable: https://www.haptik.ai/blog/roundtable-a-winning-whatsapp-commerce-strategy
- BCG B2B AI agents: https://www.bcg.com/publications/2025/how-ai-agents-will-transform-b2b-sales · BCG emerging-markets sales AI: https://www.bcg.com/publications/2026/how-ai-can-reshape-sales-channels-in-emerging-markets · McKinsey gen-AI in B2B sales: https://www.mckinsey.com/capabilities/growth-marketing-and-sales/our-insights/unlocking-profitable-b2b-growth-through-gen-ai
- Peer-reviewed B2B WhatsApp chatbot field experiment (16,000+ participants): https://www.sciencedirect.com/science/article/abs/pii/S0148296325005041
- Steelcase AI thought leadership: https://www.steelcase.com/research/articles/ai-supercycle/ · Herman Miller × Salesforce relaunch: https://www.salesforce.com/news/press-releases/2021/06/02/herman-miller-redesigns-its-shopping-experience-with-salesforce/

### Benchmarks / evals
- τ-bench: https://github.com/sierra-research/tau-bench · Sierra blog: https://sierra.ai/blog/benchmarking-ai-agents · τ²-bench: https://github.com/sierra-research/tau2-bench · HAL leaderboard: https://hal.cs.princeton.edu/taubench_airline
- Berkeley Function Calling Leaderboard (BFCL): https://gorilla.cs.berkeley.edu/leaderboard.html · AgentBench: https://github.com/THUDM/AgentBench · WildBench: https://arxiv.org/abs/2406.04770 · Chatbot Arena: https://lmarena.ai
- Eval frameworks: G-Eval (in DeepEval) https://github.com/confident-ai/deepeval · Ragas: https://github.com/explodinggradients/ragas · Promptfoo: https://github.com/promptfoo/promptfoo · Langfuse: https://github.com/langfuse/langfuse · Curated index: https://github.com/Vvkmnn/awesome-ai-eval

---

## Conclusion — what changes Monday morning

Stop adding routing rules. The complexity isn't in your prompts; it's in your missing state primitive. **Adopt LangGraph this week, in shadow mode**, behind your existing Wazzup webhook, on a typed `StateGraph` with `PostgresSaver`. Keep every piece that encodes your business: Zoho adapters, КП generator, audit log, operator panel, multilingual templates, Wazzup transport. Run the 1-week PoC with Parlant in parallel — its observation-gated tools and Journey state-diagrams are the strongest *declarative* alternative if your team prefers Python decorators to graph topology. Do **not** evaluate Rasa CALM unless you've already committed budget for the $35k/yr Pro tier; do **not** evaluate CrewAI/AG2/AutoGen for transactional dialogue; do **not** treat any commercial WhatsApp AI agent as a brain — they're transports.

The deepest insight from the evidence: **LLM sales agents demonstrably move B2B numbers** (peer-reviewed +leads/+quality vs landing pages, BCG +11% sales in a month, IKEA Billie €13M savings + €1.3B remote-design uplift, Klarna 700 FTE-equivalent), but **the dominant failure mode in production is optimizing deflection over resolution** (Klarna's public reversal). Instrument resolution rate, repeat-inquiry rate, CSAT, and quote-to-order conversion — not message count. Use BANT + light SPIN + Sandler upfront contract for inbound furniture chats; reserve MEDDPICC for opportunities a human will close. Use WhatsApp interactive lists/buttons for confirmation moments — not free text. Treat manager handoff as a *designed workflow* with serialized state, not an error fallback. Pre-translate every WhatsApp template to EN/RU/AR at approval time; the model handles language naturally, but templates and currency/RTL rendering are your engineering problem.

The Steelcase, Herman Miller, Hoff and Wildberries-furniture vacuum is real — there's a first-mover gap in B2B office furniture LLM agents. The supporting evidence (peer-reviewed B2B WhatsApp lift, IKEA-Billie operational pattern, BCG CPG WhatsApp cases, Klarna's hybrid post-mortem) all point the same way: a hybrid LangGraph-orchestrated, human-augmenting WhatsApp agent built on your existing Zoho stack is both technically de-risked and commercially under-served. Build it, measure resolution not deflection, and ship it.