---
schema_version: orchestration-artifact/v1
artifact_type: orchestrator-triage
task_id: tj-order-state.9
stage_id: tj-order-state
repo: treejar
branch: codex/tj-order-state-refactor
base_branch: main
base_commit: 5c85a5b46d28320a1790196b48651ad6bc01a41f
worktree: /home/me/code/treejar
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: read-only review reports were persisted; accepted fixes were implemented locally in the stage branch
risk_level: high
verification:
  - targeted review-fix suite passed: 22 passed, 307 deselected
  - high-signal review-fix suite passed: 107 passed, 225 deselected
  - changed-module suite passed: 332 passed
  - full repository pytest passed before artifact normalization: 1333 passed, 19 skipped
  - stage closeout passed: stage closeout verification OK
changed_files:
  - src/dialogue/catalog_refs.py
  - src/dialogue/order_guards.py
  - src/dialogue/order_runtime.py
  - src/dialogue/order_state.py
  - src/llm/engine.py
  - src/llm/fact_extractor.py
  - src/services/customer_memory.py
  - tests/
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/customer-facts-layer.md
  - .codex/stages/tj-order-state/
explicit_defers:
  - none
---

# Summary

## Review Routing

Mandatory read-only review streams were run as visible spawned Codex
subagents: `correctness_reviewer` and `improvement_reviewer`.

Triggered read-only specialists were also run as visible spawned Codex
subagents: `reviewer`, `code_health_reviewer`, `architect_reviewer`,
`api_designer`, `qa_expert`, `prompt_regression_tester`, `llm_architect`,
`risk_manager`, `responsible_ai_reviewer`, `docs_reviewer`,
`security_auditor`, and `performance_engineer`.

Individual reports are persisted as `review-*.md` artifacts in this directory.

## Accepted Must-Fix Findings

- `tj-order-state.9.1`: fixed mixed complete-plus-missing order lines entering
  partial `PurchaseSelection`; blocked connector false SKUs `AND-4`, `OR-4`,
  and `BUT-8`; made order inquiry blockers intent-aware and multilingual.
- `tj-order-state.9.3`: made deterministic `order.items` canonical for
  single-line and multi-line runtime selections; memory accepts
  `order.items` only from deterministic, valid snapshots and supersedes older
  snapshots.
- `tj-order-state.9.4`: redacted contact PII from fast-model customer-facts
  requests; dropped fast-model `order.items`; changed order-items evidence to
  item-only text; marked customer facts prompt context as untrusted data.
- `tj-order-state.9.5`: added transcript and regression coverage for review
  findings, including slash-separated quote details plus item correction.

## Accepted High-Value Improvements Implemented In Follow-Up

- `tj-order-state.9.2`: compact `order_runtime_trace` and phase latency were
  added, and plain static selection now runs before FAQ/behavior retrieval when
  quote/service gates are not active.
- `tj-order-state.9.6`: exact-quote missing-details safety copy is localized
  for Arabic flows.

## Rejected Or Not Actioned

- Adding Rasa or Parlant runtime: rejected for this stage. Their flow and repair
  patterns remain references, but adding a new runtime would add migration and
  operational surface without replacing the existing LangGraph/Pydantic stack.
- Moving Zoho/PDF/WhatsApp side effects into the order runtime: rejected for
  this stage. The runtime must remain a side-effect-free contract until a
  separate side-effect migration has dedicated tests.
- Moving quote-like or service-policy turns ahead of quote/service gates:
  rejected. The early shortcut is limited to plain static purchase selection.

## Top 3 Recommended Next Improvements

1. Run an explicitly approved live WhatsApp/API E2E before any production
   delivery.
2. Monitor bounded `order_runtime` traces after delivery to validate route and
   latency behavior on real conversations.
3. Consider a later dedicated side-effect migration only if Zoho/PDF/WhatsApp
   ownership can move behind the typed contract with its own tests.

# Verification

- Targeted review-fix suite passed: `22 passed, 307 deselected`.
- High-signal review-fix suite passed: `107 passed, 225 deselected`.
- Changed-module suite passed: `332 passed`.
- Full repository pytest passed before artifact normalization:
  `1333 passed, 19 skipped`.
- Final stage closeout was rerun after artifact normalization:
  `stage closeout verification OK`.

# Risks / Follow-ups

- No explicit defers remain for `tj-order-state.9.2` or `tj-order-state.9.6`.
- No live WhatsApp/API E2E, deploy, GitHub issue close, or production mutation
  was run in this review-fix pass.
