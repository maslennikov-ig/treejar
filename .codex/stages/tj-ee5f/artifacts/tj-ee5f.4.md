---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f.4-ci-identity-fix
orchestration_level: slice_acceptance
scope_kind: foundation
immediate_consumer: canonical GitHub Actions acceptance compilation
public_facade: TrustedAcceptanceRegistry canonical identity and traceability source validation
bounded_acceptance: canonical HTTPS origin in a fresh checkout accepts only the optional .git suffix, enforces repository path identity, requires full Git history for provenance in CI, and frozen traceability data is tracked, exact, and fail-closed
non_goals:
  - production deploy or readback
  - provider customer Wazzup Zoho CRM quotation order or paid action
  - changing immutable scope authorization evidence or production safety contracts
task_id: tj-ee5f.4
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f
milestone: CI portability repair for trusted acceptance identity
milestone_status: accepted
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
  - .github/workflows/ci.yml
  - scripts/e2e_acceptance/policy.py
  - scripts/e2e_acceptance/manifest.py
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-ee5f/frozen-beads-records.jsonl
  - tests/test_e2e_acceptance_policy_v2.py
  - tests/test_e2e_acceptance_manifests.py
  - tests/test_ci_workflow_contract.py
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.4.md
success_criteria:
  - a simulated fresh checkout accepts the official HTTPS origin with or without .git, and rejects URL variants plus top-level or common-dir identity drift
  - the standard-checkout fixture returns literal .git while repo_root/.git exists, so the relative common-directory branch is exercised
  - a missing top-level path remains distinguishable from existing top-level identity drift
  - the CI test job has exactly one Run tests step with the full configured Pytest token sequence and fetches full Git history for scope-provenance validation
  - tracked frozen Beads source contains exactly 105 referenced IDs and canonical record digests
  - source validation fails closed on missing extra malformed reordered noncanonical escaped symlinked or digest-drifted data
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - https://github.com/actions/checkout
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
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: accepted content is integrated; legacy worktree remains because destructive cleanup was not requested
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
docs_review_notes: official actions/checkout README confirms the default single-commit checkout and fetch-depth 0 full-history behavior; no durable user documentation changed
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
  - RED: uv run pytest tests/test_e2e_acceptance_policy_v2.py::test_canonical_https_origin_rejects_fresh_checkout_path_identity_drift tests/test_e2e_acceptance_policy_v2.py::test_canonical_https_origin_rejects_missing_fresh_checkout_top_level -q -> 1 failed, 2 passed; non-existent other-checkout returned identity is unavailable rather than identity drift
  - GREEN: focused checkout identity branches -> 5 passed
  - GREEN: uv run pytest tests/test_e2e_acceptance_policy_v2.py -q -> 39 passed
  - GREEN: uv run pytest tests/test_e2e_acceptance_*.py -q -> 207 passed
  - GREEN: uv run ruff check tests/test_e2e_acceptance_policy_v2.py -> passed
  - GREEN: uv run ruff format --check tests/test_e2e_acceptance_policy_v2.py -> 1 file already formatted
  - CI RED: GitHub Actions run 30335662631 on main@65ca9bce8f0fe51e1ef855a4137331379ce6f119 -> test job 108 failed, 1977 passed, 19 skipped; first/root exception scope provenance creation commit is invalid; lint and type-check passed, deploy skipped
  - RED: focused CI workflow contract -> 1 failed; test job checkout fetch-depth was absent
  - GREEN: focused CI workflow contract -> 1 passed
  - GREEN: uv run pytest tests/test_ci_workflow_contract.py -q -> 2 passed
  - GREEN: uv run pytest tests/test_e2e_acceptance_*.py -q -> 207 passed
  - GREEN: uv run ruff check src/ tests/ -> passed
  - GREEN: uv run ruff format --check src/ tests/ -> 315 files already formatted
  - GREEN: uv run mypy src/ -> 163 source files, no issues
  - GREEN: uv run pytest tests/ -v --tb=short -> 2086 passed, 19 skipped
  - RED: mutation of Run tests to uv run pytest tests/test_ci_workflow_contract.py -q -> 1 failed, DID NOT RAISE; prior substring contract accepted narrowed Pytest
  - GREEN: uv run pytest tests/test_ci_workflow_contract.py -q -> 3 passed
  - GREEN: uv run pytest tests/test_e2e_acceptance_*.py -q -> 207 passed
  - GREEN: uv run ruff check src/ tests/ -> passed
  - GREEN: uv run ruff format --check src/ tests/ -> 315 files already formatted
  - GREEN: uv run mypy src/ -> 163 source files, no issues
  - GREEN: uv run pytest tests/ -v --tb=short -> 2087 passed, 19 skipped
  - GREEN: GitHub Actions run 30336804422 on main@4457b541322f4b726ec5b69336296550392f5a25 -> test, lint, and type-check passed; deploy correctly skipped for the CI-only change
  - EXCEPTION: uv run mypy scripts/e2e_acceptance exits 2 because repository mypy config excludes scripts/; no config change was permitted in this task
