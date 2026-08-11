---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-mshi-permission-list/stage-manifest.json
stream_owner: tj-mshi.4-root-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-mshi.5-blind-measured-round
public_facade: build_system_prompt
bounded_acceptance: registry-subsumed-prompt-prohibition-removal
non_goals:
  - deterministic-commitment-check
  - customer-text-repair-path
  - scoring-rubric-change
evidence:
  - protected-policy-replay-under-git-common-dir
task_id: tj-mshi.4
epic_id: tj-mshi
stage_id: tj-mshi-permission-list
session_id: tj-mshi-permission-list
milestone: registry-only-commercial-promise-contract
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned sequential P0 prompt-contract removal
repo: treejar
branch: main
base_branch: main
base_commit: 1b3f34c
worktree: /home/me/code/treejar
write_zone:
  - src/llm/prompts.py
  - src/llm/communication_policy.py
  - tests/test_llm_prompts.py
  - .codex
success_criteria:
  - named-prohibition-blocks-removed-without-replacement-prohibition
  - grounding-output-tests-byte-identical-and-green
  - protected-policy-replay-unchanged
  - recruitment-redirect-has-no-routing-or-callback-promise
selected_docs:
  - docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md
  - docs/plans/2026-08-11-permission-list-plan.md
  - docs/plans/2026-08-11-promise-types-for-ratification.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
  - superpowers-verification-before-completion
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - tj-mshi.3-root-implementation
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: root-owned main worktree; no child worktree or branch existed
risk_level: high
verification_tier: release
risk_tags:
  - prompt-contract-change
  - grounding-backstop-preservation
  - protected-corpus-replay
affected_surfaces:
  - backend
invariants:
  - one-commercial-promise-registry
  - untouched-grounding-output-backstop
  - no-customer-text-repair-added
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: stage summary and handoff record all removed duplicates, declared assertion replacements, replay evidence, and measured recruitment follow-up
verification:
  - focused removal tests failed on the discount duplicate customer-owned block and future-check prohibition, then passed: 3 passed
  - recruitment redirect phrasing-family test: passed
  - tests/test_llm_grounding_output.py passed untouched: 107 passed; sha256 9cd7c94e22ff029702271040db3b80cd4d416b761645abf0ca6c3e641cbe7917
  - protected full-chain replay: 60 checked, 0 mismatches, digest 1b0b2963480c08e466a8d44133e763a2ede3fa423d5dc4b0f2f327f383411052
  - root read recruitment redirect: sales-channel and official-route response, application stays with sender, no forwarding callback or shortlist promise
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed over 369 files after formatting the added test
  - uv run mypy src/: passed over 173 source files
  - uv run pytest tests/ -v --tb=short: 3561 passed and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - .codex/handoff.md
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-mshi-permission-list/stage-manifest.json
  - .codex/stages/tj-mshi-permission-list/summary.md
  - .codex/stages/tj-mshi-permission-list/artifacts/tj-mshi.4.md
  - src/llm/communication_policy.py
  - src/llm/prompts.py
  - tests/test_llm_prompts.py
explicit_defers:
  - tj-riim-closes-in-tj-mshi.5-only-if-the-new-dialog-28-reply-holds-the-redirect
---

# Summary

The customer-owned-furniture block, both future-check prohibitions, the greeting
stage's duplicate deferred-answer promise, and the compact policy's duplicate
discount rule are gone. Their ratified positive conditions remain once in
`COMMERCIAL_CAPABILITIES`; no compensating prohibition was added.

# Scope / Routing

Root-owned sequential work on `main`. This child removed only prompt rules now
owned by the registry. It did not change any response guard, add a deterministic
commitment check, or add a customer-text repair path.

# Declared test removal and replacement

`test_llm_prompts.py::test_customer_owned_furniture_prompt_covers_the_service_promise_family`
was **removed and replaced** by
`test_customer_owned_furniture_redirect_covers_the_service_promise_family`.
The replacement holds the same phrasing family against the `not_offered`
registry entry. This was a declared removal, not a test edited to accommodate a
move. The owner also authorized replacing the stale future-check and discount
prompt-text assertions with positive registry ownership and absence checks.

# Verification

`test_llm_grounding_output.py` passed untouched: all 107 tests passed and its
SHA-256 stayed
`9cd7c94e22ff029702271040db3b80cd4d416b761645abf0ca6c3e641cbe7917`.
The protected replay was widened from the required historical 31 to all 60 raw
assistant outputs across the three measured rounds; the full policy chain
changed zero outputs and retained aggregate digest `1b0b2963…`.

The root read the recruitment redirect itself. It names the sales channel and
official route, leaves the application with the sender, and promises no
forwarding, callback, or shortlist. A phrasing-family test holds that contract.
The actual new dialog 28 generation is deliberately left for the authorized
measured round `.5`; `tj-riim` closes only if that reply also holds.

Ruff, format, Mypy, the complete Pytest suite, and process verification passed.

# Delivery / Cleanup

Accepted directly in the root worktree for one local child commit. Protected
replay content stayed under `.git`; tracked evidence contains counts and digests
only. No paid call, push, deploy, live mutation, or real-user message occurred.

# Risks / Follow-ups

`tj-riim` remains open only through the immediately following measured child.
Its new dialog 28 output must be read by the root before the bug closes; a
failure reopens the permission wording rather than adding a prohibition.
