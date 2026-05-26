---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-4cm4
stage_id: tj-4cm4
agent_type: n/a-local-orchestrator
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Single coupled bugfix in src/llm/engine.py; no independent parallel stream.
repo: treejar
branch: codex/tj-4cm4-exact-sku-resume
base_branch: main
base_commit: 57e4bd303494c5d822dcdfc4b8381a62cbf0ead8
worktree: /home/me/code/treejar
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
success_criteria:
  - Exact quote item clarification reply with SKU and quantity resolves pending CH 620 to CH 620 grey x 5.
  - The clarification reply does not overwrite quote address metadata with "quantity 5".
  - The bot resumes quotation detail/PDF flow instead of asking for item(s)/quantity again.
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-mmj8/summary.md
selected_skills:
  - orchestrator-stage
  - systematic-debugging
  - test-driven-development
selected_agents:
  - none - single local stream; no explicit subagent spawn authorization for this focused fix.
catalog_candidates:
  - none - installed workflow skills covered the task.
parallel_group: local-single-stream
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: Branch retained until explicit merge/deploy decision; no separate stage worktree was created.
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Stage summary, artifact, and handoff updated; stable API/operator docs unchanged because no public contract, route, deploy, or operator procedure changed.
verification:
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k exact_quote_unresolved_followup_resolves_sku_and_quantity: passed after RED failed on quote-resume-missing-items
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k "exact_quote_unresolved or sales_order_unresolved_followup_resumes_quote or customer_details_resume_pending_quote_selection": passed, 4 passed
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q: passed, 219 passed
  - uv run --extra dev ruff check src/ tests/: passed
  - uv run --extra dev ruff format --check src/ tests/: passed
  - uv run --extra dev mypy src/: passed
  - uv run --extra dev python -m pytest tests/ -q: failed, 7 frontend regressions blocked by missing frontend/admin node_modules esbuild
  - uv run --extra dev python -m pytest tests/ -q --ignore=tests/test_admin_dashboard_frontend.py: passed, 1168 passed, 19 skipped
  - scripts/orchestration/run_process_verification.sh --stage tj-4cm4: passed
  - scripts/orchestration/run_stage_closeout.py --stage tj-4cm4: blocked because delivery/merge is intentionally deferred and the closeout script requires delivery mini-closeout for accepted streams
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - Deploy, push, merge, and live WhatsApp E2E require explicit approval.
  - Full pytest including tests/test_admin_dashboard_frontend.py requires installing frontend/admin node dependencies; skipped to avoid adding node_modules during disk cleanup work.
---

# Summary

Implemented a local TDD fix for `tj-4cm4`. A pending exact quote with an
unresolved catalog item now treats replies such as
`The exact SKU is CH 620 grey, quantity 5.` as item clarification, preserves the
original quantity, resolves the clarified SKU, and resumes quote creation or
quote-detail gating.

# Scope / Routing

Parallel Decomposition Matrix: one stream, local, write zone
`src/llm/engine.py` and `tests/test_llm_engine.py`, dependent on the exact quote
resume path, verified by targeted engine tests plus lint/type checks. No
subagent was spawned because the parser, metadata guard, and resume behavior are
one coupled control path.

# Verification

The new regression failed before implementation with the existing
`quote-resume-missing-items` answer, then passed after the fix. Full
`tests/test_llm_engine.py`, ruff, format check, mypy, and all Python tests except
the frontend dashboard regression file passed.

# Delivery / Cleanup

Local implementation is accepted on branch `codex/tj-4cm4-exact-sku-resume`.
Stage closeout is blocked until delivery is authorized because the closeout
script requires accepted streams to have a delivery mini-closeout. No merge,
push, deploy, live WhatsApp test, or branch cleanup was performed.

# Risks / Follow-ups / Explicit Defers

The remaining production confidence step is deployment plus a bounded live E2E
retest for the original `CH 620 grey` clarification scenario after approval.
