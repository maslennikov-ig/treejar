# Noor Agent-Driven E2E Acceptance Design

**Date:** 2026-07-27
**Beads goal:** `tj-ee5f`
**Status:** approved design, preparation only
**Runtime target for the future authorized run:** `https://noor.starec.ai`

## 1. Purpose

Create a comprehensive, agent-driven end-to-end acceptance of Noor as a
customer-facing WhatsApp sales assistant. The test agent converses with Noor,
adapts within bounded customer personas, verifies externally visible behavior
and downstream effects, and preserves evidence suitable for both engineering
work and a client report to Viktor.

The acceptance must answer four questions:

1. Does Noor fulfill the original Treejar requirements?
2. Do previously fixed bot-behavior defects remain fixed?
3. Does the current model routing remain factual, commercially useful, and
   operationally safe in full conversations?
4. Can every conclusion be traced to exact questions, answers, runtime
   identity, side effects, and retest evidence?

This design does not authorize live tests, paid model calls, customer
messaging, Zoho/CRM mutations, quotation creation, deployment, or production
cleanup. The execution plan must put those actions behind an exact run
authorization manifest.

## 2. Sources of Truth and Precedence

The acceptance derives its coverage from:

1. Current repository and runtime contracts:
   `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
   `.codex/project-index.md`.
2. Original and updated requirements:
   `docs/01-tz-basic.md`, `docs/02-tz-extended.md`,
   `docs/03-ai-agent-requirements.md`, `docs/tz.md`.
3. Sales and evaluation rules:
   `docs/04-sales-dialogue-guidelines.md`, `docs/05-company-values.md`,
   `docs/06-dialogue-evaluation-checklist.md`,
   `docs/08-manager-evaluation-criteria.md`.
4. Catalog and evidence policy:
   `docs/07-knowledge-base-spec.md`,
   `src/llm/communication_policy.py`.
5. Closed Beads defects and accepted stage evidence.
6. Current behavior when later accepted decisions intentionally supersede an
   older requirement.

When sources conflict, the latest accepted repository decision wins. Examples:

- Customer-facing identity is Noor, not the older Siyyad wording.
- Treejar Catalog API is the customer-facing catalog and price truth.
- Zoho Inventory is the operational confirmation and quotation/SaleOrder
  system, not the primary customer catalog.
- Exact price, stock, quotation, order state, exceptional discounts, payment
  terms, and unverified logistics require the applicable tool or manager gate.

The report must disclose each material precedence decision rather than silently
rewriting the original requirement.

## 3. Chosen Test Architecture

Use a hybrid structure:

### 3.1 Isolated scenario capsules

Most scenarios use a unique synthetic identity derived from one approved test
recipient plus a run and scenario suffix. Each capsule starts from declared
state, exercises one coherent customer outcome, and has its own cleanup and
readback.

This prevents a name gate, escalation, quotation, or stale memory from
contaminating unrelated results.

### 3.2 One longitudinal customer journey

After isolated capsules, run one long conversation that combines:

- first contact and name capture;
- company, address, preferences, and budget;
- product discovery and changing requirements;
- product quantities and exact references;
- an interruption about delivery or assembly;
- an objection and alternative request;
- quotation readiness or an explicit quotation hold;
- a saved-context summary;
- a clear next step.

The long journey validates memory, expected-answer frames, interruption
handling, fact retention, and context recovery.

### 3.3 Separate evidence blocks

Admin/operator UI, quality/reporting, referrals, load, backups, security, and
availability are not mixed into the customer conversation. They receive
separate read-only or separately authorized acceptance blocks that link to the
same final report.

## 4. Coverage Model

Every scenario has a stable ID and links to one or more requirements and prior
defects. The implementation plan will maintain an exact traceability matrix.

### A. Runtime and transport

- Release SHA, deployment run, app version, model route readback, health,
  Redis, PostgreSQL, worker, Wazzup channel state.
- Inbound text reaches one conversation and is persisted once.
- Outbound text/media has an audit row, provider ID where applicable, delivery
  status, and deterministic idempotency identity.
- No silent timeout, duplicate response, unsupported typing loop, or orphaned
  pending conversation.
- Measure inbound-to-first-visible-reply, final reply, media delivery, and
  end-to-end scenario duration.

Historical anchors include `tj-zj9`, `tj-2i3`, `tj-av22.11`,
`tj-15m.5.1`, `tj-15m.6`, and `tj-e2e26`.

### B. Opening, identity, names, and language

- First English and Arabic turns introduce Noor and Treejar and ask for the
  customer's name without leaking product/quote side effects.
- Labeled and bare-name replies are accepted without a repeated name question.
- The request made before the name gate resumes after name capture.
- First-turn Arabic is Arabic before the dialogue kernel responds.
- Locale remains consistent through normal, fallback, and manager paths.
- Returning customer context does not force a new-customer opener.

Historical anchors include `tj-gh12.1`, `tj-gh12.16`, `tj-gh12.18`,
`tj-gh14.3`, `tj-gh14-delivery.4`, `tj-gh15.1`, `tj-gh49.1`,
`tj-final27.14`, and `tj-15m.9`.

### C. Product discovery and consultative selling

- Broad category, exact product, budget, use case, team size, room type,
  style, and option-count requests.
- Relevant catalog-backed options before unnecessary data collection.
- One useful narrow question after a useful answer when clarification is
  needed.
- Alternatives when no exact match exists, clearly labeled as alternatives.
- Comparison, value explanation, cross-sell, and objection handling without
  invented discounts or unsupported benefits.
- Off-catalog redirection remains useful and does not falsely claim a match.
- Ordinary furniture requests, product preferences, and numbered discovery
  answers do not cause fake SKU references or premature manager handoff.
- Showroom visits and project samples follow current capability policy:
  showroom availability can be stated from verified FAQ; samples are
  conditional and not promised as fulfilled.

Historical anchors include `tj-7z2n`, `tj-v4rl`, `tj-pgms`, `tj-gh47`,
`tj-gh48.8`, `tj-6r78`, `tj-lgmg`, `tj-tauh`, `tj-15m.3`,
`tj-15m.5.2`, and `tj-final27.17`.

### D. Factual grounding and commercial safety

- Catalog identity, description, category, image, and customer price match the
  Treejar Catalog API.
- Exact stock/availability uses the operational confirmation path.
- Missing or invalid evidence is reported as unknown/unconfirmed, not as
  unavailable, and does not produce a promise to check later instead of using
  an available tool.
- No invented stock, price, discount, payment term, delivery date, warranty,
  medical benefit, quotation state, manager action, or sample fulfillment.
- Catalog-only and missing-price items fail closed for quotation/SaleOrder.
- Prompt injection or a soft-deleted knowledge record cannot override policy
  or leak into the answer.

Historical anchors include `tj-final27.10`, `tj-prl26.5`, `tj-5cb2`,
`tj-4gtc`, `tj-hwls.1`, `tj-j13d`, and `tj-r1f3`.

### E. Context, memory, and interruptions

- Product, quantity, delivery, assembly, company, address, email, role,
  preference, budget, and next-step facts survive a long dialogue.
- Neutral detail updates do not trigger verified-policy handoff.
- Saved-context summaries are faithful and do not invent missing fields.
- Preference, ordinal, quantity, and compact detail answers attach to the
  question Noor actually asked.
- Delivery/assembly questions can interrupt product selection and then return
  to the active flow.
- New requests do not inherit stale quotation decisions or stale product
  selection.
- A user correction replaces the corrected fact while preserving unrelated
  facts.

Historical anchors include `tj-e2e15.2`, `tj-e2e16.5`, `tj-memory.8`,
`tj-memory.11`, `tj-gh47`, `tj-gh48`, `tj-gh49`, `tj-m7wz.1`,
`tj-m7wz.2`, and `tj-order-state`.

### F. Product media, voice, and WhatsApp presentation

- Main textual answer arrives before its product media.
- Images match products actually named in the final answer, including variant
  words and similar SKUs.
- No ordinary chair image is attached to a convertible sleeper chair.
- No repeated media after exact selection, quotation creation, fail-closed
  response, or manager handoff.
- Captions are absent or useful, not redundant duplicate messages.
- Voice messages in English and Arabic are accepted, transcribed, answered in
  the detected language, persisted, and represented in audit data.
- WhatsApp formatting contains no broken nested markers, raw horizontal rules,
  malformed links, or unpaired emphasis.

Historical anchors include `tj-a82d`, `tj-adca`, `tj-q0ou`,
`tj-gh17.3`, `tj-gh18.2`, `tj-jyig`, `tj-a5n`, `tj-8yn`, `tj-bp2`,
and accepted `tj-15m` media corrections.

### G. Quotation and order lifecycle

- Exact and natural quotation requests recognize SKU/model aliases, homoglyphs,
  suffixes, punctuation, word quantities, position quantities, and multiple
  items.
- A quantity-only reply attaches to the pending product, not a fake item.
- Product/model numbers are not misread as quantities.
- Missing item, quantity, or customer details produce one bounded request for
  missing data rather than escalation.
- Explicit "no quotation" remains consultation-only.
- Customer-provided name, company, email, address, and item data are preserved
  exactly; unprovided data are not invented in the PDF.
- Quotation is created only after exact SKU and quantity readiness and the
  applicable customer-data gate.
- PDF, text, media/caption audit, manager approve/reject, and customer order
  status are consistent.
- Generic "yes/ok" acts on a quotation only when directly answering the current
  quotation decision question.
- A new proposal clears stale decision metadata.

Historical anchors include `tj-va4o`, `tj-gh12.2`, `tj-gh12.4`,
`tj-gh12.7`, `tj-gh12.12`, `tj-gh12.19`, `tj-gh14.1`,
`tj-gh14.2`, `tj-gh15.2`, `tj-gh17.1`, `tj-gh17.2`,
`tj-gh18.1`, `tj-gh19.1`, `tj-gh19.2`, `tj-gh23.1`–`tj-gh23.4`,
`tj-m7wz.1`–`tj-m7wz.3`, `tj-4cm4`, `tj-8ma2`, `tj-nzob`,
`tj-mmj8`, `tj-order-state`, `tj-order-cutover`, and `tj-e2e26`.

### H. Escalation and manager continuity

- Direct human request, complaint, refund/return, exceptional terms, large
  concrete order, and other current hard triggers hand off once.
- Ordinary discovery, customer detail capture, product preference, and
  low-risk delivery/assembly questions do not hand off prematurely.
- Pending escalation always returns a localized fallback instead of silence,
  with bounded manager notification behavior.
- Escalation row, reason, context tail, Telegram alert, manager reply,
  customer delivery, persistence, and resolution remain consistent.
- A manager reply adapter does not add facts absent from the manager draft or
  verified sources.
- Every synthetic escalation is resolved before run closeout.

Historical anchors include `tj-zj9`, `tj-lgmg`, `tj-e2e15.2`,
`tj-gh12.17`, `tj-jy5i`, `tj-19ti`, `tj-19ol.3.7`,
`tj-19ol.3.9`, `tj-19ol.3.11`, and `tj-19ol.3.13`.

### I. CRM and returning-customer behavior

- New synthetic customer creates or enriches only the expected contact/deal
  records using the approved mutation path.
- Existing customer is recognized by the approved identifier and receives
  bounded relevant context.
- Name, phone, email, company, source, original/latest UTM, segment, address,
  and deal stage follow current mapping and overwrite policy.
- Conversation history and manager/customer messages are readable in the
  operator surfaces.
- CRM/OAuth failure is fail-soft for customer communication and visible to
  operations; it must not drop the inbound batch.

Historical anchors include `tj-p9ui`, `tj-memory`, `tj-final27.2`,
`tj-qs72`, and `tj-mamw`.

### J. Follow-up, feedback, and lifecycle messaging

- Quotation acceptance/rejection is tied to the current prompt and proposal.
- Follow-up cadence follows the approved policy; final FU3 has a response grace
  period and does not immediately mark rejection.
- Explicit rejection persists final state and stops further follow-ups.
- Arabic locale variants stay Arabic.
- Payment reminders remain disabled unless their separately approved template,
  timing, stop conditions, and service-window policy are present.
- Post-delivery feedback asks at the correct lifecycle state and stores the
  result once.

Historical anchors include `tj-gh21.1`–`tj-gh21.5`, `tj-gh22`,
`tj-xu1`, `tj-final27.3`, `tj-final27.5`, and `tj-lzt`.

### K. Quality, reporting, admin, referrals, and nonfunctional blocks

These are linked but separately authorized blocks:

- Bot dialogue scoring uses the 15-rule, 4-weighted-block, stage-aware
  methodology and records `n_a` correctly.
- Manager assessment evaluates only completed/resolved escalations and uses
  transcript evidence.
- Admin/operator readback shows conversations, audit rows, prompts, QA results,
  costs, and operational status without silent UI actions.
- Referral behavior is tested only after business rules and synthetic reward
  constraints are approved.
- Load test proves the declared concurrency target without contacting real
  customers.
- Backup/restore evidence, security/auth checks, and availability measurement
  are reported separately from conversational quality.

Historical anchors include `tj-ruue`, `tj-final27.5`–`tj-final27.8`,
`tj-qh8e`, `tj-wpzl`, `tj-s4j9`, and `tj-av22`.

## 5. Agent Behavior

The test agent plays bounded customer personas, not a passive script runner.
For each scenario it receives:

- persona and starting state;
- customer goal and facts it may disclose;
- required checkpoints;
- prohibited disclosures or accidental shortcuts;
- stop conditions;
- readback requirements.

The agent may paraphrase and ask natural follow-ups, but it must:

- preserve the scenario's factual constraints;
- never help Noor by revealing the expected implementation;
- never accept an unsafe or factually unsupported answer merely because the
  wording is polite;
- avoid opening unrelated branches;
- preserve every sent and received message;
- stop the affected scenario when continuation could create unwanted business
  state.

Deterministic seeded prompts provide reproducibility. One controlled paraphrase
variant per high-risk regression family provides robustness without turning the
run into open-ended exploration.

## 6. Evidence Architecture

### 6.1 Run identity

Every run has:

- `run_id`;
- UTC and Europe/Moscow timestamps;
- repository commit;
- deployed release SHA and CI run;
- app version and migration head;
- main/fast model readback;
- approved recipient/channel and synthetic prefix;
- scenario-set version;
- authorization manifest;
- evidence checksums.

### 6.2 Per-turn record

For every customer and assistant turn, store:

- run, scenario, conversation, and turn IDs;
- exact customer text or synthetic media reference;
- exact Noor text and media/caption references;
- original language and, for Arabic, a Russian report translation;
- send, receive, first-visible, final-visible, and delivery timestamps;
- model identity, routing suffix, tools invoked, tool outcome class, token/cost
  data when available;
- message/provider/audit IDs;
- expected behavior and actual observation;
- deterministic checks and evaluator judgment;
- pass/fail status and linked requirement/Beads IDs.

Exact synthetic question and answer text belongs in the client evidence. Raw
credentials, tokens, full phone numbers, private manager data, and unrestricted
production logs do not.

### 6.3 Storage layers

Use two layers:

1. **Protected raw evidence** outside Git, mode `600`, containing unredacted
   transport/readback records and restricted logs.
2. **Tracked redacted evidence** under
   `.codex/stages/<stage_id>/results/<run_id>/`, containing manifests,
   redacted transcripts, scenario results, checksums, defect links, and report
   inputs.

The tracked layer is sufficient to reproduce every conclusion without exposing
secrets or real personal data.

### 6.4 Client deliverable

Generate a Russian client report for Viktor with:

- scope and runtime identity;
- methodology;
- requirement-to-scenario coverage;
- every scenario's exact questions and answers;
- expected versus actual behavior;
- screenshots/media thumbnails or safe references where applicable;
- timing and delivery evidence;
- defects found;
- initial failed evidence;
- what was fixed;
- exact retest evidence;
- final status and remaining limitations.

The durable source is Markdown/structured evidence. PDF is generated only after
content acceptance and visually inspected.

## 7. Result and Defect Model

Allowed scenario states:

- `passed`;
- `failed`;
- `fixed_and_retested`;
- `blocked`;
- `not_run`.

Do not overwrite a failed attempt. A correction adds a new attempt linked by:

- same scenario ID;
- original run/attempt;
- Beads defect ID;
- fix commit and deployment identity;
- invariant test evidence;
- retest run/attempt;
- final disposition.

Defect severity:

- **P0:** unsafe external mutation, privacy/security exposure, corrupted
  commercial document/state, or systemic inability to test safely.
- **P1:** core customer flow failure, factual hallucination, wrong
  price/stock/order state, lost context, silence, wrong manager handoff, or
  persistent transport failure.
- **P2:** material quality/UX defect with a safe workaround.
- **P3:** polish or low-impact evidence issue.

P0/P1 stops the affected branch and blocks acceptance. It does not erase other
independent evidence. P2/P3 may continue only when the scenario remains safe.

Every defect is created in Beads as a child or `discovered-from` item of
`tj-ee5f` and includes:

- minimal reproduction;
- exact evidence path;
- expected and actual behavior;
- customer/business impact;
- severity rationale;
- acceptance criteria;
- linked historical regression when applicable.

The same correction stream owns root-cause analysis, failing invariant,
implementation, local verification, deployment gate, exact scenario retest,
and report update. A defect is not marked fixed based only on a code change.

## 8. Scoring and Acceptance

Use three complementary layers:

1. **Hard safety/correctness gates:** binary. Any unsupported commercial fact,
   wrong side effect, privacy breach, or P0/P1 regression fails the scenario.
2. **Scenario behavior:** required checkpoints and prohibited outcomes.
3. **Sales quality:** the current 15-rule weighted evaluation, stage-aware
   applicability, usefulness, clarity, tone, and next-step quality.

Performance reporting includes:

- time to first visible response;
- time to final text;
- media delivery time;
- scenario duration;
- p50, p95, and maximum;
- timeout and retry counts.

The original `<10 seconds` response requirement remains visible as the
contractual target. A miss is reported, not normalized away. External-model
latency and local delivery latency are separated when trace evidence permits.

Overall acceptance requires:

- every in-scope requirement mapped to evidence, a declared external gate, or
  an explicit client-approved exclusion;
- no unresolved P0/P1;
- every found-and-fixed defect shown with before/after evidence;
- zero unintended pending synthetic escalations or active test workflows;
- protected raw evidence and complete redacted client evidence;
- client report consistency with structured results.

## 9. Safety and Authorization Boundaries

Before execution, bind an exact authorization manifest:

- recipient and Wazzup channel;
- synthetic suffix/prefix;
- maximum scenarios/messages/model calls and cost;
- allowed quotation/SaleOrder, CRM, Telegram, media, voice, follow-up,
  feedback, referral, and load branches;
- cleanup method;
- permitted readbacks;
- stop conditions.

Never use real customers or real customer data. Never place secrets in prompts,
Git, Beads, or client reports. Do not run broad production suites, scheduled AI
quality jobs, payment reminders, referral rewards, destructive cleanup, deploy,
or configuration changes unless the exact action is separately authorized.

Cleanup must be exact-manifest based. It may resolve synthetic escalations and
close synthetic workflows through approved application paths; destructive
database deletion is not implied by test authorization.

## 10. Orchestration Boundary

One execution stage owns the shared customer-acceptance boundary. Scenario
families may be parallel streams only when they have disjoint synthetic
identities and no shared external state. Quotation, manager, CRM, follow-up,
and cleanup work remains sequential where it shares provider, business state,
or acceptance proof.

Preparation, Beads maintenance, prompt drafting, evidence collation, and final
report reconciliation remain root-owned. The future orchestrator decides
whether specialist or isolated subagents materially improve execution; this
design does not prescribe an agent count.

## 11. Non-Goals

- Testing against real customers.
- Replacing repository unit/integration tests with conversational E2E.
- Treating a model judge as the only correctness oracle.
- Rewriting historical failed evidence after a fix.
- Enabling currently disabled business features merely to make acceptance look
  complete.
- Using exact wording as the pass criterion when behavior and factual outcome
  are correct.
- Broad production exploration outside the approved scenario manifest.

## 12. Design Acceptance

The design is accepted when:

- original requirements and historical defect families are represented;
- isolated capsules and the long-memory journey share one evidence model;
- all exact questions and answers can reach the client report;
- raw sensitive evidence remains protected;
- defect discovery, Beads, fix, deploy, retest, and report update form one
  traceable chain;
- full execution remains gated on exact live authorization.
