# Референсная архитектура reusable playbooks для AI‑ботов продаж и поддержки

## Исполнительное резюме

Лучший reusable‑подход для вашего reference architecture — не “универсальный супер‑prompt” и не “полностью автономный AI SDR”, а **слоистая разговорная архитектура**:
**channel contract for messaging → reusable repair patterns → consultative sales discovery/qualification → deterministic commercial facts layer → human handoff package → observability/evals**. Именно такая сборка лучше всего соответствует и open‑source находкам, и production‑паттернам из публичной документации: у вас есть отдельно описываемые поведенческие правила, отдельно многошаговые journeys/procedures, отдельно tool gating, отдельно canned/controlled responses для критичных фактов. Это очень близко к тому, как публично структурируют поведение Parlant, Rasa, Botpress, Intercom Fin и Zendesk Advanced AI. citeturn25view0turn25view1turn25view2turn26view0turn30view0turn33view0turn34view0turn34view1

Для WhatsApp B2B‑продаж офисной мебели я бы строил не “продавца, который давит на сделку”, а **consultative commerce concierge**: бот быстро понимает задачу клиента, бережно собирает контекст, рекомендует варианты, хранит selections, делает факт‑чеки по stock/price только через инструменты, затем оформляет quote/proforma или передает разговор менеджеру с полноценным handoff package. Это сильнее совпадает с реальным поведением покупателей в мессенджерах, где короткие, персонализированные и интерактивные сообщения работают лучше длинных монологов, а numeric choices/quick replies особенно полезны в каналах вроде WhatsApp. citeturn12search7turn34view2

По методологии продаж я рекомендую **SPIN/SPICED для discovery**, **BANT + MEDDPICC‑lite для qualification**, **Sandler‑стиль вопросов для мягкого выяснения боли и критериев**, а **Challenger** использовать ограниченно — только после того, как бот уже понял контекст и имеет право на “reframe”, иначе в мессенджере он быстро начинает звучать generic и pushy. SPIN ориентирован на situation/problem/implication/need‑payoff; BANT — на budget/authority/need/timeline; MEDDPICC добавляет metrics, decision criteria/process, economic buyer, pain, champion и paper process; Sandler подчеркивает консультативную роль и ценность открытых вопросов; Challenger — teach, tailor, take control. citeturn2search3turn3search11turn3search12turn3search8turn3search1turn3search9turn3search2turn3search10

Самый важный архитектурный вывод: **не пытайтесь сделать “один agent, который сам все решит”**. Производственные системы, о которых есть сильная публичная документация, выигрывают за счет разложения поведения на управляемые примитивы: guideline/pattern/use case/procedure/dialogue/search rule/entity/attribute/tool/eval. Именно это и нужно превратить в ваш reusable blueprint. citeturn25view0turn26view0turn33view0turn34view0

## Лучшие источники и что из них забирать

Ниже — shortlist источников, которые реально стоит превратить в library of behavior, а не просто “почитать”. Ссылки даны через citations.

**SalesGPT** на entity["company","GitHub","developer platform"] — лучший open‑source skeleton для **sales stage machine**. Репозиторий явно задает стадии вроде Introduction, Qualification, Value Proposition, Needs Analysis, Solution Presentation, Objection Handling, Close и End Conversation; он также показывает tool‑use для product search и оплаты и декларирует работу в texting‑каналах, включая WhatsApp. Но у него слабее проработаны repair patterns, human handoff и production policy discipline, поэтому его стоит использовать как seed для sales progression, а не как конечный blueprint. **Практичность:** высокая. **Reusability:** средняя. **Риск generic/pushy:** средний. **Fit to state machine:** высокий. citeturn22view0turn23view0

**GTM Skills** — один из лучших публичных prompt corpora для B2B GTM: 2,500+ prompts, role packs, industry packs, full workflows и пакеты методологий от MEDDPICC до Challenger и Sandler. Ценность здесь не в том, чтобы брать prompts как runtime‑policy, а в том, чтобы **вытащить from it a taxonomy of modules, buyer signals, question banks, objection archetypes, tonal variants**. Это хороший сырой материал для authoring layer, но слабый runtime control layer. **Практичность:** высокая. **Reusability:** высокая. **Evidence of use:** есть, но в основном self‑reported. **Risk of generic:** высокий, если использовать дословно. citeturn22view1

**Sales Skills for Claude Code** — surprisingly useful не как готовая conversational engine, а как **module map**. В repo явно есть core selling skills, process/strategy skills и особенно полезная категория **AI SDR & Bot Skills**: intent detection, sentiment, conversation memory, compliance handling, handoff detection, summarization, human‑in‑the‑loop training и т. п. Для вашей задачи это почти готовый backlog reusable modules. **Практичность:** высокая. **Ease of translation into structured policies:** высокая. **Evidence of real‑world use:** ограниченное, но структура сильная. citeturn22view2

