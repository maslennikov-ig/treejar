---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh18.1-2
stage_id: tj-gh18
repo: treejar
branch: codex/tj-gh18-open-issues-hardening
base_branch: origin/main
base_commit: 20bad53c2292
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Spawned Codex worker threads were closed; no child worktrees or child branches required cleanup.
risk_level: medium
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py tests/test_services_chat_batch.py tests/test_outbound_audit.py tests/test_messaging_wazzup.py -v --tb=short: passed, 246 passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed, 1056 passed, 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh18/artifacts/tj-gh18.1-2.md: passed
  - OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh18: passed
changed_files:
  - src/llm/engine.py
  - src/llm/prompts.py
  - src/llm/verified_answers.py
  - tests/test_llm_engine.py
  - tests/test_outbound_audit.py
  - tests/test_services_chat_batch.py
  - tests/test_verified_answers.py
explicit_defers:
  - tj-gh18.3 tracks merge/deploy/live E2E/GitHub closure for gh-39 and gh-35.
---

# Summary

Accepted and reviewed the two delegated streams for `tj-gh18`.

Stream A fixed GitHub #39 by extending deterministic SKU selection handling and
verified-answer classification. The orchestrator found a regression risk in the
first worker implementation of SKU catalog lookup, replaced it with a single
priority-ordered SQLAlchemy query, and re-ran the affected tests and full suite.

Stream B verified GitHub #35 at the send boundary. The production send path
already suppressed customer-visible captions when `send_caption=False`; tests now
prove the provider receives `caption=None`, no caption CRM id is sent, and hidden
caption audit rows remain non-customer-visible for future product selection
resolution.

# Verification

- Critical regressions for SKU variants, no handoff, and media captions: `9 passed`.
- Full targeted modified suites: `246 passed`.
- Static gates: `ruff check`, `ruff format --check`, and `mypy` passed.
- Full pytest: `1056 passed, 19 skipped`.
- Process verification passed on `balanced-v2.7`.
- Artifact validation and stage closeout passed.

# Delivery / Cleanup

Work was accepted through manual integration in the stage branch. Both visible
Codex worker threads were closed after review. No child branches or worktrees
were created by the workers, so cleanup is complete.

# Risks / Follow-ups / Explicit Defers

- No deploy, production cleanup, live WhatsApp/media test, or GitHub issue
  closure was performed in this local implementation step.
- `tj-gh18.3` tracks the required delivery and comprehensive deployed E2E matrix
  before GitHub #39/#35 can be commented and closed.
