# Model-owned customer intent — tj-r703

Status: local implementation; production deployment is not authorized or performed.
Branch: `codex/model-owned-intent`, based on `377a99a` (includes the prior reset hotfix).

## Incident and cause

Read-only production evidence on 2026-09-17 identified conversation
`ed682abc-0f73-44c0-a69f-5533d7841f48`. At 11:00:00 UTC the customer answered
`sure` to the assistant's offer to suggest a four-person furniture setup and
check availability/pricing. At 11:00:33 the worker returned the literal assembly
handoff template, with route `service-confirmation-handoff`, zero response
input/output tokens, and a matching escalation event. The preceding question's
word `setup` matched a lexical service classifier. The deployed engine and
processor files matched the inspected local source by SHA-256.

## Decision

The main tool-using model interprets the original inbound message with history,
including short acknowledgements, negation, conditions, corrections and topic
changes. Code validates state, evidence, parameters and tool execution. It does
not infer the next commercial action from keyword matches.

## Audited runtime boundaries

| Previous boundary | New behavior |
| --- | --- |
| Service confirmation, mixed service/product, showroom, sales fallback, proposal clarification, FAQ clarify/handoff | Evidence is retrieved for the main model; no prewritten response or automatic notification |
| Dialogue kernel and expected-answer frames | Existing state remains data; no pre-model classification, consent mutation or frame response |
| Product/ordinal/quantity selection, exact quotation, quote-detail resumption, name gate | Original message and saved context reach the model; tools own recording and execution |
| Sales-opportunity detection | Only the model-selected CRM tool executes it |
| Post-PDF approval/acknowledgement/hold | Model records acceptance or consent with current-message evidence; actual sent-quotation state remains required |
| Customer-facts extractor and past-order static answer | Existing memory is read without interpreting new text; model records facts and writes the answer |
| Catalog planning before generation | No lexical plan selection or deterministic answer route |
| Search query enrichment and result count/capacity inference | Model supplies query, result limit, seat count, coverage, families and budget explicitly |
| Automatic cross-sell recovery after model failure | No new tool action inferred after failure; existing error handling remains |
| Followup reply rejection/autoreply matching | Any customer reply neutrally stops reminders; commercial rejection/pause requires a model decision |

Legacy dialogue/order/verified-answer helpers remain available to their isolated
compatibility and historical tests. They are not invoked by the incoming chat
pipeline. The assembly classifier and template were removed entirely.

## State and safety

- `record_customer_intent` validates literal current-message evidence, restores
  masked PII, records customer details/quotation consent, and records acceptance
  only for a sent pending quotation. It does not create a quote or notify anyone.
- Refused quotation tools can be made available again by a new model-recorded
  customer request. Consent to create a document and approval of a sent document
  are separate facts.
- Customer details stay synchronized with canonical quote state and, when
  customer-memory enforcement is enabled, the durable profile/order store.
  Superseded values retain their source and audit history.
- `record_proposal_response` records explicit sent-proposal rejection or a
  future followup pause. It preserves reminder send controls and records
  rejection in enabled durable order memory, without sending messages.
- Memory/state writes use a real savepoint. The savepoint helper now correctly
  enters SQLAlchemy transactions implementing both awaitable and async-context
  protocols, rather than accidentally skipping their transaction context.
- Quotation consent, required details, actual catalog SKU/price/stock evidence,
  deduplication, outbound channel authorization, active human handoff and
  transport failure handling remain enforced.
- Existing output factual checks remain. The main model still must use tools
  before claiming completed actions or verified availability/prices.

## Verification contract

`tests/test_model_owned_intent.py` includes the incident and adjacent English,
Russian and Arabic cases, plus 150 migrated original route input boundaries.
They preserve source test IDs, input text, history and initial state. Fourteen
boundaries belong to seven old two-turn scenarios; fixtures explicitly do not
synthesize retired router mutations between those turns. Actual multi-round
model/tool dispatch is checked separately in `test_dialog_scenarios.py`.

This is offline verification with controlled model outputs and mocked external
services. It proves routing, tool/state behavior and safety gates; it does not
claim a fresh live-model semantic score or a production WhatsApp conversation.
No paid model calls or real messages were initiated for this change.

Final results: 1,128 affected tests passed (1,125 in the combined run, followed
by 3 search-contract tests after correcting only their missing test dependency).
Ruff check passed, Ruff format passed for all 391 Python files, and Mypy passed
for all 178 source files. `git diff --check` passed. No full-suite or live-model
acceptance is claimed.

The selected set covers `test_model_owned_intent`, `test_model_search_intent`,
`test_customer_intent_tools`, `test_model_customer_memory`, `test_llm_engine`,
`test_llm_engine_customer_facts`, `test_dialog_scenarios`, `test_llm_quotation`,
`test_customer_memory_service`, `test_proposal_followup`, `test_services_chat`,
`test_services_chat_batch`, `test_llm_response_policy`,
`test_llm_response_policy_guards`, `test_llm_repair_judge`,
`test_llm_message_processor_structure`, `test_llm_message_processor_patch_points`,
`test_outbound_audit`, and `test_wazzup_outbound_safety` under `tests/`.
Commands used the existing canonical Python environment with `PYTHONPATH=.`;
no dependency upgrade or new runtime environment is required.

## Delivery and rollback

Keep this branch/worktree for review and authorized delivery. The running
`noor-reset:tj-0pht` release and test0665-only restrictions were not changed.
Deployment and any live messages require separate owner authorization. A code
rollback restores the prior image/source; no schema migration is required.
Do not replay old inbound messages automatically after deployment or rollback.

Docs-reviewed: updated — runtime ownership, tools and acceptance boundaries.
Graph-reviewed: no-change-needed — no local graph is present or required.
