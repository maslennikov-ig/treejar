---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: python-pro-task-1
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: tj-ee5f Task 2 acceptance runner and report foundation
public_facade: versioned Noor E2E acceptance manifests and validation API
bounded_acceptance: local-only immutable scope, traceability, scenario, and authorization contracts
non_goals:
  - live/provider/paid/customer/production/Zoho/Wazzup/CRM/quotation/order/deploy/cleanup actions
task_id: tj-ee5f-task-1
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f
milestone: acceptance contracts traceability and scenario set
milestone_status: accepted
agent_type: python_pro
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: public validation and authorization contracts require strict Python schema reasoning
repo: treejar
branch: codex/tj-ee5f-acceptance
base_branch: main
base_commit: b2f74088a0b83147503a1d7d8cd536e3e17639e8
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-acceptance
write_zone:
  - .codex/goals/tj-ee5f/scope-criterion-snapshot.json
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-ee5f/scenario-set.json
  - .codex/stages/tj-ee5f/authorization-manifest.example.json
  - scripts/e2e_acceptance/schemas.py
  - scripts/e2e_acceptance/manifest.py
  - tests/test_e2e_acceptance_manifests.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f-task-1.md
  - .superpowers/sdd/task-1-report.md
success_criteria:
  - immutable thirty-criterion scope anchor with Git creation provenance
  - exact source and regression traceability with owner and observable oracle
  - independent outcome and evidence-mode contracts
  - isolated EN/AR scenarios high-risk variants long journey and separate evidence blocks
  - exact authorization preflight rejects identity target quota permission and expiry drift
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/project-index.md
  - docs/01-tz-basic.md through docs/08-manager-evaluation-criteria.md
  - docs/tz.md
  - docs/superpowers/specs/2026-07-27-noor-agent-driven-e2e-acceptance-design.md
  - relevant named Beads regressions and tj-r1f3 evidence
selected_skills:
  - superpowers:test-driven-development
  - superpowers:receiving-code-review
selected_agents:
  - python_pro
catalog_candidates:
  - none
parallel_group: tj-ee5f-acceptance-contracts
depends_on_streams:
  - accepted tj-ee5f design review
parallel_decision: sequential
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: dedicated worktree retained for orchestrator review; no external or runtime state was created
risk_level: high
verification_tier: slice_acceptance
risk_tags:
  - authorization
  - security
  - state-transition
  - data
affected_surfaces:
  - data
  - backend
invariants:
  - test-matrix
  - state-transition
  - idempotency
docs_impact: api-contract
docs_reviewed: updated
docs_review_notes: task report and versioned manifests document the new acceptance contract; no product/operator documentation changed
verification:
  - initial focused pytest RED missing scripts.e2e_acceptance package: failed as expected
  - source digest drift focused RED: failed as expected
  - reciprocal traceability focused RED: failed as expected
  - closed-dependency transition and unresolved approved placeholders focused RED: failed as expected
  - correction RED collected no tests because build_scenario_binding was absent
  - second correction RED reproduced five policy placeholder referral and TOCTOU failures
  - uv run python -m pytest tests/test_e2e_acceptance_manifests.py -q --tb=short: passed 43
  - focused Ruff and format: passed
  - focused Mypy strict explicit-package-bases: passed
  - full Ruff and format over src tests and scripts/e2e_acceptance: passed
  - full Mypy over 162 source files: passed
  - full Pytest: 1650 passed, 19 skipped, 7 unrelated frontend failures because esbuild is absent in this worktree
  - stage sizing and artifact validators: passed
  - git diff --check: passed
changed_files:
  - .codex/goals/tj-ee5f/scope-criterion-snapshot.json
  - .codex/goals/tj-ee5f/scope-source-provenance.json
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-ee5f/scenario-set.json
  - .codex/stages/tj-ee5f/authorization-manifest.example.json
  - scripts/e2e_acceptance/schemas.py
  - scripts/e2e_acceptance/manifest.py
  - tests/test_e2e_acceptance_manifests.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f-task-1.md
  - .superpowers/sdd/task-1-report.md
explicit_defers:
  - tj-r1f3 remains a hard non-passing external gate until fresh closure and deployed provider proof
  - client-owned referral payment-pricing CRM-stage availability load backup and operator inputs remain explicit external gates
---

# Summary

Implemented the local Task 1 contract boundary: immutable scope identity,
versioned traceability, reproducible scenario ownership, and an exact
authorization preflight. The correction pass binds the immutable anchor to the
exact frozen `tj-ee5f` and `tj-ee5f.1` Beads records, hardcodes the grounding
gate to exactly AC-07 and AC-30, and adds isolated Arabic manager continuity.
The second correction hardcodes the exact criterion/block evidence-mode maps,
models AC-21 implementation versus client exclusion outcomes, narrows
placeholder sentinels, and reads each validated source through one no-following
file descriptor. Outcome and evidence mode remain independent.

# Scope / Routing

The execution boundary is `scripts/e2e_acceptance/manifest.py`: it reads only
local JSON and Git/Beads provenance, validates Pydantic contracts, compares the
scope anchor with its first Git blob, verifies actual source content digests,
section locators, path containment and symlink safety from the same descriptor,
and rejects authorization or canonical scenario/executable-input drift before
any future live caller may act.

# Verification

TDD demonstrated intended failures for the absent package, source provenance
drift, non-reciprocal traceability ownership, dependency-transition state, and
unresolved approved placeholders. The correction RED then failed collection
because the new scenario-binding API did not exist. The second correction RED
reproduced five concrete failures: mutable policy maps, absent AC-21 resolution
semantics, missing referral permission, a legitimate `manager_draft_prompt`
false positive, and source reopening by path. The final focused suite passes 43
tests, including recursive placeholder keys/leaves, exclusive expiry,
stop-condition drift, both grounding transition states, source path escape,
symlink/no-follow rejection, same-descriptor hashing/section validation, exact
opened-inode stability across path replacement, canonical scenario binding, and
Arabic escalation.
Focused and full Ruff/format, strict focused Mypy, full Mypy over 162 source
files, stage sizing, artifact validation, and `git diff --check` pass. Full
Pytest reached 1650 passed and 19 skipped; seven unrelated admin-dashboard
Node tests could not import the missing local `esbuild` package.

# Delivery / Cleanup

The branch is committed for orchestrator review and cherry-pick. No live,
provider, paid, customer, production, CRM, Zoho, quotation, order, deploy, or
cleanup action occurred; there is no external test state to reconcile.

# Risks / Follow-ups / Explicit Defers

`tj-r1f3` is deliberately recorded as `in_progress` and non-passing. The draft
authorization example has zero quotas, no permissions, placeholder identities,
and an expired one-minute window; it cannot authorize execution. Client-owned
inputs remain visible external gates and cannot be counted as PASS. When
`tj-r1f3` closes, the versioned trace manifest must bind the updated named-Beads
digest, remove the open risk, and select
`dependency_closed_freshness_required`; fresh release/provider evidence is
still required and closure alone is not PASS.
