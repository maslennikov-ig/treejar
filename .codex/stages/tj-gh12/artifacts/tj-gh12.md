---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh12
stage_id: tj-gh12
repo: treejar
branch: codex/tj-gh12-new-issues
base_branch: origin/main
base_commit: 838d3d65887947452b2e77e75c633848a37fa2b9
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh12-new-issues
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Built-in subagent changes were reviewed and integrated into the stage worktree; no child git branches needed cleanup.
risk_level: medium
verification:
  - "Code-review RED regressions for exact quote fallback, mixed invalid quote items, unsupported typing loop, Wazzup typing no-op, and stage script tomllib bootstrap: failed before fixes, 6 failed"
  - "Code-review GREEN regressions for exact quote fallback, mixed invalid quote items, unsupported typing loop, Wazzup typing no-op, and stage script tomllib bootstrap: passed, 6 passed"
  - "Follow-up code-review RED regressions for price-as-SKU parsing, artifact-required closeout, and proposal template transport confirmation: failed before fixes, 6 failed"
  - "Follow-up code-review GREEN regressions plus adjacent happy paths: passed, 13 passed"
  - "uv run pytest tests/test_proposal_followup.py tests/test_webhook.py tests/test_scripts_process_verification.py targeted LLM SKU/exact-quote tests -v --tb=short: passed, 39 passed"
  - "uv run pytest tests/test_proposal_followup.py tests/test_webhook.py -v --tb=short: passed, 22 passed"
  - "uv run pytest targeted review/quotation/typing/process-verification set -v --tb=short: passed, 12 passed"
  - "uv run pytest tests/test_scripts_process_verification.py::ProcessVerificationTests::test_process_verification_uses_uv_when_python3_lacks_tomllib -v --tb=short: passed"
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short: passed, 1002 passed, 19 skipped"
  - "uv run ruff check src/ tests/: passed"
  - "uv run ruff format --check src/ tests/: passed"
  - "uv run mypy src/: passed"
  - "scripts/orchestration/run_process_verification.sh: passed"
  - "scripts/orchestration/run_stage_closeout.py --stage tj-gh12: passed"
changed_files:
  - .codex/orchestrator.toml
  - .codex/stage-artifact-template.md
  - .codex/handoff.md
  - .codex/stages/tj-gh12/summary.md
  - .codex/stages/tj-gh12/artifacts/tj-gh12.md
  - docs/06-dialogue-evaluation-checklist.md
  - docs/reports/code-reviews/2026-05/CR-2026-05-12-tj-gh12-review.md
  - docs/reports/code-reviews/2026-05/CR-2026-05-13-tj-gh12-follow-up-review.md
  - scripts/bot_test_suite.py
  - scripts/orchestration/check_stage_ready.py
  - scripts/orchestration/cleanup_stage_workspace.py
  - scripts/orchestration/report_child_completion.py
  - scripts/orchestration/review_completion_inbox.py
  - scripts/orchestration/run_process_verification.sh
  - scripts/orchestration/run_stage_closeout.py
  - scripts/orchestration/validate_artifact.py
  - src/api/v1/webhook.py
  - src/integrations/messaging/base.py
  - src/integrations/messaging/wazzup.py
  - src/llm/communication_policy.py
  - src/llm/engine.py
  - src/llm/opening_guard.py
  - src/llm/prompts.py
  - src/quality/evaluator.py
  - src/quality/manager_evaluator.py
  - src/quality/schemas.py
  - src/services/chat.py
  - src/services/proposal_followup.py
  - src/services/report_localization.py
  - src/templates/quotation/style.css
  - src/templates/quotation/template.html
  - src/worker.py
  - tests/services/test_quotation_template.py
  - tests/test_dialog_scenarios.py
  - tests/test_e2e_stage2.py
  - tests/test_e2e_tools.py
  - tests/test_llm_engine.py
  - tests/test_llm_prompts.py
  - tests/test_llm_quotation.py
  - tests/test_messaging_wazzup.py
  - tests/test_opening_guard.py
  - tests/test_proposal_followup.py
  - tests/test_quality_evaluator.py
  - tests/test_quality_transcript_context.py
  - tests/test_report_localization.py
  - tests/test_scripts_process_verification.py
  - tests/test_services_chat_batch.py
  - tests/test_telegram_notifications.py
  - tests/test_webhook.py
explicit_defers:
  - "tj-b4n / GitHub #24: blocked pending an official Wazzup typing endpoint; provider method is a documented no-op and no fake API call is made."
  - "Proposal follow-up sends: disabled by default until approved WhatsApp templates/config are provided; template-mode sends also require confirmed Wazzup template transport schema."
---

# Summary

Implemented the `tj-gh12` Local Beads stage for GitHub issues #21, #22, #24-#33. The stage updates the orchestration baseline to `balanced-v2.7`, changes customer-facing identity to Noor, gates first-turn unknown-name replies, hardens quotation/SKU parsing, exposes price-filtered product search, adds deterministic showroom Maps responses, blocks incomplete quotations, compacts quotation PDFs, adds typing provider infrastructure, and adds disabled-by-default proposal follow-up state, read-status handling, and bounded executor safety gates.

Code review reports:
- `docs/reports/code-reviews/2026-05/CR-2026-05-12-tj-gh12-review.md`
- `docs/reports/code-reviews/2026-05/CR-2026-05-13-tj-gh12-follow-up-review.md`

Review Beads `tj-gh12.7` through `tj-gh12.14` were created and closed after addressing the review findings.

Wazzup typing support is intentionally blocked at provider level because the checked public sending-message docs do not expose a supported typing endpoint. The implementation does not guess or fake an API call.

# Verification

- Code-review RED/GREEN regressions -> failed before fixes (`6 failed`) and passed after fixes (`6 passed`).
- Follow-up code-review RED/GREEN regressions -> failed before fixes (`6 failed`) and passed after fixes (`13 passed` including adjacent happy paths).
- `uv run pytest tests/test_proposal_followup.py tests/test_webhook.py tests/test_scripts_process_verification.py targeted LLM SKU/exact-quote tests -v --tb=short` -> passed (`39 passed`).
- `uv run pytest tests/test_proposal_followup.py tests/test_webhook.py -v --tb=short` -> passed (`22 passed`).
- Targeted review/quotation/typing/process-verification set -> passed (`12 passed`).
- `uv run pytest tests/test_scripts_process_verification.py::ProcessVerificationTests::test_process_verification_uses_uv_when_python3_lacks_tomllib -v --tb=short` -> passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short` -> passed (`1002 passed, 19 skipped`).
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `scripts/orchestration/run_stage_closeout.py --stage tj-gh12` -> passed.

# Delivery / Cleanup

All accepted subagent work was manually integrated in the stage worktree. No child git branches were merged, pushed, or left for cleanup. GitHub issues were not mutated.

# Risks / Follow-ups / Explicit Defers

- `tj-b4n` / GitHub #24 remains blocked until Wazzup provides or confirms an official typing endpoint.
- Proposal follow-up sends remain disabled until approved WhatsApp templates/config are provided; template-mode sends also require confirmed Wazzup template transport schema.
- No deploy, production config mutation, live WhatsApp/media/voice test, GitHub issue comment, or GitHub issue closure was performed.
