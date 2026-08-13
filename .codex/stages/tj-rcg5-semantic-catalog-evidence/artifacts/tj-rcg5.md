---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-rcg5-semantic-catalog-evidence/stage-manifest.json
stream_owner: tj-rcg5-root-implementation
orchestration_level: integration
scope_kind: product_slice
immediate_consumer: measured-opening-preflight
public_facade: semantic-catalog-evidence-cli
bounded_acceptance: exact-offline-retrieval-artifact-and-fail-closed-consumer
non_goals:
  - production-retrieval-change
  - paid-generation-round
  - reply-must-quote-retrieved-rows
evidence:
  - protected-retrieval-artifact-and-report-digests
task_id: tj-rcg5
epic_id: tj-rcg5
stage_id: tj-rcg5-semantic-catalog-evidence
session_id: tj-rcg5-semantic-catalog-evidence
milestone: production-path-semantic-evidence-boundary
milestone_status: accepted
agent_type: n/a
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: root-owned shared artifact schema and acceptance boundary
repo: treejar
branch: codex/tj-rcg5
base_branch: main
base_commit: ecd9c33
worktree: /home/me/code/treejar
write_zone:
  - scripts/corpus_bridge
  - tests
  - docs/client
  - docs/superpowers
  - .codex
success_criteria:
  - semantic-artifact-fails-closed-before-provider-work
  - production-search-function-runs-on-exact-pgvector
  - qrels-not-row-presence-own-relevance
  - historical-keyword-rounds-have-bounded-claims
selected_docs:
  - docs/superpowers/specs/2026-08-13-semantic-catalog-evidence-boundary-spec.md
  - docs/superpowers/plans/2026-08-13-semantic-catalog-evidence-boundary.md
selected_skills:
  - orchestrator-stage
  - superpowers-test-driven-development
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: sequential
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: cleaned
cleanup_notes: exact task-owned pgvector container removed; no delegated worktree exists
risk_level: high
verification_tier: integration
risk_tags:
  - privacy
  - data
affected_surfaces:
  - backend
  - data
invariants:
  - fail-closed-before-paid-provider-work
  - exact-retrieval-only
  - protected-bodies-never-tracked
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: client claim boundary, normative spec, plan and handoff updated
verification:
  - focused-real-pgvector-61-passed
  - protected-golden-zero-hard-failures
  - protected-frozen-20-offline-validation-passed
  - full-repository-3718-passed-20-skipped
  - process-verification-and-root-closeout-passed
changed_files:
  - .codex/goals/tj-rcg5/scope-criterion-snapshot.json
  - .codex/handoff.md
  - .codex/orchestrator.toml
  - .codex/stages/tj-ee5f/traceability-manifest.json
  - .codex/stages/tj-rcg5-semantic-catalog-evidence/artifacts/tj-rcg5.md
  - .codex/stages/tj-rcg5-semantic-catalog-evidence/stage-manifest.json
  - .codex/stages/tj-rcg5-semantic-catalog-evidence/summary.md
  - docs/client/noor-opening-acceptance-2026-08-13.md
  - docs/superpowers/plans/2026-08-13-semantic-catalog-evidence-boundary.md
  - docs/superpowers/specs/2026-08-13-semantic-catalog-evidence-boundary-spec.md
  - scripts/corpus_bridge/real_opening_acceptance.py
  - scripts/corpus_bridge/semantic_catalog_evidence.py
  - tests/test_corpus_bridge_real_opening_acceptance.py
  - tests/test_corpus_bridge_semantic_catalog_evidence.py
explicit_defers:
  - none
---

# Summary

Measured opening preflight now consumes one protected semantic retrieval
artifact produced by the production search function on exact local pgvector.
The validator binds catalog, query set, qrels, pinned embedding revision,
retrieval code and both pgvector versions before any provider lookup. Raw top-3
and qrels relevance remain separate; only confirmed SKUs reach generation.

# Scope / Routing

Root-owned because producer and consumer share one artifact schema, one
privacy boundary and one rollback.

# Verification

- Focused real-pgvector slice: `61 passed`.
- Golden artifact `444b9ffaa64673264045676377bb85622124abe9e63592455091b9bb4fed20f2`;
  report `3229b80da15f35a8cd8a3cfaaef5b57513a3fd404d76ce41ce6a3ce4a021d23a`.
- Frozen-20 artifact `3b105d92fa79e53b6a968d5f301db170c3e62ee723d319c19da6d5eebf7e019e`;
  report `d9168348969229ce8283e3bd5ec8476ecf113605707fe66864676c8076d1e90c`.
- Catalog `979e791b1d5c52e53976ec455fb301aab59e1e4848601d1a7939d4efe18df2d7`;
  BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`; exact pgvector
  Python `0.4.2`, extension `0.8.5`; protected files mode `0600`.
- Normal: 436 returns three office tables and 442 returns workstations.
  Failure: stale/missing/code/model/query/qrels/pgvector/ANN evidence fails
  before provider lookup. Edge: a qrels-negative no-match still has nearest
  rows in the artifact but none reaches generation; typo and Arabic are scored.
- Ruff, format, Mypy `174` files and full Pytest `3718 passed, 20 skipped`.
  Process verification passed. Root slice acceptance passed the focused
  real-pgvector command with `61 passed`.

# Delivery / Cleanup

Accepted by the root orchestrator. One root-owned commit and authorized push to
`origin/main` remain.

# Risks / Follow-ups / Explicit Defers

No defer accepted. Remaining evidence limitation: `query_source=frozen_opening`
does not reproduce the LLM's live tool-query wording. Exact SKU remains owned by
the existing direct `get_stock` route and is intentionally outside this semantic
qrels set.