**Parlant** — самый сильный публичный источник именно для **policy architecture**. Его docs разводят:
guidelines = context‑specific behavioral rules;
journeys = multi‑turn SOPs;
tools = action layer, доступный только по релевантности;
canned responses = deterministic wording for high‑stakes moments;
relationships/criticality/tags = control over applicability and analytics. Для коммерческих фактов, sensitive steps и auditability это почти идеальная mental model. **Практичность:** высокая. **State‑machine compatibility:** очень высокая. **Ease of structured policy translation:** очень высокая. **Multilingual adaptability:** высокая. citeturn24search8turn25view0turn25view1turn24search3turn24search4turn1search6

**Rasa CALM** от entity["company","Rasa","conversational ai software"] — лучший публичный каталог **conversation repair patterns**. Документация прямо выделяет correction, clarification, interruption, cancellation, restart, search, human handoff, fallback/error patterns; dialogue understanding выдает не свободный текст, а команды вроде `start flow`, `set slot`, `clarify`, `human handoff`, `knowledge answer`. Это очень ценно для вашей reusable support layer и для golden tests. **Практичность:** очень высокая. **Reusability across industries:** очень высокая. **Risk of sounding generic:** низкий, если тексты брендуются. citeturn26view0turn26view1turn26view2

**Botpress** от entity["company","Botpress","ai agent platform"] — полезен как reference для **prompt scaffolding inside workflow nodes**. Их Autonomous Node docs дают сильный шаблон: Identity, Scope, Response Style, Guardrails, Greeting, Escalation, Closing, plus explicit variable/tool permissions; отдельно docs на controlled workflows, HITL и Policy Agent показывают, как выводить sensitive tasks из LLM‑режима в deterministic flows. **Практичность для WhatsApp:** высокая. **Ease of translation into structured policies:** высокая. **Risk of hallucinating commercial facts:** низкий, если critical steps выводить в controlled workflows. citeturn30view0turn30view1turn31search1turn31search0turn32view0

**Intercom Fin** от entity["company","Intercom","customer service software"] — самый сильный production‑quality набор публичных support patterns. У Fin публично описаны multi‑source knowledge grounding, policies/guidance, attributes for routing/reporting, procedures with natural language + branching logic + system access, default escalation on frustration/human request/repetitive loop, simulations for pass/fail testing и 45+ languages. Если Parlant — лучший authoring mental model, то Intercom — лучший **operating model** для “train → test → deploy → analyze”. **Практичность:** очень высокая. **Evidence of use:** очень высокая. **Multilingual:** высокая. **State‑machine fit:** высокая. citeturn33view1turn33view0turn33view2turn33view3turn16view3

**Zendesk Advanced AI** от entity["company","Zendesk","customer service software"] — лучший публичный материал для **knowledge scoping, use-case routing and entity/session engineering**. Особенно полезны их use cases как “conversational IVR”, search rules для выбора конкретных knowledge sources/segments, entities для extraction/PII/validation и примечание про multilingual numeric lists в WhatsApp‑подобных каналах. Это именно то, что нужно для ваших flows around pricing, stock, contact capture и route‑to‑manager. **Практичность:** очень высокая. **Risk of hallucination:** низкий при хорошем scoping. **Ease of structured translation:** высокая. citeturn34view0turn34view1turn34view2turn34view3

**LangSmith / Phoenix** — сильнейшая публичная связка для **evaluation design**. LangSmith публично различает reference‑free vs reference‑based evaluators, trajectory evaluation, online/offline evaluation и evaluator rubrics. Phoenix дает готовые evaluators для tool selection, tool invocation, tool response handling, faithfulness и correctness. Это почти готовая матрица для ваших “sales quality”, “grounding”, “tool correctness” и “handoff quality” scores. **Практичность:** очень высокая. **Reusability:** очень высокая. **Evidence of production fit:** высокая. citeturn11search2turn11search4turn11search6turn11search8turn11search9turn10search0turn10search1turn10search3turn10search6

**Conversica Answers** — не лучший общий framework, но очень полезный источник практических микро‑правил: короткие message lengths by channel, FAQ answers with confidence selection, one‑question discipline, explicit guidance on avoiding spam triggers, multi‑language handling и safe wording for “Are you an AI?”, pricing, demo, next steps. Это стоит украсть для canned responses и localization discipline. **Практичность:** средняя. **Value as prompt module source:** высокая. **Risk of genericness:** средний. citeturn21search0turn21search1

Главный общий вывод по shortlist: **открытое сообщество дало хорошие prompt corpora и demo state machines, а наиболее mature behavior rules сегодня публичнее всего описаны в vendor docs support/CX‑систем**. Я не нашел одного open‑source артефакта, который уже содержал бы одновременно production‑grade repair patterns, deterministic commercial fact gating, quote/proforma capture и multilingual handoff package; это нужно собрать самим из нескольких источников. citeturn22view0turn22view1turn22view2turn25view0turn26view0turn33view0turn34view0

## Каноническая модульная архитектура и state machine

### Ранжированный backlog reusable conversation modules

Если собрать backlog модулей в порядке влияния на качество и reuse, я бы ранжировал его так:

