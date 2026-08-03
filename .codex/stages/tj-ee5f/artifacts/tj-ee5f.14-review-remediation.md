---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f-r14-review-remediation
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: tj-ee5f integration owner
public_facade: scripts/model_battle.py
bounded_acceptance: deterministic isolated model-battle remediation without paid or production calls
non_goals:
  - product-runtime model configuration, paid comparison, push, deploy, or production readback
evidence:
  - none
task_id: tj-ee5f.14
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f.14-review-remediation
milestone: cohesive-vertical-slice
milestone_status: in_progress
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: money integrity, blind scoring, and cross-cutting harness review findings
repo: treejar
branch: codex/tj-ee5f-r14-review-remediation
base_branch: codex/tj-ee5f-quality-model-battle
base_commit: d58e321ab57105ded04a47deea9a9a3340dbb07b
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-r14-review-remediation
write_zone:
  - scripts/model_battle.py
  - scripts/model_battle_cases.py
  - tests/test_scripts_model_battle.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.14-review-remediation.md
success_criteria:
  - a challenger can win the core profile through objective plus sealed blind quality
  - provider-reported actual cost governs a cheapest-first one-dollar-cap budget
  - truncated and unsupported candidates are explicit and not quality-scored
  - blind review inputs contain synthetic tool evidence without identified plaintext results
  - hard fixture ids and customer flows match the reviewed acceptance classes
selected_docs:
  - docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
selected_skills:
  - superpowers:test-driven-development
  - superpowers:verification-before-completion
selected_agents:
  - tj-ee5f-r14-review-remediation
catalog_candidates:
  - none
parallel_group: tj-ee5f-review-remediation
depends_on_streams:
  - tj-ee5f.13
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: integration owner must review and integrate the returned commit
risk_level: high
verification_tier: delta
risk_tags:
  - retry
  - state-transition
  - data
affected_surfaces:
  - backend
invariants:
  - test-matrix
  - state-transition
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: this artifact records only behavior proven by focused harness tests
verification:
  - uv run pytest tests/test_scripts_model_battle.py -q: passed, 113 tests
  - uv run ruff check scripts/model_battle.py tests/test_scripts_model_battle.py: passed
  - uv run ruff format --check scripts/model_battle.py tests/test_scripts_model_battle.py: passed
  - git diff --check: passed
  - artifact validator: integration-blocked until the parent registers this returned artifact in the stage manifest outside this stream write zone
changed_files:
  - scripts/model_battle.py
  - scripts/model_battle_cases.py
  - tests/test_scripts_model_battle.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.14-review-remediation.md
explicit_defers:
  - R-17 product-runtime model-id and cache/reasoning capability cleanup is outside the harness write zone; the integration owner must bound it in Beads and handoff before stage close
---

# Summary

The core profile can now select a non-incumbent winner: critical safety facts
remain hard gates, noncritical requirements produce partial objective scores,
and the sealed blind judge score is mapped into every completed row before
ranking. Replication noise is measured within each case, while tool discipline,
latency, and actual cost remain deterministic ordering inputs.

Requests include provider usage cost. Each worst-case reservation is reconciled
to actual reported spend. The request reservation uses the UTF-8 byte length of
the complete billable payload as a conservative token upper bound. Unused
allowance carries forward only after a candidate finishes or is eliminated, so
unfinished candidates retain their reserved allowance; every model also keeps
an independent USD 1 hard cap. A length finish is `TRUNCATED`, stops that
configuration, and never becomes a quality score. Non-finite estimates,
pricing, usage, latency, and cost fail closed.

Blind review files use fresh cryptographic entropy for every item and include
rule labels, synthetic tool results, observed tool sequence, and parsed
arguments. The reveal key is mode `0600` in the sibling plaintext evidence
directory; the reviewer bundle exposes only its SHA-256 commitment. Missing
models or required capabilities produce a machine-readable `UNSUPPORTED`
artifact before the paid-call gate.

Before either hard-profile winner is selected, the scorer now requires the
complete unique staged model-by-case-by-repetition matrix. Blind judge scores
and critical failures are applied to one copied final row set before any scored
row or aggregate artifact is written, so durable evidence and ranking use the
same state.

# Scope / Routing

Only the assigned harness, synthetic fixtures, focused tests, and this artifact
changed. Exact scenario text remains in fixture code. No product prompt,
runtime configuration, Beads metadata, summary, handoff, or external system was
modified. No metadata preflight or paid model call was run.

# Verification

The initial TDD RED produced 14 expected failures across winner selection, cost usage and
reconciliation, grounding, truncation, blind mapping/evidence, capability
status, evidence separation, and scenario identity. A later focused RED proved
that truncated rows leaked into audit comparison; another proved aggregate
reporting attempted to score them; a final money-integrity RED proved missing
`usage.cost` did not fail closed. The correction RED produced 27 expected
failures covering carry isolation, full-payload reservation, staged-matrix
integrity, immutable final scoring, cryptographic blindness/private reveal, and
non-finite accounting. The implementation reached GREEN with 113 focused tests.

# Delivery / Cleanup

Return one isolated commit for orchestrator review and cherry-pick. The worker
did not push, deploy, touch runtime model configuration, read production, or
make any OpenRouter request.

# Risks / Follow-ups / Explicit Defers

The exact provider metadata preflight still requires a later network boundary;
it will now persist `SUPPORTED`/`UNSUPPORTED` states before refusing a paid run.
The product-runtime portion of `R-17` remains outside this stream: model-id
validity, reasoning capability, and cache-control policy in `src/` need a
separately owned bounded decision and Beads/handoff record from the integration
owner. Paid battle, configuration change, push, deploy, and production readback
remain prohibited without separate current authority.
