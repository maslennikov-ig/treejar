---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f.4-ci-identity-fix
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: canonical GitHub Actions acceptance compilation
public_facade: TrustedAcceptanceRegistry canonical identity and traceability source validation
bounded_acceptance: canonical HTTPS origin in a fresh checkout accepts only the optional .git suffix, enforces repository path identity, and frozen traceability data is tracked, exact, and fail-closed
non_goals:
  - production deploy or readback
  - provider customer Wazzup Zoho CRM quotation order or paid action
  - changing immutable scope authorization evidence or production safety contracts
task_id: tj-ee5f.4
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f
milestone: CI portability repair for trusted acceptance identity
milestone_status: returned
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: bounded trust-boundary correction in a dedicated worktree
repo: treejar
branch: codex/tj-ee5f-ci-identity-fix
base_branch: main
base_commit: 0b0e0704a20a321ad30872689bafc57f7e3c2f53
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-ci-identity-fix
write_zone:
  - scripts/e2e_acceptance/policy.py
  - scripts/e2e_acceptance/manifest.py
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-ee5f/frozen-beads-records.jsonl
  - tests/test_e2e_acceptance_policy_v2.py
  - tests/test_e2e_acceptance_manifests.py
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.4.md
success_criteria:
  - a simulated fresh checkout accepts the official HTTPS origin with or without .git, and rejects URL variants plus top-level or common-dir identity drift
  - tracked frozen Beads source contains exactly 105 referenced IDs and canonical record digests
  - source validation fails closed on missing extra malformed reordered noncanonical escaped symlinked or digest-drifted data
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
selected_skills:
  - superpowers:test-driven-development
  - superpowers:systematic-debugging
  - orchestrator-stage
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: tj-ee5f
depends_on_streams:
  - tj-ee5f.3 policy-v2 trust center
parallel_decision: local
status: returned
delivery_method: manual integration
accepted_by_orchestrator: no
cleanup_status: not_applicable
cleanup_notes: dedicated worktree retained for orchestrator integration
risk_level: high
verification_tier: integration
risk_tags:
  - security
  - data
  - authorization
affected_surfaces:
  - backend
  - data
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: no-change-needed
docs_review_notes: the tracked traceability manifest and this artifact fully describe the portable source replacement; no durable user documentation changed
verification:
  - RED: uv run pytest tests/test_e2e_acceptance_policy_v2.py::test_canonical_https_origin_allows_only_optional_git_suffix -q -> expected PolicyValidationError identity drift
  - RED: uv run pytest tests/test_e2e_acceptance_manifests.py::test_traceability_uses_exact_tracked_frozen_beads_records -q -> expected old .beads/issues.jsonl path assertion failure
  - GREEN: focused two-test command -> 2 passed
  - GREEN: uv run pytest tests/test_e2e_acceptance_*.py -q -> 203 passed
  - GREEN: uv run ruff check scripts/e2e_acceptance tests/test_e2e_acceptance_*.py -> passed
  - GREEN: uv run ruff format --check scripts/e2e_acceptance tests/test_e2e_acceptance_*.py -> 17 files formatted
  - GREEN: uv run ruff check src/ tests/ -> passed
  - GREEN: uv run ruff format --check src/ tests/ -> 315 files formatted
  - GREEN: uv run mypy src/ -> 163 source files, no issues
  - RED: uv run pytest tests/test_e2e_acceptance_policy_v2.py -q -> 1 expected failure; missing fresh-checkout top-level raised raw FileNotFoundError instead of PolicyValidationError
  - GREEN: uv run pytest tests/test_e2e_acceptance_policy_v2.py -q -> 38 passed
  - GREEN: focused fresh-checkout identity matrix -> 11 passed
  - GREEN: uv run pytest tests/test_e2e_acceptance_*.py -q -> 206 passed
  - GREEN: scripts/orchestration/validate_artifact.py .codex/stages/tj-ee5f/artifacts/tj-ee5f.4.md -> artifact validation OK
  - GREEN: scripts/orchestration/run_process_verification.sh -> process verification OK
  - GREEN: uv run pytest tests/ -v --tb=short -> 2084 passed, 19 skipped
  - EXCEPTION: uv run mypy scripts/e2e_acceptance exits 2 because repository mypy config excludes scripts/; no config change was permitted in this task
changed_files:
  - .codex/stages/tj-ee5f/frozen-beads-records.jsonl
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - scripts/e2e_acceptance/manifest.py
  - scripts/e2e_acceptance/policy.py
  - tests/test_e2e_acceptance_manifests.py
  - tests/test_e2e_acceptance_policy_v2.py
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.4.md
implementation_commit: 58cdae1
correction_commit: a6f2034
explicit_defers:
  - none
---

# Summary

The CI portability defect is repaired without relaxing the trust boundary.
`TrustedAcceptanceRegistry` accepts exactly the official HTTPS origin in its
two canonical spellings. Traceability now reads a Git-tracked minimal JSONL
source of 105 exact issue IDs and canonical-record SHA-256 bindings, rather
than ignored runtime Beads export data.

# Root Cause and TDD Evidence

The base guard required the `.git` URL suffix byte-for-byte, while canonical
GitHub checkout may omit it. The manifest also depended on ignored
`.beads/issues.jsonl`, so fresh checkout compilation depended on local state.

The first corrective identity fixture was itself not checkout-realistic: it
derived `.git` from the worktree parent, whereas a normal GitHub checkout uses
`<repository>/.git`. The repaired matrix now simulates that layout, proves both
canonical HTTPS spellings, and rejects top-level and common-directory path
drift. Path-resolution failures are converted to `PolicyValidationError` so the
identity guard remains fail-closed.

RED was recorded before implementation:

- the no-suffix canonical HTTPS origin raised `PolicyValidationError`;
- the new tracked-source test found the obsolete `.beads/issues.jsonl` path.

GREEN proves the accepted no-suffix URL, rejection of HTTP, SSH, foreign
owner/repository, query, fragment, and userinfo variants, and exact frozen
source validation. The source reader rejects missing, extra, malformed,
duplicate, reordered, noncanonical, escaped, symlinked, and digest-drifted
data before it can be trusted.

# Verification

- Focused RED and GREEN tests were recorded in the frontmatter verification
  ledger; the focused GREEN command passed 2 tests.
- `uv run pytest tests/test_e2e_acceptance_policy_v2.py -q` passed 38 tests;
  the focused fresh-checkout matrix passed 11 tests.
- `uv run pytest tests/test_e2e_acceptance_*.py -q` passed 206 tests.
- Artifact and process verification passed. Ruff, formatting, `mypy src/`, and
  the full Pytest suite passed as recorded in the frontmatter verification
  ledger.

# Delivery / Cleanup

Implementation commit: `58cdae1` (`fix(acceptance): support canonical CI identity`).
Checkout-identity correction: `a6f2034`
(`fix(acceptance): harden canonical checkout identity`).
No external, paid, production, customer, or business action occurred.

# Risks / Follow-ups / Explicit Defers

Residual risk is limited to the repository-wide Mypy configuration excluding
`scripts/`; the canonical configured Mypy gate over `src/` is green. No
product-scope defer is required.
