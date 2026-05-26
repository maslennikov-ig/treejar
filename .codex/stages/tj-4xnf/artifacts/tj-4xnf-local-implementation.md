---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-4xnf
stage_id: tj-4xnf
agent_type: n/a-local-orchestrator
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Single coupled customer-resolution bug; no independent parallel stream.
repo: treejar
branch: codex/tj-4xnf-zoho-customer-fallback
base_branch: main
base_commit: 069e4f91bb5b2d1b4c4b1c6b45d1e5caac11bc94
worktree: /home/me/code/treejar
write_zone:
  - src/llm/engine.py
  - tests/test_llm_quotation.py
success_criteria:
  - Zoho Inventory customer lookup and create_contact payload use the real base WhatsApp phone when the app conversation phone has a repo-owned synthetic # suffix.
  - Existing duplicate-name fallback remains covered.
  - Exact quote fail-closed behavior is preserved if a customer still cannot be resolved or created.
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-8ma2/artifacts/tj-8ma2-production-e2e.md
selected_skills:
  - orchestrator-stage
  - systematic-debugging
  - test-driven-development
  - verification-before-completion
selected_agents:
  - none - one local state-boundary bug; no separate subagent authorization needed.
catalog_candidates:
  - none - repo-local tests and existing implementation were sufficient.
parallel_group: local-single-stream
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: No child worktree was created; current feature branch is retained pending owner decision on merge/push/deploy/live E2E.
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Stage summary, artifact, and handoff updated; stable operator/API docs unchanged because no public API or operator procedure changed.
verification:
  - uv run --extra dev python -m pytest tests/test_llm_quotation.py -q -k 'synthetic_suffix_for_zoho or duplicate_name_conflict': failed before implementation, then passed
  - uv run --extra dev python -m pytest tests/test_llm_quotation.py tests/integrations/test_zoho_inventory.py -q: passed, 20 passed
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k 'quote_customer_details or customer_details_resume or exact_quote or sales_order_resolved_followup_then_brief_creates_quote': passed, 46 passed / 174 deselected
  - uv run --extra dev ruff check src/ tests/: passed
  - uv run --extra dev ruff format --check src/ tests/: passed after formatting the new test
  - uv run --extra dev mypy src/: passed
  - scripts/orchestration/run_stage_closeout.py --stage tj-4xnf: passed, 1181 passed / 19 skipped plus process verification and orchestration closeout checks
changed_files:
  - src/llm/engine.py
  - tests/test_llm_quotation.py
explicit_defers:
  - Merge, push, deploy, and live WhatsApp E2E require explicit owner approval.
  - tj-nzob remains a separate parser bug.
---

# Summary

Implemented the remaining local fix for `tj-4xnf`. Inventory customer
resolution now strips repo-owned synthetic `#...` suffixes before calling Zoho
Inventory lookup or `create_contact`, while keeping the suffixed phone in app
conversation storage.

# Scope / Routing

Parallel Decomposition Matrix: one local stream. The write zone is
`src/llm/engine.py` and `tests/test_llm_quotation.py`. The bug is a single
external-boundary issue: the live synthetic phone suffix leaked into Zoho
Inventory contact lookup/create, while Wazzup outbound already strips it.

Prior-work check found commit `e97bbb4` already covers duplicate-name fallback.
The current live failure is different: the phone sent to Inventory included the
E2E suffix digits and suffix text. `tj-nzob` was also checked and remains
unfixed, but it is a separate quote-brief parser task.

# Verification

The new regression failed before implementation because
`find_customer_by_phone` received
`+79262810921#tj-8ma2-salesorder-mixed-20260526-200552`. After the fix it passed
and asserted that both lookup and create-contact phone/mobile payloads use
`+79262810921`.

Targeted quotation, Inventory, and engine quote-resume tests passed. Ruff,
format check, and mypy passed after formatting the new test.

# Delivery / Cleanup

This is a local branch implementation only. It has not been merged, pushed,
deployed, or live-E2E tested. No extra worktree was created.

# Risks / Follow-ups / Explicit Defers

Live production retest is still needed after merge/deploy to verify that the
same sales-order quote path can create the quotation instead of fail-closing on
Inventory customer resolution. `tj-nzob` remains separate.
