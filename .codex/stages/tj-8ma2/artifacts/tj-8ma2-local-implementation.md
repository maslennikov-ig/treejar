---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-8ma2
stage_id: tj-8ma2
agent_type: n/a-local-orchestrator
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: Single coupled state-machine bug in src/llm/engine.py; no independent parallel stream.
repo: treejar
branch: main
base_branch: main
base_commit: bc03a8fdb5db71744c5ce6ad18d963a3ebc24063
worktree: /home/me/code/treejar
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
success_criteria:
  - After a sales-order unresolved item is clarified as CH 620 grey x 5, the resolved item is preserved in pending_quote_selection when customer PDF details are still missing.
  - A following multiline/slash customer brief is stored as quote_customer_details and resumes quotation creation.
  - The brief must not be reinterpreted as unresolved item text.
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-mmj8/artifacts/tj-mmj8-production-e2e.md
selected_skills:
  - orchestrator-stage
  - systematic-debugging
  - test-driven-development
selected_agents:
  - none - single local stream; current user did not request spawned subagents and the bug is one coupled route.
catalog_candidates:
  - none - installed workflow skills and repo-local tests covered the task.
parallel_group: local-single-stream
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Feature branch merged to main, pushed/deployed, then deleted locally after delivery; no extra worktree remained.
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Stage summary, artifact, and handoff updated; stable API/operator docs unchanged because no public API, route, deploy, or operator procedure changed.
verification:
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k sales_order_resolved_followup_then_brief_creates_quote: failed before implementation on stale unresolved pending_quote_selection, then passed
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k "sales_order_unresolved or sales_order_resolved_followup_then_brief_creates_quote or customer_details_resume_pending_quote_selection or unlabeled_quote_brief_completes_pdf_details or exact_quote_unresolved_followup_resolves_sku_and_quantity": passed, 7 passed
  - uv run --extra dev python -m pytest tests/test_llm_engine.py -q: passed, 220 passed
  - uv run --extra dev ruff check src/ tests/: passed
  - uv run --extra dev ruff format --check src/ tests/: passed
  - uv run --extra dev mypy src/: passed
  - uv run --extra dev python -m pytest tests/ -q --ignore=tests/test_admin_dashboard_frontend.py: passed, 1169 passed / 19 skipped
  - scripts/orchestration/run_process_verification.sh --stage tj-8ma2: passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
explicit_defers:
  - Residual Zoho Inventory create_contact HTTP 400 finalization failure is tracked separately as tj-4xnf.
---

# Summary

Implemented a local TDD fix for `tj-8ma2`. A resolved sales-order quote
follow-up now persists the resolved item selection before `create_quotation`
runs. If quotation creation stops to ask for customer PDF details, the next
brief reply resumes from the preserved `CH 620 grey x 5` item instead of
rewriting the pending selection as an unresolved item built from customer
details.

# Scope / Routing

Parallel Decomposition Matrix: one stream, local, write zone
`src/llm/engine.py` and `tests/test_llm_engine.py`. The failure is a single
state-machine ordering issue in `process_message`: sales-order follow-up
resolution called `create_quotation` without first updating
`pending_quote_selection` to the resolved items.

# Verification

The new regression failed before the implementation because
`pending_quote_selection` still contained the old unresolved `CH 620 grey`
after the item clarification. After the fix, the regression, seven related
quote-resume tests, full `tests/test_llm_engine.py`, ruff, format check, mypy,
process verification, and the broad Python suite excluding the frontend
dashboard regression file passed.

# Delivery / Cleanup

The local implementation was fast-forwarded into `main` as
`80e6f4371da44f163406f76f30f858e94d35da4a`, pushed to `origin/main`, deployed
by GitHub Actions run `26462939020`, and verified on production. The local
feature branch was deleted after delivery. No extra worktree was created.

# Risks / Follow-ups

No in-scope `tj-8ma2` blocker remains. Live E2E exposed a separate Zoho
Inventory customer-resolution failure after the fixed state-machine path reached
`create_quotation`; that residual is tracked under `tj-4xnf`. `tj-nzob`
remains separate.