1. **Opening contract and router** — language detection, scope statement, offer of help, fast routing into sales/support/off‑scope/human.
2. **Clarification, correction, interruption and recovery patterns** — must be global overlays, not local hacks.
3. **Discovery and qualification** — SPIN/SPICED discovery + BANT/MEDDPICC‑lite slots.
4. **Recommendation engine dialogue** — asks for constraints before recommending.
5. **Comparison and shortlist memory** — “you liked A, B, not C”.
6. **Commercial facts gate** — stock, price, lead time, promo, logistics only through tools/approved sources.
7. **Selection memory and cart‑like state** — preserve chosen products, quantities, finishes, delivery needs.
8. **Quote/proforma capture** — collect exactly the missing fields, then confirm, then generate.
9. **Price objection and budget reframing** — lower pressure, more options, bundles, trade‑offs.
10. **Stock‑out alternatives** — substitutes, lead times, mix‑and‑match, manager escalation rules.
11. **Logistics and installation clarification** — address delivery address, floor, assembly, deadlines, VAT/company detail requirements.
12. **Human manager handoff** — summary, selected items, open questions, urgency, language, sentiment.
13. **Post‑sale follow‑up** — quote reminder, changes requested, delivery status, satisfaction check.
14. **Off‑scope / irrelevant / unsafe request** — polite boundary + redirect.

Такой порядок хорошо согласуется с тем, как Parlant делит fast rules vs journeys, как Rasa выделяет repair patterns, как Intercom и Zendesk разводят routing/use cases/procedures, и как SalesGPT/GTM prompt libraries структурируют selling steps. citeturn25view0turn25view1turn26view0turn33view0turn34view0turn23view0turn22view1

### Каноническая state machine для reference bot

Ниже — state machine, который я бы сделал **каноническим** для reusable sales/support assistant. Это не rigid script; это **primary journey + global interrupt layers**.

```text
NEW_CONVERSATION
  -> LANGUAGE_AND_SCOPE
  -> TRIAGE
      -> SALES_DISCOVERY
          -> QUALIFICATION_PROGRESSIVE
          -> RECOMMENDATION
          -> COMPARISON
          -> SELECTION_MEMORY
          -> COMMERCIAL_FACT_CHECK
          -> QUOTE_CAPTURE
          -> QUOTE_CONFIRMATION
          -> DOCUMENT_GENERATION
          -> FOLLOW_UP_OR_HANDOFF
      -> SUPPORT_INTAKE
          -> ISSUE_CLASSIFICATION
          -> KNOWLEDGE_ANSWER
          -> SECURE_LOOKUP_OR_ACTION
          -> RESOLUTION_CHECK
          -> HANDOFF_OR_CLOSE
      -> HUMAN_REQUESTED
      -> OFF_SCOPE

GLOBAL_OVERLAYS
  - clarification
  - correction
  - interruption/topic switch
  - fallback / cannot-handle
  - frustration detection
  - multilingual switching
  - compliance / pricing / stock truth gate
  - audit labeling
```

Почему именно так:

- **Triage** должен быть early and cheap: многие systems выигрывают не потому, что “умнее отвечают”, а потому, что быстро понимают, какой use case активировать. Это прямо видно и у Rasa’s flows/commands, и у Zendesk use cases, и у Intercom attributes/routing. citeturn26view2turn34view0turn33view2
- **Repair patterns должны быть orthogonal**, а не зашиты в каждый business flow. Это core idea у Rasa patterns и у adaptive procedures/journeys в Intercom/Parlant. citeturn26view0turn33view0turn25view1
- **Commercial facts** нельзя смешивать с free‑form persuasion. Stock, price, delivery window, payment terms и document generation должны идти через scoped knowledge, tools и, где нужно, canned/controlled wording. citeturn24search3turn24search4turn33view3turn34view1

### Что особенно важно для WhatsApp B2B furniture

Для мессенджера важно не просто “state”, а **message granularity**: один turn = одна цель, максимум один‑два вопроса, короткие блоки, опции в виде buttons/numbered choices, visible memory of selections, and rapid escalation if context becomes expensive. Публичные messaging best practices предупреждают против длинных one‑way messages и рекомендуют short, personalized, interactive replies. Zendesk отдельно отмечает для WhatsApp‑подобных каналов важность multilingual entity lists для numeric options. citeturn12search7turn34view2

## Схема политик и примеры политик

Лучший переносимый формат для вашего blueprint — **framework‑agnostic policy schema**, которую потом можно маппить в Parlant guidelines/journeys/canned responses, в LangGraph nodes/edges, в Botpress instructions/workflows или в Rasa flows/pattern overrides. На schema level он должен явно различать signal, stage, allowed/forbidden actions, facts, tools, style and eval checks. Это следует из Parlant’s guideline/journey split, Rasa command/pattern model, Zendesk use case + entity + search rule design и Intercom procedures/guidance/escalation logic. citeturn25view0turn25view1turn26view2turn34view0turn34view1turn33view3

### Предлагаемая canonical policy schema

