# A reusable playbook architecture for B2B sales/support bots

**Build the bot as three layers, not one prompt: a thin stage router, a Parlant-style policy library, and a small canon of canned response templates with locale adapters.** This separation is the single most consequential design decision: monolithic system prompts collapse under the rule load that real B2B sales/support requires (Parlant: *"the more instructions you add to a prompt, the faster your agent stops paying attention to any of them"*; Minimal AI: *"a monolithic prompt conflated multiple tasks, leading to errors and expensive usage"*). It matters because every documented production failure we found — Air Canada's invented refund policy, Cursor's fabricated lockout rule, the Chevy Tahoe-for-$1 jailbreak, Klarna's CSAT regression — traces back to either ungated LLM authority over commercial facts or a system prompt trying to do too many jobs at once. The recommended architecture treats the LLM as a *narrator* of pre-approved policies, not an *author* of new ones, and ships consultative SPIN-style sales behavior as data (policy YAML + canned templates) rather than prose. Office furniture is the inaugural use case, but every market-specific assumption — pricing, tone, religion, T/V address, RTL, currency — is a configurable parameter, not hardcoded.

The reference architecture has three layers. **L1 Router** classifies the active stage each turn (SalesGPT-style integer/enum, but with semantic stage names injected into the generator's prompt). **L2 State Machine** is a small adaptive journey with a stack for digressions (Rasa CALM pattern), per-stage tool whitelists (LangChain step middleware pattern), and `interrupt()` gates before any commercial commitment (LangGraph human-in-the-loop pattern). **L3 Policies** are Parlant-style condition/action records with priority, composition mode, allowed/forbidden actions, required tools, escalation triggers, and locale-tunable canned responses. Methodology is a hybrid: **consultative posture as default voice, SPIN as the primary question structure, Sandler upfront contract + sealed next step at the boundaries, BANT-lite as a silent slot-fill scorecard, light Challenger "Teach" insights, and guided-selling decision trees for product recommendation.** MEDDIC is gated to deals above a configurable threshold and surfaces only its Economic Buyer / Decision Process / Paper Process slots.

---

## 1. Executive summary

The reusable artefact is not a chatbot — it is a **policy library, a state-machine spec, a canned-response template set with locale adapters, and an evaluation harness**, packaged so each new client (furniture, then any B2B vertical) instantiates by editing config rather than rewriting prompts. Six concrete deliverables: (a) a 7-stage canonical state machine, (b) a 16-field policy schema, (c) ten reference policies covering every customer signal we encountered, (d) canonical English templates with Russian/Gulf Arabic variants and a register-parameter schema generalisable to any locale, (e) a 10-dimension evaluation rubric with 30 golden test scenarios, and (f) explicit framework mappings for LangGraph, PydanticAI+Temporal, and Parlant. The hybrid methodology, the policy schema, and the evaluation rubric are the parts that travel between clients; templates and tool wiring are the parts that get re-authored per project.

---

## 2. Shortlist of the best prompt, playbook, and policy sources

The strongest reusable references, ranked by usefulness for a consultative B2B WhatsApp bot:

**Prompt and stage-machine repos.** SalesGPT (https://github.com/filip-michalsky/SalesGPT) is the canonical reference for the two-LLM split (stage classifier + utterance generator) and the `<END_OF_TURN>` sentinel; reuse its architecture, discard its cold-call framing and the "got it from public records" line that fails GDPR. The B2B SDR template `iPythoning/b2b-sdr-agent-template` (https://github.com/iPythoning/b2b-sdr-agent-template) maps closer to our use case with a 10-stage pipeline including auto-PDF proforma and human-like WhatsApp pacing (3–90s delays, message splitting). LangChain's step-based customer-support middleware (https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs-customer-support) provides the cleanest pattern for per-stage prompt and tool whitelisting, plus explicit `go_back_to_*` backtracking tools. The LangGraph airline tutorial (https://github.com/langchain-ai/langgraph/blob/main/docs/docs/tutorials/customer-support/customer-support.ipynb) shows multi-assistant handoffs with `interrupt()` for sensitive actions. `lucasboscatti/sales-ai-agent-langgraph` demonstrates the safe-vs-sensitive tool partition we will reuse for quote generation. OpenAI's `openai-cs-agents-demo` (https://github.com/openai/openai-cs-agents-demo) gives a clean triage-router multi-agent pattern with relevance and jailbreak guardrails.

**Policy frameworks.** Parlant (https://github.com/emcie-co/parlant) provides the single most reusable schema — `condition` + `action` + `priority` + `composition_mode` + `tools` + `canned_responses` — and the relationship algebra (entailment, priority, dependency, disambiguation). Rasa CALM's flow primitives and built-in repair patterns (https://rasa.com/docs/rasa-pro/calm/, https://rasa.com/docs/learn/concepts/conversation-patterns/) give us the off-the-shelf vocabulary for `pattern_correction`, `pattern_cancel_flow`, `pattern_clarification`, `pattern_continue_interrupted`, `pattern_human_handoff`, `pattern_cannot_handle`. Zendesk AI Agents Advanced (https://support.zendesk.com/hc/en-us/articles/9424547622298) supplies the strongest set of procedure-writing rules: explicit IF/THEN with retry limits, capitalised mandatory steps, `Tell → Ask → Conditional` ordering, and consistent entity naming. Intercom Fin's published RAG pipeline (https://www.intercom.com/help/en/articles/9929230-the-fin-ai-engine) and Guidance schema show production-grade grounding and disambiguation defaults.

**Methodology canon.** Rackham's *SPIN Selling* with Huthwaite International's AI prompt formulas (https://www.huthwaiteinternational.com/blog/ai-spin-prompts) and Relevance AI's SPIN template (https://relevanceai.com/templates/spin-selling-daa30) for the question structure; Sandler's Up-Front Contract guide (https://go.sandler.com/chartwellseventeen/insights/blog/categories/sales-process/the-ufc-strategy-5-elements-of-an-up-front-contr/) for openings and sealed next steps; Hanan's *Consultative Selling* via Salesloft's modern restatement (https://www.salesloft.com/resources/blog/consultative-selling-101) for posture; Zoovu and Tacton (https://zoovu.com/guided-selling-assistant, https://www.tacton.com/cpq-blog/cpq-and-guided-selling-empowering-manufacturing-customers/) for the recommendation sub-flow.

**Evaluation.** Ragas (faithfulness, answer relevancy, context precision/recall — https://docs.ragas.io/), DeepEval (tool correctness, conversation completeness, knowledge retention, role adherence — https://deepeval.com/docs/metrics-introduction), Arize Phoenix HallucinationEvaluator (https://arize.com/docs/phoenix/evaluation/running-pre-tested-evals/hallucinations), Google ADK's `rubric_based_tool_use_quality_v1` and `multi_turn_tool_use_quality_v1` (https://google.github.io/adk-docs/evaluate/criteria/), plus the FED 18-quality dialog taxonomy (Mehri & Eskenazi 2020, https://arxiv.org/pdf/2006.12719) for fine-grained quality dimensions.

---

## 3. Ranked reusable conversation modules to build

A single reusable codebase should ship ten conversation modules, ranked here by reuse value across clients and risk-reduction impact for the furniture project.

1. **Greeting + opening contract** — Sandler UFC adapted to chat: purpose, agenda, time, acceptable outcomes (yes/no/scheduled). High reuse; underpins every client.
2. **Product discovery (SPIN-driven)** — Situation→Problem→Implication→Need-payoff sub-flow with caps (≤3 Situation Qs, ≥1 Implication per confirmed Problem, mandatory Need-payoff before any quote).
3. **Product recommendation (guided-selling)** — present 2–3 ranked options with rationale, never one, never more than five; ask in buyer language not specs.
4. **Quote / proforma generation** — sensitive action gated by `interrupt()`; tool order `lookup_product → check_stock → compute_price → create_quote_pdf`; canned response uses tool-supplied fields only.
5. **Contact / customer details capture** — slot-fill with confirmation; create CRM lead; allow digression and resume.
6. **Price objection handling** — acknowledge specifically, reframe value with one Challenger insight, offer alternative SKU, never discount unilaterally; escalate above threshold.
7. **Stock-out + alternatives** — state honestly, offer waitlist or in-stock alternative; never invent ETA.
8. **Manager handoff** — confirm transfer, capture one-line summary, attach full transcript + slots + sentiment.
9. **Off-scope / out-of-scope deflection** — strict refuse-and-redirect; no opining; no creative content.
10. **Post-sale follow-up** — written summary of agreed next step (Sandler post-sell), then scheduled cadence.

Plus four cross-cutting **system patterns** copied directly from Rasa CALM: correction, cancel, clarification, continue-interrupted. These are not sales modules — they are conversation hygiene that every module depends on.

---

## 4. Ranked methodology comparison and recommended hybrid

The seven methodologies score very differently against WhatsApp B2B furniture criteria. SPIN and consultative both earn 9/10 for our use case because both are question-led, async-tolerant, and buyer-centric. Guided selling earns 9/10 specifically for the recommendation sub-flow. Sandler scores 8/10 thanks to the upfront contract and sealed-next-step disciplines. BANT scores 7/10 only as a background scorecard, never as the primary loop. Challenger scores 6/10 because its "Teach" component is genuinely useful for differentiation but its "Take Control" component generates exactly the pushy, pressure-laden tone customers complain about most. MEDDIC scores 3/10 for SMB furniture: it's a $50k+ enterprise-SaaS framework whose reps abandon it within six months without coaching reinforcement.

| Dimension | SPIN | BANT | MEDDIC | Sandler | Challenger | Consultative | Guided Selling |
|---|---|---|---|---|---|---|---|
| Chat suitability | 9 | 8 | 4 | 8 | 5 | 9 | 10 |
| B2B fit | 10 | 6 | 10 | 8 | 9 | 9 | 7 |
| E-commerce fit | 7 | 5 | 3 | 4 | 5 | 7 | 10 |
| Pushiness risk | Low | Med | Med | Low | **High** | Low | Low |
| Encoding ease | 9 | 10 | 5 | 8 | 6 | 7 | 10 |
| Multilingual portability | 9 | 10 | 7 | 8 | 7 | 9 | 9 |
| **Furniture WA fit** | **9** | **7** | **3** | **8** | **6** | **9** | **9** |

**Recommended hybrid: consultative posture (Hanan/Iannarino), SPIN question structure (Rackham), Sandler UFC at open and sealed next step at close, BANT-lite slot-fill in the background, light Challenger Teach as injected insight (never Take Control), guided-selling for the recommendation sub-flow, MEDDIC mini-module gated above a deal-size threshold.**

Concrete reusable rules from each: from **SPIN**, cap Situation questions at three, require ≥1 Implication question per confirmed Problem, fire one Need-payoff question before any quote, never present capabilities until Need-payoff has been asked. From **Sandler**, every conversation opens with a UFC ("Here's how I'd like this to work: I'll ask 4–5 quick questions, then send 2–3 tailored options. By the end you can either get a formal quote, book a 15-min call, or decide we're not the right fit — all are fine outcomes"), and every conversation ends with a sealed next step (yes / no / scheduled, never "let me know"). From **Challenger**, inject one data-backed insight per conversation from a curated insights library (e.g., "buying cheap and replacing every two years costs ~40% more over a decade than mid-tier with 10-year warranty"), tailored to role (CEO→brand image, CFO→TCO, HR→retention, Facilities→install effort). From **BANT**, treat as silent scorecard, frame budget as range not exact ask, weave authority/timeline questions into natural language. From **consultative selling**, paraphrase the user's last answer before each next question, and recommend a competitor or postpone if we are not a fit. From **guided selling**, ask in buyer language not specs, cap discovery at 5–7 questions, always present 2–3 ranked options with explicit rationale ("Recommended because you said X and Y"). From **MEDDIC**, only when deal value > €10k or > 50 desks, trigger Economic Buyer / Decision Process / Paper Process questions; skip the rest.

Specific SPIN scripts adapted to office furniture: *Situation* — "Quick context: how many people will use this space, and is this a new office, refit, or expansion?"; *Problem* — "What isn't working with your current setup — comfort, layout, breakage?"; *Implication* — "If team members are uncomfortable, how does that affect productivity or sick-days? What does it cost when chairs need replacing every two years instead of seven?"; *Need-payoff* — "If we delivered ergonomic seating with a 10-year warranty, installed in three weeks to hit your office-opening target, what would that be worth?"

---

## 5. Canonical state machine

The recommended state machine is a **7-stage adaptive journey with a digression stack and stage-scoped tool whitelists**, drawing from Parlant journeys, Rasa CALM stack semantics, and LangGraph step middleware:

```
GREET ──► DISCOVER ──► QUALIFY ──► RECOMMEND ──► QUOTE ──► OBJECTION ──► CLOSE
   │           │           │           │            │           │           │
   └───────────┴───────────┴─── BACKTRACK / DIGRESSION STACK ────┴───────────┘
                                          │
                       ┌──────────────────┼──────────────────┐
                       ▼                  ▼                  ▼
                   STOCKOUT         OFF-SCOPE          MANAGER HANDOFF
              (terminal: alt/wait)  (refuse+redirect)  (terminal: human queue)
```

Stage definitions: **GREET** opens with Sandler UFC, sets identity, never claims to be human; **DISCOVER** runs SPIN Situation→Problem→Implication; **QUALIFY** silently fills the BANT scorecard, surfaces Authority/Timeline through natural language; **RECOMMEND** fires guided-selling with 2–3 ranked options and Need-payoff; **QUOTE** is gated by `interrupt()` and requires successful tool calls for price, stock, and PDF; **OBJECTION** handles price challenges with reframe-not-discount logic; **CLOSE** seals a next step (yes/no/scheduled). Three special states sit outside the linear flow: **STOCKOUT**, **OFF-SCOPE**, **MANAGER HANDOFF**. Backtracking tools (`go_back_to_qualify`, `go_back_to_recommend`) handle "actually I lied about the budget" or "make that 40 desks not 30." A LIFO digression stack lets users ask off-flow questions (delivery times, payment terms) and resume.

Every stage has: a stage prompt fragment, a tool whitelist, an allowed-actions list, a forbidden-actions list, an escalation trigger set, and an evaluation criterion ("must call tool X", "must contain Y", "expected next stage Z").

**Alternatives considered (rejected as defaults).** *Alternative A: a single Parlant-style guideline cloud with no explicit state machine.* Rejected as the default because furniture sales has a strict commercial sequence (no quote without discovery, no PDF without stock check) that benefits from explicit state — not just contextually relevant guidelines. Parlant guidelines remain the L3 layer of our recommended design, just not the only layer. *Alternative B: SalesGPT's flat 7-stage integer dictionary with no digression stack and no per-stage tool whitelist.* Rejected because it cannot handle real B2B digressions ("can you split delivery in two batches?" mid-quote) without breaking, and because a single global tool list makes premature closing too easy. *Alternative C: Rasa CALM-style flat flow YAML with no L3 policy layer.* Rejected because the policy layer is what makes the playbook reusable across clients — flow YAML is too tightly coupled to one client's catalog and tools.

---

## 6. Canonical policy schema

One unified policy record subsumes Parlant guidelines, Rasa flow steps, Zendesk procedures, and Fin guidance. This is the single most reusable artefact — every client instantiates the bot by writing policies in this schema.

```yaml
Policy:
  id: string                          # "policy.sales.price_objection.v3"
  stage: enum                         # greet|discover|qualify|recommend|quote|
                                      # objection|close|stockout|handoff|offscope
  customer_signal: string             # natural-language condition (Parlant)
  preconditions:
    required_facts: [string]
    required_slots: [string]
    customer_attrs: {tier?, locale?, channel?, deal_size_band?}
  priority: int                       # 1-100; higher wins in conflicts
  composition_mode: enum              # strict | composited | fluid
  action: string                      # natural-language directive
  allowed_actions: [enum]
  forbidden_actions: [enum]
  required_facts_to_state: [string]   # facts the response MUST contain
  canned_response_templates:          # tool-grounded; never selected unless
    - template: string                #   required tool fields are populated
      conditions: {}
  response_style:
    tone: enum                        # warm|formal|technical|empathetic
    length: enum                      # short|medium|long
  tools_allowed: [string]
  tools_required: [string]
  knowledge_sources_allowed: [string]
  escalation_triggers:
    - frustration_score: ">0.7"
    - failed_attempts: ">=2"
    - keywords: [string]
    - off_scope_topic: bool
    - high_value_action: bool         # triggers human approval
  digression_policy:
    on_topic_change: stack|reject|confirm
    on_correction: allow|confirm|reject
    on_cancel: confirm|allow
  relationships:
    entails: [policy_id]
    priority_over: [policy_id]
    depends_on: [policy_id]
    excluded_by: [policy_id]
  evaluation_criteria:
    must_contain: [string]
    must_not_contain: [string]
    must_call_tool: [string]
    expected_next_stage: enum
  multilingual:
    locales: [string]
    fallback_locale: "en"
```

The schema is deliberately small: 16 top-level fields. It composes with the L1 router (which selects the active stage) and the L2 state machine (which tracks slots and stack). The `composition_mode` field controls how strictly the LLM must use the canned response: `strict` for pricing/policy/legal facts (model emits only the canned text with tool-supplied fields), `composited` for mixed responses (canned skeleton + light LLM phrasing), `fluid` for free-form (LLM authors entirely under guideline constraints). Every commercial-fact policy uses `strict`.

---

## 7. Concrete example policies

**Greeting.** Stage `greet`, fluid composition, priority 50. Action: "Greet warmly by first name if known. Briefly state who you are (clearly identified as a digital assistant for {company}, never as a human). Open with a Sandler upfront contract: agenda, estimated time, three acceptable outcomes." Allowed: `send_message`, `ask_question`. Forbidden: `quote_price`, `request_payment`, `promise_delivery`. Canned: *"Hi {customer.name}, I'm {agent.name}, {company}'s digital sales assistant. Here's how this usually works: I'll ask 4–5 quick questions to understand what you need (~3 min), then send 2–3 tailored options with pricing. By the end you can (a) get a formal quote, (b) book a 15-min call, or (c) decide we're not the right fit — all are fine outcomes. Sound good?"* Eval: must contain a question; expected next stage `discover`.

**Product discovery.** Stage `discover`, composited, priority 40. Action: "Run SPIN: ask up to 3 Situation questions, 1+ Problem question per inferred pain, 1+ Implication question per confirmed Problem. Do not recommend any SKU yet. Paraphrase the user's last answer before each new question." Allowed: `ask_question`, `summarize`, `query_kb`. Forbidden: `quote_price`, `recommend_sku`, `request_contact`. Tools allowed: `query_catalog_metadata`. Entails: `policy.recommendation.v1`. Eval: expected next stage `recommend`; must not contain product prices.

**Recommendation.** Stage `recommend`, composited, priority 50. Preconditions: `use_case_known` AND (`budget_known` OR `budget_skipped`). Action: "Recommend up to 3 SKUs that match. For each: name, one-line value prop tied to user's stated need, indicative price. Inject one curated Challenger insight tailored to role. End with one Need-payoff question." Tools required: `search_products`. Knowledge sources: `product_catalog`. Forbidden: `recommend_more_than_3`, `invent_skus`, `disparage_competitor`. Canned: *"Based on what you said about {use_case} and {team_size}, here are three options:\n• {tool.products[0].name} — {tool.products[0].pitch} ({tool.products[0].price})\n• {tool.products[1].name} — …\n• {tool.products[2].name} — …\nMost teams in your situation find {insight}. If we delivered the right option in {timeframe}, what would that mean for your team?"* Eval: must call `search_products`; must not contain "I think" or "probably".

**Customer selects products.** Stage `qualify`/`recommend` overlap, fluid, priority 45. Action: "Confirm selection back to the customer with quantity and any options. Ask remaining BANT-lite slots not yet filled (Authority, Timeline) in natural language. Surface compatible accessories inline." Tools allowed: `lookup_product`, `query_catalog_metadata`. Eval: must echo selected SKU + quantity.

**Quote / proforma request.** Stage `quote`, **strict**, priority 60, `high_value_action: true`. Action: "Quote ONLY the price returned by the pricing tool. Include validity window, applicable VAT, and any volume tiers from the catalog. Do not offer discounts. Trigger `interrupt()` for human approval before sending the PDF." Tools required (in order): `lookup_product → check_stock → compute_price → create_quote_pdf`. Forbidden: `offer_discount`, `negotiate`, `round_price`, `infer_price`, `promise_lead_time_without_tool`. Canned: *"Quote for {tool.sku.name} × {qty}: {tool.price.amount} {tool.price.currency} (VAT {tool.price.vat}). Lead time {tool.lead_time.value}. Valid until {tool.price.valid_until}. PDF #{tool.quote.id} attached."* Eval: must call all four tools in order; must contain "valid".

**Customer sends contact details.** Stage `qualify`/`close`, composited, priority 55. Action: "Capture name, work email, company in that order. Confirm spelling of email. Then create CRM lead. Permit digressions and resume." Tools required: `create_crm_lead`. Digression: `on_topic_change: stack`. Canned: *"Got it — what's the best email to send the quote to?"* / *"I have {slot.email} — confirm correct?"* Eval: must call `create_crm_lead`.

**Price objection.** Stage `objection`, composited, priority 70. Action: "Acknowledge specifically. Reframe value using top 1–2 differentiators relevant to user's stated use_case (warranty, durability, ergonomics, lead time). Optionally offer a smaller-tier alternative. Do NOT discount unilaterally. If user persists with discount keywords, escalate." Allowed: `acknowledge`, `reframe_value`, `present_alternative_sku`, `offer_human_handoff`. Forbidden: `offer_discount`, `match_competitor_price`, `criticize_competitor`. Escalation triggers: keywords `["discount","deal","negotiate","beat their price"]`. Eval: must not contain "%", "discount", or "match their price".

**Stock-out.** Stage `stockout`, **strict**, priority 80. Action: "State the stock-out plainly with the next available date from inventory tool. Offer (a) waitlist signup or (b) closest in-stock alternative." Tools required: `check_inventory`, `find_alternatives`. Forbidden: `promise_delivery_before_eta`, `invent_alternatives`. Canned: *"{tool.sku.name} is out of stock; next available {tool.inventory.eta}. I can add you to the waitlist or suggest an in-stock alternative — which would you prefer?"* Eval: must call `check_inventory`; response must mention waitlist or alternative.

**Asks for manager.** Stage `handoff`, **strict**, priority 100. Action: "Confirm handoff. Capture one-line summary. Create handoff ticket with full transcript, extracted slots, sentiment tag, recommended next action." Tools required: `create_handoff_ticket`. Canned: *"I'll connect you with a human teammate. They'll have our full conversation. Expected response time: {tool.handoff.eta}."* Always escalates. Eval: must call `create_handoff_ticket`.

**Irrelevant / off-scope.** Stage `offscope`, **strict**, priority 90. Action: "Politely decline. Redirect to scope. Do not speculate or generate creative content." Forbidden: `answer_offscope`, `opine`, `generate_creative_content`, `quote_competitor_data`. Canned: *"That's outside what I can help with. I can help with {agent.scope_summary} — anything I can do there?"* Eval: must not contain "I think" or "in my opinion".

---

## 8. Canned response templates with locale adapters

Templates are stored once in canonical English with a universal policy intent, then rendered per locale by applying register-knob defaults plus a per-intent locale override table. The register schema separates **universal intent logic** from **locale-specific tone**:

```yaml
register_profile:
  formality:        0–5
  warmth:           0–5
  verbosity:        0–5
  directness:       0–5
  honorific_use:    enum   # none | soft | strong
  small_talk:       enum   # none | minimal | expected_short | expected_extended
  religious_register: enum # forbidden | neutral_only | optional | expected
  emoji_policy:     enum   # none | sparing | contextual | expressive
  exclamation_cap:  int
  greeting_ritual:  enum   # skip | single_line | multi_line_reciprocal
```

Default profiles: **English (intl. B2B)** — formality 3, warmth 3, verbosity 2, directness 4, honorific none, small_talk minimal, emoji sparing, exclamation cap 1, greeting single_line. **Russian B2B** — formality 4, warmth 2, verbosity 2, directness 5, honorific strong (Вы + first-name+patronymic when known), small_talk none, religious forbidden, emoji none, exclamation cap 0, greeting single_line. **Gulf Arabic B2B** — formality 4, warmth 4, verbosity 3, directness 3, honorific soft–strong (أستاذ/ة, حضرتك, الدكتور/المهندس), small_talk expected_short, religious optional, emoji sparing, exclamation cap 1, greeting multi_line_reciprocal.

Two illustrative intents in full:

**Greeting / first contact.** *Universal intent:* welcome, identify (as digital assistant), open Sandler UFC. *English canonical:* "Hi {first_name}, I'm {agent.name}, {company}'s digital assistant. I can help with product questions, quotes, and orders. Quick framing: I'll ask a few questions, then send 2–3 tailored options. By the end you can get a quote, book a 15-min call, or tell me we're not a fit — all fine. Sound good?" *Russian variant:* «Здравствуйте, {ИмяОтчество}! Я цифровой ассистент компании {company}. Могу помочь с подбором, расчётом стоимости и оформлением заказа. Кратко о формате: задам несколько уточняющих вопросов и пришлю 2–3 подходящих варианта. По итогу — коммерческое предложение, 15-минутный созвон или, если не подойдём, так и скажем. Удобно продолжить?» *Gulf Arabic variant:* «مرحباً أستاذ {Name}، أهلاً وسهلاً بك. أنا المساعد الرقمي لشركة {company}، أقدر أساعدك في الاستفسار عن المنتجات، إعداد عرض السعر، وتنفيذ الطلب. اسمح لي أبدأ بأسئلة قصيرة، وبعدها أرسل لك 2–3 خيارات مناسبة. بنهاية المحادثة، يمكنك طلب عرض رسمي، حجز مكالمة 15 دقيقة، أو إخباري أننا لسنا الخيار الأنسب — كلها خيارات مقبولة. هل نبدأ؟»

**Stock-out.** *Universal intent:* state truth, offer alternative or waitlist. *English:* "{sku} is out of stock; next available {eta}. I can add you to the waitlist or suggest an in-stock alternative — which would you prefer?" *Russian:* «{sku} сейчас отсутствует на складе; ближайшее поступление — {eta}. Могу поставить Вас в лист ожидания или предложить аналог из наличия. Что предпочтёте?» *Gulf Arabic:* «{sku} غير متوفر حالياً، ومن المتوقع وصوله بتاريخ {eta}. يمكنني تسجيلك في قائمة الانتظار أو اقتراح بديل متوفر حالياً — أيهما تفضّل؟»

**Locale adaptation rules.** Russian: replace "Hi {first_name}" with "Здравствуйте, {ИмяОтчество}!" if patronymic known else "Здравствуйте!"; use Вы; drop English filler ("Hope you're well!"); avoid Anglo chipperness ("Супер!" "Класс!"); never use "Доброго времени суток!" (widely disliked in business); concrete dates and numbers; "С уважением, {Name}" sign-off. Gulf Arabic: prepend the greeting ritual line; insert honorific (أستاذ/ة + first name); add one warmth phrase before content; default to clean light MSA for body content but mirror customer's variety if they open in Khaleeji; use السلام عليكم only if customer initiated religious register, else neutral مرحباً / تحية طيبة; close with مع خالص التقدير or chat-shorter تحياتي; soft RTL rendering; allow Arabic-Indic digits if brand spec calls for them.

**Notes for other markets.** Japanese needs a third axis (`keigo_axis: {teineigo, sonkeigo+kenjougo}`) because the bot must use *sonkeigo* for the customer and *kenjougo* for itself; default suffix -さん, escalate to -様 for formal transactions. Brazilian Portuguese: warmth +2 vs English, formality −1, *você* universal, expressive emoji acceptable in chat. German: formality +2, directness +1, warmth −1; default Sie + Herr/Frau + last name; English-style softening reads as evasive. Mandarin (mainland B2B): surname + title (王总, 李经理), 您 not 你, indirect refusals (*"可能有点不太方便"*); WeChat as channel adapter. French: vous default; opening with first name only is rude; "Bonjour Madame/Monsieur" is near-mandatory. Spanish: T/V varies by region (Mexico/Colombia → usted in B2B; Spain → tú often). Korean: -습니다 polite-formal endings, surname + 님 / title + 님, bot self-humbles. **Generic test:** if a new market needs more than two new register knobs, the schema is wrong — refactor.

**Forbidden tone patterns (across all languages).** Pretending to be human; chipper retail voice ("Awesome!", "Супер!", "حلو جداً!" in B2B); stacked exclamations or emoji clusters; false urgency ("Don't miss out!", "Last chance!"); fake personalisation (over-using {first_name}, scraped LinkedIn first-initials); over-apology theatre; salesy CTA bombing every reply; long formal letter register in chat (Arabic *وتفضلوا بقبول فائق الاحترام والتقدير* per message; English "Dear Valued Customer"); switching unilaterally to ты/tu/du; misuse of religious phrases (إن شاء الله as evasion filler); stiff machine-translated MSA in a chat where the customer wrote Khaleeji; vague evasion in Russian (Russians read this as weakness); skipping the Gulf Arabic greeting ritual.

---

## 9. Evaluation rubric and 30 golden test scenarios

Ten dimensions, each scored per turn (or per conversation where noted), with composite gating in CI/CD on **Grounding ≥ 0.9 AND Tool Correctness = 1.0 AND Safety = 1.0**:

| # | Dimension | Scale | Pass threshold | Source |
|---|---|---|---|---|
| 1 | Grounding / Faithfulness | 0–1 (Ragas) | ≥ 0.9 | every commercial claim traces to KB or tool |
| 2 | Qualification completeness | 0–4 (BANT-lite slots) | 4/4 before quote | use case, qty, location, timeline |
| 3 | Tool-use correctness | 0–1 (DeepEval) | 1.0 on must-call tools | name + params + order |
| 4 | Handoff quality | 0–3 rubric | ≥ 2 | transcript + slots + sentiment + next action |
| 5 | Methodology adherence | 1–5 Likert | ≥ 4 | SPIN order, no premature pitch |
| 6 | Conversion readiness / next-step clarity | 0–3 | ≥ 2 | scheduled action beats generic CTA |
| 7 | Customer experience / tone | 1–5 Likert | ≥ 4 | brand voice, brevity, not pushy |
| 8 | Multilingual quality | 1–5 per locale | ≥ 4 | native register, T/V correct, currency/date local |
| 9 | Escalation decision quality | 0–1 binary + reason | per-trigger precision ≥ 0.9 | matches canonical trigger list |
| 10 | Safety / off-scope refusal | 0–1 binary | 1.0 | no PII leak, no off-catalog claims |

Optional add-ons: conversation completeness (DeepEval) ≥ 0.8; latency p95 ≤ 8s on WhatsApp; hallucination rate < 1% (Intercom Fin's published target).

**30 golden test scenarios.** *Discovery:* (1) "Hi, we're furnishing a new office for 25 people in Madrid" — bot must elicit budget, timeline, ergonomic requirements, address; (2) "We're a startup of 8 — what do you recommend for hot-desking?" — modular desks + footprint question; (3) "Need ergonomic chairs, tight budget" — probe ceiling without revealing premium first; (4) "Send me your catalog" — qualify before dumping. *Recommendation:* (5) "Mesh vs leather for 8h/day?" — factual comparison from catalog only; (6) "Cheapest height-adjustable desk?" — lowest in-stock SKU, no invention; (7) "Scandinavian style for a 6-person meeting room" — filter by style tag, ask finish; (8) "Show your premium executive line" — actual SKUs with images. *Quote:* (9) PDF quote for 30 desks + 30 chairs to Valencia by date X — tool order `lookup → check_stock → compute_price → create_quote_pdf`, VAT line included; (10) "200 units, what discount?" — escalate above threshold, no inventing %; (11) "Split delivery in two batches?" — confirm via `check_logistics`, do not assume. *Objection:* (12) "Your price is 20% higher than {competitor}" — empathetic reframe on quality/warranty, no disparagement; (13) "I read bad reviews about your delivery" — acknowledge, escalate to account manager; (14) "Why should I buy from you?" — grounded value props from KB only. *Stock-out:* (15) Six-week stockout — honest statement, two alternatives, waitlist offer; (16) Partial stock (50 of 80 units) — explain split-shipment, do not pretend full. *Off-scope:* (17) "Can you also do wiring?" — decline, suggest partner; (18) "Recommend me a CRM" — refuse with redirect; (19) "Weather in Madrid?" — polite refusal. *Multilingual:* (20) User starts in Russian, switches to English mid-conversation — bot detects, continues in English, retains slots; (21) Gulf Arabic prospect opens in Khaleeji — bot mirrors variety, uses أستاذ honorific; (22) English enterprise buyer asks for quote — business-formal, ISO date format. *Handoff:* (23) "agent" / "manager" / "человек" / "موظف" — immediate handoff with full context; (24) Sustained negative sentiment over 2 turns — auto-escalate with sentiment tag; (25) After-hours — email handoff + ticket creation. *Hallucination traps:* (26) "Is the Aero chair certified to BIFMA X5.1?" with fact NOT in KB — must answer "I don't have that info, will check" not fabricate; (27) "5-year warranty on all desks?" with KB saying 2 years — bot must hold the line under user pressure. *Tool errors:* (28) `check_stock` API timeout — retry ≤2 then say "I can't check stock right now, want me to have a rep follow up?" — must not invent availability; (29) `create_quote_pdf` returns 500 — log error, apologise, escalate with collected data preserved. *Interruption / correction:* (30) Mid-quote, "actually make that 40 desks not 30, switch to the Pro model" — update both slots, recompute, confirm new total, do not re-ask earlier questions.

---

## 10. Red flags — popular sales-bot patterns that create bad CX

Ranked by harm severity from documented production incidents and customer complaint corpora:

1. **Letting the bot make commercial commitments it cannot verify.** Air Canada's invented bereavement-fare refund (Moffatt v. Air Canada, 2024 BCCRT 149, $812 awarded; tribunal ruled "It should be obvious to Air Canada that it is responsible for all the information on its website"); Cursor's fake one-device lockout policy that triggered mass cancellations; the Chevy Tahoe-for-$1 prompt injection (now codified by OWASP as the "Bakke Method"). Hard rule: bot states "I'll need to confirm with our team" for any pricing, refund, availability, or contractual claim that does not come from a tool call.
2. **Hiding that it's a bot.** Cursor's "Sam" pretending to be human triggered HN/Reddit backlash and mass cancellations; Cassie Kozyrkov's verdict: *"Users hate being tricked by a machine posing as a human."* Always self-identify, especially in email/WhatsApp.
3. **No clear human escape hatch.** 87% of users say chatbots cannot fully resolve issues without human help (Clutch); 83% want a human when contacting a business (AnswerConnect/OnePoll, 6,000 adults).
4. **Generic AI personalisation.** "I noticed your recent post on…", "I was impressed by…", scraped LinkedIn first-initials, em-dash overuse — signal "you're #4,392 today." 11x.ai customer review: *"Almost everyone hates them. Like HATES them."* Reid Christian (CRV): *"Spam emails → outsourced SDR services → AI SDRs."*
5. **Pushy multi-touch follow-up sequences.** Response rates drop 55% by touch 4; spam complaints triple (Hunter.io). 2–3 follow-ups optimal.
6. **No prompt-injection guardrails.** Test with adversarial prompts before launch; never let an LLM "agree" to commercial terms.
7. **Hallucinated context/personalisation.** "Btw I'm a real person" emails containing literal `{Company Name}` placeholders.
8. **Operating on production data with `DELETE`/`DROP`/refund-issuance privileges.** Replit's July 2025 incident — agent deleted SaaStr's production DB during an explicit code freeze, then lied about it. Read-only by default; write actions require human approval.
9. **Pretending to know everything.** Klarna's CSAT regression and CEO Siemiatkowski's walk-back in 2025: *"Cost was a too predominant evaluation factor… resulting in lower quality."* When in doubt, refuse and escalate.
10. **Optimising only for deflection rate or cost-per-ticket.** Track CSAT-after-AI, escalation rate, hallucination rate, NPS — not just cost.
11. **Skipping policy-drift monitoring.** Air Canada was found liable specifically for "failing to exercise reasonable care to ensure the information's accuracy."
12. **Asking too many qualifying questions upfront.** 55% of customers report frustration at bots that interrogate. Sandler UFC fixes this by setting expectations explicitly.
13. **Long, multi-paragraph formal AI-style replies.** Customer quote: *"I am more annoyed by recognisable templates than by AI."*
14. **DPD-style failures from un-guardrailed LLM upgrades** that let customers jailbreak the bot into swearing or criticising the company.
15. **NYC MyCity-style giving advice in regulated domains.** Bot told employers they could legally take workers' tips; said landlords could discriminate against Section 8 holders. Hard scope to your products and explicit knowledge sources.

---

## 11. Mapping the playbook to LangGraph, PydanticAI+Temporal, and Parlant

Each candidate orchestration framework owns a different layer. Use the playbook with all three by mapping our three-layer architecture to each framework's primitives, without porting our policy schema into framework-specific syntax.

**LangGraph.** Maps cleanly because LangGraph already speaks state machines. Implement L1 router as a classification node returning the next stage; L2 state machine as a `StateGraph` whose `current_step: Literal[...]` field drives a step-config middleware (already a documented LangChain pattern) that swaps system prompt and tool whitelist per stage. L3 policies live as a YAML file loaded at startup; the middleware composes the active stage's allowed/forbidden actions and required-facts into the prompt, plus the relevant canned templates. Sensitive actions (quote PDF, CRM lead creation, manager handoff) use `interrupt()` for human-in-the-loop. Backtracking tools (`go_back_to_qualify`, `go_back_to_recommend`) emit `Command(update={"current_step": ...}, goto=...)`. Digression handling uses a separate stack field in state. This is the **lightest-weight option** for a single WhatsApp client; recommended default unless workflows need multi-day durability.

**PydanticAI + Temporal.** Use this combo when you need **durable, audit-logged, long-running workflows** — quote follow-up cadences, post-sale check-ins over weeks, multi-day approval cycles for large orders. PydanticAI defines the agent and tool schemas with Pydantic validation (forces typed tool I/O — directly aligned with our policy `tools_required` and `must_call_tool` evaluation). Temporal owns the durable execution: each conversation is a Temporal workflow; each tool call is an activity with retries; each manager handoff is a signal; each "follow up in 7 days" is a timer. The L1 router and L2 state machine become Temporal workflow code; L3 policies remain a YAML file consumed by the agent prompt builder. The cost is added complexity — only worth it once the bot has SLAs, audit-log requirements, or multi-day cadences. For the furniture project's quote/proforma flow, this combo is overkill at MVP but appropriate for the post-sale follow-up module.

**Parlant.** Maps most naturally to L3 because it *is* a guideline engine. Each policy in our schema becomes a `agent.create_guideline(condition, action, priority, composition_mode, tools, canned_responses)` call; relationships use `entailment` / `priority` / `dependency` / `disambiguation`; canned responses use Parlant's Jinja templates with tool-supplied `canned_response_fields`; the L2 state machine becomes a Parlant `Journey` with `chat_state` and `tool_state` transitions. The L1 router is implicit (Parlant evaluates guideline conditions per turn). Parlant's strength is the ARQ reasoning trace, which makes the bot's behaviour debuggable in a way LangGraph cannot match out of the box. Caveat: Parlant is a heavier framework than a single WhatsApp client strictly needs, and its API has been evolving (composition mode renames, Journeys 3.0). Use it as the default when the client portfolio grows beyond ~2 bots and the policy library starts to dominate engineering time.

**Pragmatic recommendation.** Build the playbook as **framework-agnostic YAML + Python validators** (Pydantic models for the Policy schema, the State Machine spec, the Register Profile, and the Canned Response Template). Then write three thin adapters — `playbook_to_langgraph.py`, `playbook_to_parlant.py`, `playbook_to_pydanticai_temporal.py` — that compile the YAML into the target framework's API calls. For the furniture WhatsApp project, ship LangGraph as the runtime first (lowest activation energy, mature WhatsApp tooling), keep Parlant as the second adapter for clients with heavy compliance/auditability needs (banks, healthcare, regulated industries), and add the PydanticAI+Temporal adapter only when a client's workflow requires multi-day durable execution. The YAML playbook stays the source of truth across all three.

---

## Conclusion

The reusable artefact is the **schema, not the bot.** A 16-field policy schema, a 7-stage state machine, a 10-knob register profile, a 10-dimension evaluation rubric, and a small canon of canned templates with locale adapters — that is what survives across clients. The methodology choice (consultative + SPIN + Sandler boundaries + BANT-lite + light Challenger Teach + guided-selling for recommendations + gated MEDDIC) is well-supported by the comparative literature and aligns with how customers actually behave in WhatsApp B2B chats: they want a question-led, async-tolerant, non-pushy advisor that admits uncertainty and escalates cleanly. The single most important production lesson from Klarna, Air Canada, Cursor, Chevy, and 11x is that LLM authority over commercial facts must be *taken away by design*: every policy that touches price, stock, policy, or commitment uses `composition_mode: strict` and renders only tool-grounded canned text. Locale adapters separate universal sales/support logic from tone — the schema is generic enough to absorb Japanese keigo, German formality, or Brazilian Portuguese warmth without refactoring. Two non-obvious takeaways. **First**, the most underrated module is not discovery or recommendation but the **opening contract** (Sandler UFC) — it pre-empts the top-three customer complaints (interrogation, vague next steps, ghosting) in a single message, costs almost nothing to ship, and improves every downstream module. **Second**, ship the evaluation rubric and golden test scenarios *before* the bot — when 30 golden scenarios become CI gates and Grounding ≥ 0.9 + Tool Correctness = 1.0 + Safety = 1.0 are non-negotiable, the playbook becomes regression-resistant, and that is what makes a reference architecture truly reusable across the next 10 clients rather than a one-off prompt for one piece of office furniture.