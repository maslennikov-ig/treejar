---
schema_version: orchestration-artifact/v1
artifact_type: orchestrator-implemented-stream
task_id: tj-e2e16.1-3
stage_id: tj-e2e16
repo: treejar
branch: codex/tj-e2e15-detail-capture-hardening
base_branch: origin/codex/tj-long-memory-e2e
base_commit: 9b2df496b38b4c55c296522dfa9c130e9a498b85
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh15-name-escalation-hardening
status: accepted
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Implementation stayed in the stage worktree; no child worker write worktree was created.
risk_level: medium
verification:
  - "Context7 PydanticAI docs: agent.md, testing.md, api/models/test.md": checked
  - "uv run pytest tests/test_llm_engine.py::test_inject_system_prompt_includes_captured_sales_context tests/test_llm_engine.py::test_process_message_company_detail_update_does_not_handoff tests/test_llm_engine.py::test_process_message_address_detail_update_does_not_handoff tests/test_llm_engine.py::test_process_message_sales_memory_note_does_not_handoff tests/test_llm_engine.py::test_process_message_product_quantity_update_stays_with_agent -q": RED before implementation, GREEN after implementation
  - "uv run pytest tests/test_llm_engine.py::test_inject_system_prompt_escapes_captured_sales_context_values tests/test_llm_engine.py::test_process_message_company_detail_with_payment_terms_still_handoffs -q": RED from reviewer findings, GREEN after hardening
  - "uv run pytest tests/test_verified_answers.py tests/test_llm_engine.py -v --tb=short": passed, 191 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed, 1041 passed, 19 skipped
  - "scripts/orchestration/run_process_verification.sh": passed
  - "scripts/orchestration/check_stage_ready.py tj-e2e16": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-e2e16/summary.md
  - .codex/stages/tj-e2e16/artifacts/tj-e2e16.1-3.md
  - .codex/handoff.md
explicit_defers:
  - Merge, deploy, production cleanup for 79262810921%, and repeat live long-dialog E2E remain tracked in tj-e2e16.4 and require explicit delivery approval.
---

# Summary

Implemented `tj-e2e16.1` through `tj-e2e16.3` locally on
`codex/tj-e2e15-detail-capture-hardening`.

The production failure in `tj-e2e15` was not caused by PydanticAI forgetting
`message_history`. The verified-answer policy ran before the agent and treated a
neutral detail update as an unsupported service/policy question. The fix adds a
narrow pre-policy detail-capture path for active sales conversations and stores
durable context for later LLM turns.

Changes in `src/llm/engine.py`:

- Natural labels now accept `The company is ...` and `Delivery address is ...`.
- `conversation.metadata_["sales_memory"]` stores assembly requirement,
  quote-hold intent, and the latest product note.
- The dynamic system prompt gets a `[CAPTURED SALES CONTEXT]` block with escaped,
  explicitly untrusted customer-provided facts.
- Neutral company/address/contact/assembly/no-quote updates in active sales
  context return a static `detail-capture` acknowledgement and avoid manager
  handoff.
- Product/quantity turns such as `Keep the 2 Skyland Novo workstations, but
  compare XTEN and Trend mobile drawers` and `Let's use 3 mobile drawers instead
  of 2. Keep 2 workstations.` remain on the normal agent/product path.
- Payment terms, credit, discounts, complaints, refund/return, and explicit
  human/manager requests still route through normal high-risk handling.

Read-only subagent review found two P1 risks after the first implementation:
payment-term messages were too easy to bypass, and captured prompt context
needed injection hardening. Both were fixed with regression tests before the
full gate run.

# Verification

RED/GREEN coverage was added for the original blocker and reviewer findings:

- `The company is Memory Test LLC.` in active product context stores company and
  does not notify the manager.
- `Delivery address is Bay Square Building 3, Business Bay, Dubai.` stores the
  delivery address and does not notify the manager.
- `Please remember assembly is required, but don't create a quotation yet.`
  stores sales memory and does not notify the manager.
- Product/quantity update turns do not become detail-only acknowledgements and
  do not notify the manager.
- `Company is ABC. Need net 30 payment terms.` still goes through handoff.
- Captured sales context is escaped and marked as untrusted prompt data.

Completed verification:

- Targeted LLM/verified-answer suites: 191 passed.
- Static gates: `ruff check`, `ruff format --check`, and `mypy` passed.
- Full pytest: 1041 passed, 19 skipped.
- Process verification passed on `balanced-v2.7`.
- Stage readiness passed for `tj-e2e16`.

# Risks / Follow-ups

This branch is not deployed. The original production bug `tj-e2e15.2` should
stay open until `tj-e2e16.4` completes: merge, deploy, audited cleanup for the
approved test phone `+79262810921`, and a repeat live long-dialog E2E through the
final memory-summary turns.