```yaml
policy_id: string
intent_family: sales | support | handoff | fallback | off_scope
stage: string
customer_signal:
  - phrase_or_semantic_condition
  - optional_entity_or_attribute_conditions
required_facts:
  - fact_name
missing_fact_strategy: ask_one_by_one | ask_batch | tool_lookup | escalate
allowed_actions:
  - ask_question
  - summarize
  - recommend
  - compare
  - call_tool:<tool_name>
  - save_memory:<field>
  - handoff
  - close
forbidden_actions:
  - invent_commercial_facts
  - skip_required_confirmation
  - ask_unnecessary_pii
  - pressure_close
  - discuss_out_of_scope
response_style:
  tone: concise | consultative | reassuring | neutral
  format: short_messages | bullets | numbered_options
  localization: plain_english_base
tools_allowed:
  - tool_name
escalation_triggers:
  - user_requests_human
  - strong_frustration
  - repeated_failure
  - missing_sensitive_capability
completion_criteria:
  - condition
evaluation_criteria:
  - grounding
  - tool_correctness
  - stage_appropriateness
  - cx_quality
labels:
  - analytics_label
```

### Конкретные example policies

#### First greeting

```yaml
policy_id: greeting_v1
intent_family: sales
stage: language_and_scope
customer_signal:
  - first inbound message or re-opened conversation
required_facts:
  - preferred_language
missing_fact_strategy: infer_then_confirm
allowed_actions:
  - greet
  - set_language
  - offer_help_categories
  - ask_one_router_question
forbidden_actions:
  - pitch_products_immediately
  - ask_for_phone_email_company_upfront
response_style:
  tone: concise
  format: short_messages
tools_allowed: []
escalation_triggers: []
completion_criteria:
  - user routed to sales/support/handoff/off_scope
evaluation_criteria:
  - clarity_of_scope
  - brevity
  - correct_language
```

#### Product discovery

```yaml
policy_id: discovery_v1
intent_family: sales
stage: sales_discovery
customer_signal:
  - user asks for products, ideas, or recommendations
required_facts:
  - use_case
  - quantity_or_scale
  - budget_band
  - timeline
missing_fact_strategy: ask_one_by_one
allowed_actions:
  - ask_discovery_questions
  - summarize_current_understanding
  - save_memory:needs
forbidden_actions:
  - recommend_without_constraints
  - overqualify_with_8_questions_in_one_turn
response_style:
  tone: consultative
  format: short_messages
tools_allowed: []
escalation_triggers:
  - user requests manager
completion_criteria:
  - enough constraints for shortlist
evaluation_criteria:
  - question_relevance
  - qualification_completeness
  - cx_quality
```

#### Product recommendation

```yaml
policy_id: recommend_v1
intent_family: sales
stage: recommendation
customer_signal:
  - discovery constraints sufficient
required_facts:
  - use_case
  - budget_band
  - key_constraints
missing_fact_strategy: ask_one_gap_only
allowed_actions:
  - recommend
  - explain_fit
  - offer_comparison
  - save_memory:recommended_options
forbidden_actions:
  - claim_stock_or_price_without_tool
  - recommend_more_than_3_options
  - generic_feature_dump
response_style:
  tone: consultative
  format: bullets
tools_allowed:
  - catalog_search
escalation_triggers:
  - no_good_match_exists
completion_criteria:
  - customer reacts to shortlist
evaluation_criteria:
  - recommendation_fit
  - grounding
  - brevity
```

#### Customer selects products

```yaml
policy_id: selection_memory_v1
intent_family: sales
stage: selection_memory
customer_signal:
  - explicit selection of one or more products
required_facts:
  - sku_or_product_identity
  - quantity
missing_fact_strategy: clarify_ambiguity
allowed_actions:
  - confirm_selection
  - save_memory:selected_items
  - ask_next_missing_field
forbidden_actions:
  - lose_previous_selection
  - overwrite_selection_without_confirmation
response_style:
  tone: concise
  format: short_messages
tools_allowed:
  - catalog_resolve_product
escalation_triggers:
  - ambiguous item cannot be resolved
completion_criteria:
  - selection state updated and confirmed
evaluation_criteria:
  - memory_accuracy
  - confirmation_quality
```

#### Quote/proforma request

```yaml
policy_id: quote_capture_v1
intent_family: sales
stage: quote_capture
customer_signal:
  - user asks for quote, offer, invoice, proforma, commercial proposal
required_facts:
  - selected_items
  - quantities
  - company_name
  - billing_country
  - currency
  - shipping_location
missing_fact_strategy: ask_batch_if_short_else_one_by_one
allowed_actions:
  - summarize_missing_fields
  - collect_fields
  - call_tool:stock_check
  - call_tool:price_check
  - call_tool:generate_quote
forbidden_actions:
  - generate_quote_without_fact_check
  - state_final_price_from_memory
  - promise_pdf_before_required_fields_complete
response_style:
  tone: neutral
  format: checklist
tools_allowed:
  - stock_check
  - price_check
  - generate_quote
escalation_triggers:
  - pricing_exception
  - special_discount_request
completion_criteria:
  - quote or proforma generated or escalated
evaluation_criteria:
  - tool_correctness
  - fact_completeness
  - commercial_grounding
```

