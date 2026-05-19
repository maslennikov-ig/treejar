---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-gh19.1-2
stage_id: tj-gh19
repo: treejar
branch: codex/tj-gh19-quote-context-hardening
base_branch: origin/main
base_commit: f268e17ea0cf
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh14-main-merge
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Implementation stayed local/sequential; read-only Codex reviewer completed without child write artifacts.
risk_level: medium
verification:
  - OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -v --tb=short: passed, 212 passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - git diff --check: passed
  - uv run mypy src/: passed
  - env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short: passed, 1063 passed, 19 skipped
  - uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-gh19/artifacts/tj-gh19.1-2.md: passed
  - scripts/orchestration/run_process_verification.sh: passed
  - OPENROUTER_API_KEY=dummy scripts/orchestration/run_stage_closeout.py --stage tj-gh19: passed
changed_files:
  - src/llm/engine.py
  - src/llm/prompts.py
  - tests/test_llm_engine.py
explicit_defers:
  - tj-gh19.3 tracks merge/deploy/production E2E/GitHub #40 closure.
---

# Summary

Accepted the local sequential implementation for `tj-gh19.1` and `tj-gh19.2`.

The quote-context fix parses terse active quotation details such as
`Lil, 1 dubay` only when a pending quote exists and the assistant just asked for
quotation details. It stores usable name/address values, keeps
`pending_quote_selection`, blocks `create_quotation` until all required details
are present, and answers with the targeted missing-details prompt instead of
the generic opener.

The quantity fix prevents model numbers in known model/family names such as
`SKYLAND NOVO 2400` from becoming quantities for a later SKU, while preserving
the prior #39 SKU variants including `CH 616`, `CH-616`, `CH616`, repeated
spaces, and Cyrillic homoglyph `СН 616`.

# Verification

- RED tests were run first for the #40 context and model-number symptoms; they
  failed on the expected old behavior.
- Targeted LLM/verified-answer suites passed: `212 passed`.
- Static checks passed: `ruff check`, `ruff format --check`, `git diff --check`,
  and `mypy`.
- Full pytest passed: `1063 passed, 19 skipped`.
- Artifact validation, process verification, and stage closeout passed.
- Read-only review subagent found no P0/P1 defects; its suggested extra
  homoglyph purchase-selection case was added and verified.

# Delivery / Cleanup

No child branch or child worktree was created for write-heavy work because both
defects touched the same central routing files. The read-only Codex reviewer
made no file changes, so cleanup is complete.

# Risks / Follow-ups

- No merge, deploy, production cleanup, live WhatsApp test, GitHub comment, or
  GitHub closure was performed in this local implementation step.
- `tj-gh19.3` tracks delivery and deployed E2E before GitHub #40 can be closed.
