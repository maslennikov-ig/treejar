---
schema_version: orchestration-artifact/v1
artifact_type: orchestrator-implemented-stream
task_id: tj-gh15.1-2
stage_id: tj-gh15
repo: treejar
branch: codex/tj-gh15-name-escalation-hardening
base_branch: origin/main
base_commit: 3f539f5cd4e404eaab7fc776945d367e6afa07bb
worktree: /home/me/code/treejar/.worktrees/codex-tj-gh15-name-escalation-hardening
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Implementation stayed in the stage worktree; no child worker worktree or branch was created.
risk_level: medium
verification:
  - "uv run pytest tests/test_llm_engine.py::test_extract_bare_name_gate_reply_accepts_only_likely_names tests/test_llm_engine.py::test_process_message_bare_name_reply_resumes_pending_name_gate_request tests/test_llm_engine.py::test_process_message_brand_quantity_selection_stays_on_product_path tests/test_verified_answers.py::test_policy_routes_brand_quantity_selection_to_product_path -q": passed
  - "uv run pytest tests/test_llm_engine.py tests/test_verified_answers.py -q": passed, 183 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" uv run pytest tests/ -v --tb=short": passed, 1033 passed, 19 skipped
  - "scripts/orchestration/run_process_verification.sh": passed
changed_files:
  - src/llm/engine.py
  - src/llm/verified_answers.py
  - tests/test_llm_engine.py
  - tests/test_verified_answers.py
  - .codex/stages/tj-gh15/artifacts/tj-gh15.1-2.md
explicit_defers:
  - tj-gh15.3 production cleanup/live E2E waits for merge and deploy.
---

# Summary

Implemented `tj-gh15.1` / GitHub #36 and `tj-gh15.2` / GitHub #37 locally on
`codex/tj-gh15-name-escalation-hardening`.

For #36, a short bare-name reply such as `Lili` is accepted only while a
`name_gate_pending_request` exists and `customer_name` is still unknown. The
name is stored in conversation and quote metadata, the pending request is
consumed, and the original request resumes with the existing continuation
directive. Product/action/quantity text such as `yes`, `ok`, `4 tables`,
`Skyland Novo`, and `2 Skyland Novo and 2xten` is not accepted as a bare name.

For #37, verified-answer product classification now recognizes Treejar catalog
brand/family terms including `Skyland`, `Novo`, `XTEN`, `Trend`, `Imago`,
drawers, pedestals, cabinets, storage, and work stations. Quantity plus likely
catalog item/brand is kept on the product/catalog path instead of verified-policy
manager handoff.

# Verification

RED tests failed before implementation:

- `test_process_message_bare_name_reply_resumes_pending_name_gate_request`
  could not import the new bare-name helper and current runtime did not handle
  bare `Lili`.
- `test_policy_routes_brand_quantity_selection_to_product_path` classified
  `2 Skyland Novo and 2xten` as `service_low_risk`.

GREEN verification completed:

- New targeted regression suite: 13 passed.
- Modified LLM policy suites: 183 passed.
- Full static checks: `ruff check`, `ruff format --check`, and `mypy` passed.
- Full pytest passed after installing the existing frontend admin lockfile
  dependencies in the clean worktree: 1033 passed, 19 skipped.
- Process verification passed on balanced-v2.7.

# Risks / Follow-ups

`tj-gh15.3` remains pending until this branch is merged, deployed, the approved
production test number `+79262810921` is cleaned in an audited transaction, live
E2E evidence is collected, and GitHub #36/#37 are commented and closed. Lili's
real WhatsApp conversation was used only for read-only root-cause analysis.