#### Customer sends contact details

```yaml
policy_id: contact_capture_v1
intent_family: sales
stage: qualification_progressive
customer_signal:
  - user provides email, phone, company, tax details, delivery address
required_facts:
  - consent_to_use_details
missing_fact_strategy: infer_if_explicit
allowed_actions:
  - extract_entities
  - sanitize_pii
  - save_memory:contact_fields
  - confirm_received_fields
forbidden_actions:
  - echo_sensitive_data_unnecessarily
  - ask_for_more_pii_than_needed
response_style:
  tone: concise
  format: receipt_style
tools_allowed:
  - contact_parser
escalation_triggers:
  - identity_or_security_requirement
completion_criteria:
  - fields stored and confirmed
evaluation_criteria:
  - entity_extraction_accuracy
  - privacy_hygiene
```

#### Price objection

```yaml
policy_id: price_objection_v1
intent_family: sales
stage: objection_handling
customer_signal:
  - too expensive / budget issue / competitor cheaper
required_facts:
  - objection_reason
missing_fact_strategy: ask_reason_before_defending
allowed_actions:
  - acknowledge
  - clarify_budget_gap
  - offer_tradeoff_options
  - offer_manager_review_if_policy_allows
forbidden_actions:
  - unapproved_discount
  - defensive_argument
  - pressure_close
response_style:
  tone: consultative
  format: short_messages
tools_allowed:
  - alternative_search
escalation_triggers:
  - custom pricing needed
completion_criteria:
  - next step agreed or manager requested
evaluation_criteria:
  - empathy
  - objection_handling_quality
  - policy_compliance
```

#### Stock-out

```yaml
policy_id: stockout_v1
intent_family: sales
stage: commercial_fact_check
customer_signal:
  - tool returns unavailable / delayed
required_facts:
  - unavailable_item
  - expected_restock_or_lead_time
missing_fact_strategy: tool_lookup_only
allowed_actions:
  - explain_unavailability
  - propose_2_to_3_alternatives
  - ask_preference_on_wait_vs_substitute
forbidden_actions:
  - pretend_item_available
  - hide_delay
response_style:
  tone: reassuring
  format: numbered_options
tools_allowed:
  - stock_check
  - alternative_search
escalation_triggers:
  - no acceptable alternative
completion_criteria:
  - waitlist / alternative / handoff chosen
evaluation_criteria:
  - transparency
  - alternative_quality
  - grounding
```

#### Asks for manager

```yaml
policy_id: manager_handoff_v1
intent_family: handoff
stage: human_requested
customer_signal:
  - explicit manager request
  - frustration
  - complex commercial exception
required_facts:
  - conversation_summary
  - selected_items_if_any
  - language
  - urgency
missing_fact_strategy: auto_summarize
allowed_actions:
  - acknowledge
  - summarize
  - handoff
forbidden_actions:
  - resist_handoff
  - ask_redundant_questions_before_handoff
response_style:
  tone: respectful
  format: short_messages
tools_allowed:
  - create_handoff_ticket
  - summarize_conversation
escalation_triggers: []
completion_criteria:
  - handoff package created and confirmed
evaluation_criteria:
  - handoff_completeness
  - cx_quality
```

#### Irrelevant/off-scope request

```yaml
policy_id: off_scope_v1
intent_family: off_scope
stage: off_scope
customer_signal:
  - request unrelated to products/support mission
required_facts: []
missing_fact_strategy: none
allowed_actions:
  - politely_decline
  - restate_scope
  - offer_valid_next_help
forbidden_actions:
  - hallucinate_answer
  - continue_off_scope_conversation
response_style:
  tone: neutral
  format: short_messages
tools_allowed: []
escalation_triggers: []
completion_criteria:
  - user redirected or conversation closed
evaluation_criteria:
  - boundary_setting
  - politeness
  - no_hallucination
```

## Локализуемые шаблоны ответов

Для English base templates, которые потом легко локализовать в русский и арабский, нужно держать стиль **plain English, short clauses, no idioms, no culture‑specific humor, no nested conditionals**. Для messaging это особенно важно; Conversica и messaging vendors отдельно подчеркивают краткость, одноцелевые сообщения и избегание confusing phrasing. citeturn12search7turn21search0turn21search1

Ниже — canned templates, которые я бы положил в library и локализовал через placeholders, а не через переписывание логики.

### Greeting and routing

```text
Hi — thanks for reaching out to [COMPANY].
I can help with product options, pricing, stock, quotes, and support.
What do you need today?
1) Product advice
2) Price / stock
3) Quote / proforma
4) Support
5) Speak to a manager
```

### Discovery

```text
Sure — I can help with that.
To suggest the right option, what is this for?
[office / meeting room / home office / reception / other]
```

```text
Got it.
About how many people or workstations are you planning for?
```

```text
Do you already have a budget range in mind?
If yes, please share a rough range.
```

### Recommendation

