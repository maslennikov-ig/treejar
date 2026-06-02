---
schema_version: orchestration-artifact/v1
artifact_type: live-e2e-fix
task_id: tj-gh48.8
stage_id: tj-gh48
repo: treejar
branch: codex/tj-gh48-e2e-service-interruption-fix
base_branch: origin/main
base_commit: a1775a7be2ffa75536051a9baa52fc2b77df3771
worktree: /home/me/code/treejar/.worktrees/tj-gh48-impl
status: local_fix_ready
delivery_method: not_delivered
accepted_by_orchestrator: yes
cleanup_status: production_synthetic_escalation_resolved
cleanup_notes: Synthetic conversation was closed and its test escalation was marked resolved after evidence capture; the real base phone conversation was not mutated.
risk_level: medium
verification:
  - "production live E2E on +79262810921#tj-gh48-eaf-20260602172558": failed before local fix; simple delivery/assembly interruption returned z-ai/glm-5|verified-policy and created a pending escalation
  - "production cleanup for conversation a1decf1a-b37d-492a-ae50-25dfc02a1962": passed; conversation closed and synthetic escalation resolved
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_process_message_delivery_assembly_interruption_in_expected_frame_answers_without_handoff -v --tb=short": failed before fix, then passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py::test_dialogue_kernel_shadow_records_verified_policy_handoff_route tests/test_llm_engine.py::test_process_message_high_risk_partial_bypasses_agent_with_handoff tests/test_llm_engine.py::test_process_message_high_risk_verified_uses_service_policy_mode tests/test_verified_answers.py -v --tb=short": passed, 40 passed
  - "OPENROUTER_API_KEY=dummy uv run pytest tests/test_llm_engine.py -k 'dialogue_kernel or service or product_preference' -v --tb=short": passed, 18 passed
  - "uv run ruff check src/ tests/": passed
  - "uv run ruff format --check src/ tests/": passed
  - "uv run mypy src/": passed
  - "env DYLD_FALLBACK_LIBRARY_PATH=\"${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}\" OPENROUTER_API_KEY=dummy uv run pytest tests/ -v --tb=short": passed, 1224 passed and 19 skipped
  - "scripts/orchestration/run_process_verification.sh": passed
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-gh48/artifacts/tj-gh48.8-live-e2e-service-interruption.md
  - .codex/stages/tj-gh48/summary.md
  - .codex/handoff.md
explicit_defers:
  - Deploy and production retest are pending explicit approval for this new hotfix branch.
---

# Summary

Live E2E after deploying `tj-gh48` found a new blocker before the expected-answer
preference answer could be tested: a simple service interruption,
`Can delivery and assembly be arranged in Dubai?`, returned a verified-policy
manager handoff.

The production failure was captured on synthetic profile
`+79262810921#tj-gh48-eaf-20260602172558`, conversation
`a1decf1a-b37d-492a-ae50-25dfc02a1962`. The base phone conversation was not
cleaned or changed.

# Findings

- Production mode was correctly `dialogue_kernel_mode=shadow`.
- The expected-answer frame remained active and was not lost.
- The customer-visible legacy route became `z-ai/glm-5|verified-policy`.
- A pending escalation was created because verified policy found no FAQ support
  for the delivery/assembly question.

# Fix

The local hotfix adds a narrow guard in `src/llm/engine.py`: in an active
product-selection or expected-answer context, a low-risk delivery/installation
availability question without concrete timing, guarantee, or outside-UAE scope
returns a deterministic English/Arabic service-availability answer instead of
manager handoff.

True high-risk logistics requests remain unchanged.

# Delivery State

The fix is local on `codex/tj-gh48-e2e-service-interruption-fix`; it has not
been pushed, merged, deployed, or production-retested yet.
