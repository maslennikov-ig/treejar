---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh22
stage_id: tj-gh22
repo: treejar
branch: codex/tj-gh22-fu1-service-window
base_branch: origin/main
base_commit: 32dabb352e8aa8cb584ca575651835a82aef2e0b
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: merged
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: branch/worktree retained until docs/E2E-plan commit is pushed
risk_level: low
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py -v --tb=short: failed before implementation as expected on old 24h FU1 schedule
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_proposal_followup.py tests/test_webhook.py::test_wazzup_webhook_read_status_records_proposal_read_without_reschedule tests/test_llm_prompts.py::test_build_system_prompt_includes_compact_communication_policy -v --tb=short: passed (21 passed)
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed (1115 passed, 19 skipped)
  - scripts/orchestration/run_process_verification.sh: passed
  - GitHub Actions run 26233690578: passed, including deploy
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed (7 passed, 0 failed)
changed_files:
  - src/services/proposal_followup.py
  - src/llm/communication_policy.py
  - tests/test_proposal_followup.py
  - tests/test_webhook.py
  - tests/test_llm_prompts.py
  - docs/client/wazzup-waba-followup-setup-guide.md
explicit_defers:
  - production follow-up sending still requires explicit configuration of FU1 free-form text and approved Wazzup WABA template ids/codes for FU2/FU3
  - live E2E execution is tracked separately in tj-gh22.1
---

# Summary

Implemented the FU1 service-window refinement locally. FU1 now becomes due at 23 hours instead of 24 hours, and the existing send planner still verifies the actual WhatsApp free-form window from the last customer inbound message before sending.

Merged the branch into `main`, deployed runtime commit `3f0ed132a12f90c6d2087f40697f0fcdc0c2b3a6` through GitHub Actions run `26233690578`, and verified production API smoke against `https://noor.starec.ai`.

# Verification

- RED test run failed on the old 24h FU1 schedule as expected.
- Targeted follow-up/webhook/prompt tests passed: 21 passed.
- Ruff, format check, mypy, full pytest, and process verification passed locally.
- GitHub Actions run `26233690578` passed, including deploy.
- Production smoke passed: `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> 7 passed, 0 failed.

# Risks / Follow-ups

This does not make unsafe free-form sends possible: if the real 24h window has closed, the code still requires a WABA template or blocks the send. The client WABA guide now asks for mandatory FU2/FU3 templates only, with optional FU1 fallback templates.

Full production E2E is planned in `docs/specs/e2e-testing/tj-gh22-post-quotation-followup-e2e-plan.md` and tracked in Beads as `tj-gh22.1`.