```text
Based on what you shared, I would start with these options:
1) [OPTION_A] — best for [REASON]
2) [OPTION_B] — best for [REASON]
3) [OPTION_C] — best for [REASON]

If you want, I can compare them side by side.
```

### Comparison

```text
Here is the short comparison:

[OPTION_A] — [best for], [key tradeoff]
[OPTION_B] — [best for], [key tradeoff]
[OPTION_C] — [best for], [key tradeoff]

Which one would you like to explore first?
```

### Selection memory

```text
Understood — I have noted:
- [ITEM_1], qty [QTY_1]
- [ITEM_2], qty [QTY_2]

Would you like to add anything else, or should I check stock and pricing?
```

### Quote / proforma capture

```text
I can prepare that.
Before I generate the quote / proforma, I need:
- company name
- delivery country / city
- contact name
- email
- selected items and quantities

If you prefer, send everything in one message.
```

### Contact details receipt

```text
Thanks — I received your details.
I have:
- company: [COMPANY_NAME]
- contact: [CONTACT_NAME]
- email: [EMAIL]
- location: [LOCATION]

If anything should be corrected, tell me now.
```

### Price objection

```text
I understand.
Is the main issue the total budget, the unit price, or the delivery / installation cost?
If you want, I can suggest lower-cost alternatives or a simpler configuration.
```

### Stock-out

```text
This item is currently unavailable / delayed.
The current lead time is [LEAD_TIME].

Closest alternatives:
1) [ALT_1]
2) [ALT_2]
3) [ALT_3]

Would you prefer an alternative, or should I ask a manager to review options?
```

### Manager handoff

```text
Of course — I will pass this to a manager.
I will include your current request, selected items, and contact details so you do not need to repeat everything.
```

### Off-scope

```text
I’m here to help with [PRODUCTS], pricing, quotes, and support related to [COMPANY].
If you want, I can still help with one of those right now.
```

### Post-quote follow-up

```text
Just checking in on the quote I shared.
Would you like:
1) a revised version
2) alternative products
3) help from a manager
4) no further action
```

Локализационное правило здесь простое: **translate wording, never translate policy logic**. Policy determines whether we ask, compare, confirm, escalate or call a tool; localization only changes surface form.

## Рубрика оценки, golden scenarios и производственные сигналы

Для evaluation stack вам нужен не один score, а **многоуровневая рубрика**:
**run‑level quality**, **trajectory/tool correctness**, **grounding**, **handoff quality**, **customer experience**, **multilingual quality**, **business readiness**. Именно так рекомендуют мыслить и LangSmith, и Phoenix, и Rasa’s DU testing, и Intercom simulations. citeturn11search2turn11search4turn11search6turn11search8turn10search0turn10search1turn10search3turn26view2turn33view0

### Предлагаемая evaluation rubric

Я бы делал weighted score out of 100:

- **Grounding and truthfulness — 20**
  Does the bot avoid inventing price, stock, policy, delivery or discount facts?
- **Tool-use correctness — 20**
  Correct tool selected, correct arguments, correct handling of tool result.
- **Sales/support stage appropriateness — 15**
  Did the bot choose the right next step for the stage and customer signal?
- **Qualification completeness — 10**
  Did it collect the minimum useful facts, not maximum possible facts?
- **Recommendation quality — 10**
  Are recommendations tied to expressed constraints?
- **Handoff quality — 10**
  Is the summary complete, actionable, and privacy‑safe?
- **Customer experience — 10**
  Short, polite, clear, non‑pushy, non‑repetitive.
- **Multilingual quality — 5**
  Correct language, no broken placeholders, natural sentence order.

### Minimum release gates

Прод выпускать только если одновременно выполнены четыре условия:

- Grounding/Truthfulness ≥ 95% on critical scenarios
- Tool correctness ≥ 95% on stock/price/quote/handoff scenarios
- No critical policy violations in human review
- Handoff completeness ≥ 90% on escalation scenarios

### 30 golden test scenarios

Ниже — curated set, который я бы сделал первым “golden pack”.

**Sales discovery and recommendation**

1. Пользователь пишет очень кратко: “Need desks for 20 people.”
2. Пользователь не отвечает на discovery question и сразу спрашивает цену.
3. Пользователь описывает use case, но не бюджет.
4. Пользователь просит “best option” без контекста.
5. Пользователь просит recommendation для small office + fast delivery.
6. Пользователь просит compare between two options.
7. Пользователь выбирает один товар, потом исправляет quantity.
8. Пользователь выбирает два товара и один снимает с выбора.
9. Пользователь спрашивает про competitor comparison.
10. Пользователь просит “something cheaper but similar.”

**Commercial facts and quote generation**

11. Пользователь просит price before any tool check exists.
12. Tool returns multiple SKU matches; bot must clarify.
13. Tool returns no stock; bot must offer alternatives.
14. Tool returns price in different currency than user asked.
15. Пользователь просит quote without company/email.
16. Пользователь sends all quote fields in one messy message.
17. Пользователь sends VAT/company details with typos.
18. Пользователь asks for proforma PDF and urgent turnaround.
19. Пользователь asks for discount not defined in policy.
20. Пользователь asks for shipping/installation details after quote draft already started.

