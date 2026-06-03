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
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: Pre-fix synthetic conversation was closed and its test escalation was marked resolved after evidence capture. Post-deploy synthetic conversation ec3c9c10-4677-4a0b-9a7b-d0e8e51c5fef was closed with no escalation. The real base phone conversation was not mutated.
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
  - "git push origin codex/tj-gh48-e2e-service-interruption-fix": passed
  - "git push origin HEAD:main": passed
  - "GitHub Actions run 26841843489": passed, deploy job success
  - "runtime readback /opt/noor/.release-sha": 3d91e54a8de36fa379ac6e2ec1bfcf778cace11e
  - "uv run python scripts/verify_api.py --base-url https://noor.starec.ai": passed, 8 passed and 0 failed
  - "production live E2E on +79262810921#tj-gh48-eaf-20260603055821": passed for delivery/assembly interruption, z-ai/glm-5|service-availability, no escalation
  - "production shadow trace for product preference answer": kernel route product_preference_answer, frame fulfilled workspace_preference=open; visible legacy response remained generic because production mode is shadow
changed_files:
  - src/llm/engine.py
  - tests/test_llm_engine.py
  - .codex/stages/tj-gh48/artifacts/tj-gh48.8-live-e2e-service-interruption.md
  - .codex/stages/tj-gh48/summary.md
  - .codex/handoff.md
explicit_defers:
  - Narrow enforce rollout remains deferred; production is still dialogue_kernel_mode=shadow.
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

The fix was pushed to `codex/tj-gh48-e2e-service-interruption-fix`,
fast-forwarded to `main`, and deployed by GitHub Actions run `26841843489`.
Runtime readback confirms `/opt/noor/.release-sha` is
`3d91e54a8de36fa379ac6e2ec1bfcf778cace11e`.

Post-deploy production E2E used synthetic profile
`+79262810921#tj-gh48-eaf-20260603055821`, conversation
`ec3c9c10-4677-4a0b-9a7b-d0e8e51c5fef`.

- `Can delivery and assembly be arranged in Dubai?` returned
  `z-ai/glm-5|service-availability` and no escalation.
- `I prefer more open for team` fulfilled the stored expected-answer frame in
  the shadow kernel with `workspace_preference=open`. Customer-visible output
  remained legacy/generic because production mode is `shadow`, not enforce.

# Verification

- Local regression and neighbor policy tests passed before delivery.
- Full local gate passed before delivery: `1224 passed, 19 skipped`.
- Process verification passed before delivery.
- Feature branch and `main` pushes succeeded.
- GitHub Actions run `26841843489` completed successfully, including deploy.
- Runtime readback confirmed
  `3d91e54a8de36fa379ac6e2ec1bfcf778cace11e`.
- Production smoke passed: `8 passed, 0 failed`.
- Production live E2E confirmed service interruption no longer escalates.
- Production shadow trace confirmed expected-answer frame fulfillment.

# Risks / Follow-ups

- Production remains in `dialogue_kernel_mode=shadow`; the kernel understood the
  product-preference answer, but the customer-visible answer still came from
  legacy and was generic.
- Narrow `product_selection` enforce rollout remains deferred in `tj-gh48.7` and
  requires separate approval.