changed_files:
  - .github/workflows/ci.yml
  - .codex/stages/tj-ee5f/frozen-beads-records.jsonl
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - scripts/e2e_acceptance/manifest.py
  - scripts/e2e_acceptance/policy.py
  - tests/test_e2e_acceptance_manifests.py
  - tests/test_e2e_acceptance_policy_v2.py
  - tests/test_ci_workflow_contract.py
  - .codex/stages/tj-ee5f/stage-manifest.json
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.4.md
implementation_commit: 58cdae1
correction_commit: a6f2034
tdd_correction_commit: 482b017
ci_history_correction_commit: 0e390a8
ci_command_contract_correction_commit: f683b55
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

The subsequent review found that the standard fixture still returned an
absolute common-directory path, leaving the relative `.git` resolution branch
unproved; it also used a non-existent top-level drift path, which only proved
the unavailable-path guard. The third correction keeps `repo_root/.git`
physical but returns literal `.git`, creates `other-checkout` before asserting
`identity drift`, and separately proves a missing top-level returns
`identity is unavailable`. This is test-only: the production guard required no
further change.

Canonical CI run `30335662631` on
`main@65ca9bce8f0fe51e1ef855a4137331379ce6f119` exposed a separate environment
defect: `jobs.test` used the checkout action's default shallow history, while
scope provenance intentionally reads the anchor creation commit and
first-addition history. The run produced 108 failures (1977 passed, 19
skipped); its first/root exception was `scope provenance creation commit is
invalid`. The official actions/checkout README records the default
single-commit checkout and `fetch-depth: 0` full-history behavior. The fix is
limited to the checkout in `jobs.test`, and its semantic contract proves that
this exact job runs full Pytest with `fetch-depth: 0`; provenance validation and
runtime network behavior are unchanged.

Final review found the first semantic workflow test used a substring for the
Pytest command, so a narrowed `tests/test_ci_workflow_contract.py -q` command
would still pass the contract. A mutation RED proved that gap. The contract now
locates exactly one `Run tests` step in `jobs.test` and compares
`shlex.split()` output with the six required full-suite tokens; it continues to
bind `fetch-depth: 0` to the single checkout in that same job. This correction
changes tests only and leaves the workflow YAML untouched.

Canonical GitHub Actions run `30336804422` then passed on
`main@4457b541322f4b726ec5b69336296550392f5a25`: the full test, lint, and
type-check jobs were green, and the deploy job was correctly skipped because
the delivered change affected only CI, tests, and orchestration evidence.

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
- The third correction's focused checkout-identity branches passed 5 tests;
  its policy and acceptance suites passed 39 and 207 tests respectively.
- The CI-history correction's focused contract passed, as did its acceptance
  surface (207), full configured gates, and full Pytest (2086 passed, 19
  skipped).
- The final command-contract mutation was RED before tightening and green
  afterward; its contract suite passed 3 tests, acceptance passed 207, and the
  full suite passed 2087 tests with 19 skips.
- Canonical GitHub Actions run `30336804422` passed against the exact delivered
  `main` commit; this is the terminal fresh-checkout proof for `tj-ee5f.4`.
- Artifact and process verification passed. Ruff, formatting, `mypy src/`, and
  the full Pytest suite passed as recorded in the frontmatter verification
  ledger.

# Delivery / Cleanup

Implementation commit: `58cdae1` (`fix(acceptance): support canonical CI identity`).
Checkout-identity correction: `a6f2034`
(`fix(acceptance): harden canonical checkout identity`).
TDD-evidence correction: `482b017`
(`test(acceptance): prove checkout identity branches`).
CI-history correction: `0e390a8`
(`fix(ci): fetch provenance history for test job`).
CI-command contract correction: `f683b55`
(`test(ci): require exact full test command`).
No external, paid, production, customer, or business action occurred.

# Risks / Follow-ups / Explicit Defers

Residual risk is limited to the repository-wide Mypy configuration excluding
`scripts/`; the canonical configured Mypy gate over `src/` is green. No
product-scope defer is required.