**Support, repair, and escalation**

21. Пользователь interrupts quote flow with support problem.
22. Пользователь corrects previously given email address.
23. Пользователь switches language mid‑conversation.
24. Пользователь asks the bot to repeat previous comparison.
25. Пользователь says “This is not what I asked.”
26. Пользователь becomes frustrated after two failed clarifications.
27. Пользователь explicitly asks for a human manager.
28. Пользователь asks off‑scope question unrelated to business.
29. Bot receives unsupported image/attachment in a commercial flow.
30. Tool error/timeout occurs during stock or quote generation.

### Как измерять это practically

- **Offline**: dataset of multi‑turn conversations with expected labels, required facts and expected tool trajectories. This is where trajectory match and reference‑based grading fit best. citeturn11search4turn11search6
- **Online**: reference‑free judges for clarity, politeness, hallucination risk, handoff adequacy, excessive questioning, and multilingual correctness. citeturn11search2turn11search8turn10search6
- **Simulation layer**: synthetic or replayed conversations against procedures/policies before release, similar to Intercom Simulations. citeturn33view0
- **Tool layer**: Phoenix‑style checks for tool selection, invocation args, and correct use of returned data. citeturn10search0turn10search1turn10search3
- **Support/intake layer**: Rasa‑style command/flow accuracy tests for clarify, cancel, set slot, human handoff, knowledge answer. citeturn26view2

## Реальные примеры, неудачи и красные флаги

Публичные production examples показывают, что хорошие AI agents действительно могут улучшать response time, containment/resolution и pipeline — но почти всегда там есть **strict knowledge control, routing, handoff and continuous optimization**. У Intercom собственная support team довела Fin до 81% resolution volume, absorb’нула рост спроса 300%+ без пропорционального роста headcount и сформировала отдельную conversation design роль; у customer story Breathe resolution rate вырос с 56% до 82%; у Synthesia AI + automation помогли выдержать рост support demand на 690% при снижении resolution time на 96%; WHOOP использовал Fin и вышел на 84% sales conversations resolved. citeturn16view3turn14search5turn14search13turn16view4

У Salesforce от entity["company","Salesforce","crm software"] Agentforce на help.salesforce.com за шесть месяцев обработал более 500,000 customer conversations и разрешал более 84% customer questions; customer story Wonolo сообщает о снижении handle time на 20% с AI‑generated replies. У Zendesk customer story NOBULL сообщает о deflection nearly 50% chat inquiries и 30% of overall contacts без просадки CSAT. Все это — полезные production signals, но нужно помнить, что это vendor case studies, а не независимые controlled trials. citeturn14search14turn14search2turn14search16

В sales automation публичные кейсы говорят не “заменить людей полностью”, а скорее “агенты снимают рутину и ускоряют response”, что хорошо совпадает с рекомендацией entity["organization","Boston Consulting Group","management consulting"] о hybrid model, где optimal mix human + AI зависит от размера сделки и важности отношений. У Regie.ai их собственные AI agents, по публичному кейсу, дают 40% SDR‑driven meetings и “millions in qualified pipeline” без дополнительного headcount; другой публичный SaaS case на их сайте заявляет 25–30% pipeline growth и productivity equivalent 4–6 SDRs. У 11x есть публичный case MMB Networks с 5x increase in qualified meetings и 2.5x industry average reply rate. Это полезные сигналы, но опять же vendor‑reported. citeturn16view2turn20search6turn20search9turn20search7

Что отличает хорошие боты от плохих:

- хорошие **не придумывают политику и коммерческие факты**;
- хорошие **быстро понимают use case и scope**;
- хорошие **запрашивают только недостающие поля**;
- хорошие **сохраняют память о выборе клиента**;
- хорошие **передают человекам полный контекст**;
- хорошие **допускают topic switches и corrections**;
- хорошие **не притворяются “слишком человеком” там, где это вызывает недоверие**. citeturn33view3turn34view1turn26view0turn16view3

Плохие production patterns уже хорошо видны по backlash cases. У Cursor front‑line support bot выдумал несуществующую policy, что вызвало публичный скандал и complaints about transparency; у entity["company","DPD","parcel delivery"] бот начал ругаться и оскорблять компанию. Отдельно исследователи из California Management Review подчеркивают, что массовое внедрение chatbot service несет скрытые costs в виде frustration; в статье приводится обзор опросов, где 53–77% респондентов сообщали о плохом или раздражающем chatbot experience. В сообществах /r/sales и HN низкокачественные AI SDR patterns repeatedly describe as “automated spam at scale” and “AI slop-email spam” — это не scientific evidence, но очень полезный market signal. citeturn7search8turn7news29turn16view0turn8search3turn8search2

### Красные флаги, которые я бы запретил в blueprint

