---
schema_version: orchestration-artifact/v1
artifact_type: local-implementation
task_id: tj-nzob
stage_id: tj-nzob
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: single local parser/test stream; no spawned subagent justified
repo: treejar
branch: codex/tj-nzob-comma-brief
base_branch: main
base_commit: c6185f2c85373ed9409abd30208554411d70ec75
worktree: /home/me/code/treejar
write_zone:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-nzob
  - .codex/handoff.md
success_criteria:
  - comma-separated ordered quote brief stores name/company/email/address
  - quote resume continues without asking for company again
  - slash and multiline ordered brief behavior remains covered
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/project-index.md
  - .codex/stages/tj-mmj8/summary.md
  - .codex/stages/tj-mmj8/artifacts/tj-mmj8-production-e2e.md
  - .codex/stages/tj-4xnf/summary.md
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /mnt/c/Users/user/.codex/superpowers/skills/systematic-debugging/SKILL.md
  - /mnt/c/Users/user/.codex/superpowers/skills/test-driven-development/SKILL.md
  - /mnt/c/Users/user/.codex/superpowers/skills/verification-before-completion/SKILL.md
selected_agents:
  - none - single local write zone and direct verification were sufficient
catalog_candidates:
  - none - installed skills covered the workflow
parallel_group: parser-fix
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: current delivery branch must remain until user authorizes merge/push/deploy or cleanup
risk_level: medium
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary/artifact and handoff updated; project index unchanged
verification:
  - "uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k 'unlabeled_quote_brief_completes_pdf_details'": passed after RED failure
  - "uv run --extra dev python -m pytest tests/test_llm_engine.py -q -k 'quote_customer_details or customer_details_resume or exact_quote or sales_order_resolved_followup_then_brief_creates_quote or unlabeled_quote_brief'": passed
  - "uv run --extra dev python -m pytest tests/test_llm_engine.py -q": passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed after npm ci --prefix frontend/admin
  - "scripts/orchestration/run_stage_closeout.py --stage tj-nzob": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/handoff.md
  - .codex/stages/tj-nzob/summary.md
  - .codex/stages/tj-nzob/artifacts/tj-nzob-local-implementation.md
explicit_defers:
  - merge/push/deploy/live E2E require explicit user approval
---

# Summary

The local fix extends deterministic ordered quote brief parsing to the
high-confidence comma-separated format found during `tj-mmj8` production E2E.
The bot now treats `Lilia, LLD, Lfdsf@kfsl.ru, 2 street` as a complete customer
brief and can continue quotation creation without asking for company again.

# Scope / Routing

This stayed local because the implementation, tests, and verification are one
coupled parser stream. No spawned subagent was used. No external dependency
documentation lookup was needed because the behavior is repo-local parser logic.
Graphify is not configured in this repository.

# Verification

The regression was first added to the existing quote resume test and observed
failing with `mock-model|quote-resume-missing-details`. After the parser change,
the targeted test, the broader quote/customer-detail slice, and the full
`tests/test_llm_engine.py` file passed. Full pytest initially exposed missing
local frontend dependencies (`esbuild`); after `npm ci --prefix frontend/admin`,
the full test suite passed.

# Delivery / Cleanup

Local implementation is accepted on the feature branch. No merge, push, deploy,
production smoke, live WhatsApp E2E, or branch cleanup has been performed.

# Risks / Follow-ups / Explicit Defers

Runtime delivery and live E2E require separate user approval.