1. **Fake personalization** — упоминать боли, отрасль или потребности, которых бот не установил явно. citeturn7search8turn16view0
2. **Hallucinated commercial facts** — цена, stock, ETA, скидка, VAT rules без tool/approved source. citeturn24search3turn24search4turn33view3
3. **Overqualification at greeting** — сначала собирать email/company/budget, потом помогать. В мессенджере это выглядит как lead form, а не помощь. citeturn12search7turn16view0
4. **Any pressure‑close language before fit is established** — особенно в WhatsApp. Community backlash against spammy AI SDR behavior делает это токсичным. citeturn8search3turn8search2
5. **Repeating fixed scripts after user correction** — repair must win over stage progression. citeturn26view0turn26view1
6. **Resisting a human handoff** — if user asks for manager, hand off early and well. citeturn31search0turn33view3turn26view1
7. **Long paragraph dumps** — especially in messaging. Use short turns and options. citeturn12search7turn21search0
8. **Single giant system prompt** — harder to debug than policy modules, journeys and controlled workflows. citeturn25view2turn30view0
9. **Unscoped knowledge retrieval from all sources** — raises leakage, irrelevance and wrong‑fact risk. Use search rules/audiences/procedure‑scoped lookup. citeturn34view1turn33view1
10. **Treating support and sales as separate memory silos** — high‑quality systems preserve context across the lifecycle. Intercom explicitly frames the future as one customer agent across service and sales. citeturn18search1turn16view4

## Практическая интеграция без оверинжиниринга

Моя рекомендация: **делайте playbook layer независимым от runtime**, а runtime выбирайте максимально скучный и управляемый.

### Рекомендуемая сборка

**Authoring layer**
Git‑versioned library of:
- policy YAML
- canned responses
- prompt modules
- journey definitions
- golden scenarios
- evaluator configs

По духу это должно быть ближе к Parlant’s guidelines/journeys/canned responses, чем к “one master prompt”. citeturn25view0turn25view1turn24search3

**Runtime layer**
Используйте **LangGraph** для primary state machine, checkpoints, human‑in‑the‑loop, memory and deterministic routing. Публичные материалы LangGraph подчеркивают durable execution, built‑in HITL support, persistent state and memory as core strengths for stateful agents. citeturn27search2turn6search3

**Typed tool layer**
Используйте PydanticAI или обычные Pydantic models как **strict contracts for tools and structured outputs**: stock check, price check, quote request payload, handoff payload, contact entities, multilingual metadata. Здесь важна не “магия framework”, а то, что every critical action has a typed schema and validation.

**Background process layer**
Используйте Temporal только там, где он действительно нужен:
quote/proforma generation, retries to CRM/ERP, delayed follow‑ups, manager callback SLAs, audit‑safe retries, long‑running approval chains.
**Не** тащите Temporal в каждый turn conversation logic. Turn‑level dialogue orchestration лучше оставить в LangGraph/flow engine, иначе reference architecture быстро станет тяжелой.

**Policy enforcement layer**
Даже если вы не берете Parlant runtime, **возьмите его идеи буквально**:
- contextual guidelines
- journeys for multi‑turn SOP
- tools only when relevant
- canned responses for critical wording
- labels/tags for audit and analytics. citeturn25view0turn25view1turn1search6

**Eval / observability layer**
Сделайте двойной контур:
- LangSmith‑style dataset/backtest/trajectory evals
- Phoenix‑style tool/faithfulness evaluators
- session labels/attributes for analytics
- human QA on a sampled set of live conversations. citeturn11search4turn11search6turn11search7turn10search0turn10search1turn10search3turn33view2

### Минимальный blueprint без оверинжиниринга

Если резюмировать в одном абзаце:
**LangGraph for runtime state + typed tool schemas + policy YAML inspired by Parlant + repair pattern catalog inspired by Rasa + controlled workflows/canned responses for commercial facts and handoff + LangSmith/Phoenix for evals + Temporal only for long‑lived business jobs.** Это даст вам достаточную управляемость для WhatsApp B2B sales/support without building an unnecessary swarm of agents. citeturn25view2turn26view0turn30view0turn27search2turn11search6turn10search6

### Открытые вопросы и ограничения

Есть несколько мест, где публичный рынок пока слабее, чем хотелось бы:

- Я не нашел сильного **open‑source, production‑grade library** именно для quote/proforma conversational capture с multilingual messaging discipline и hard commercial fact gating; это почти наверняка придется авторить самостоятельно.
- Сильнейшие публичные case studies по performance mostly vendor‑reported, so metrics should be treated as directional, not neutral benchmarks. citeturn16view3turn14search14turn20search7turn20search9
- Публичных артефактов именно по **WhatsApp B2B furniture sales playbooks** немного; наиболее reusable pieces пришлось брать из adjacent domains: ecommerce support, inbound sales, CX automation, open sales prompt libraries и framework docs. citeturn12search7turn22view0turn22view1turn33view0turn34view0

Итоговая рекомендация: **строить не “бота”, а reusable conversation operating system** — с отдельными policy objects, journeys, canned truths, tool gates и eval suites. Именно это даст вам переносимость между клиентами и одновременно сохранит качество в первом реальном кейсе с WhatsApp‑ассистентом для B2B офисной мебели.