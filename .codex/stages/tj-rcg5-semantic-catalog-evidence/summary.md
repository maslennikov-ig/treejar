# Stage tj-rcg5-semantic-catalog-evidence

Status: accepted and delivered to `origin/main` at `4a0883a`
Base: `codex/tj-rcg5` at `ecd9c33`
Acceptance owner: root orchestrator

Documentation: `docs-resolve` for pgvector 0.4.2 exact-search behavior and
model revision pinning; repository code owns Treejar behavior.

## Intended outcome

The measured opening harness consumes a protected, versioned artifact produced
through `src.rag.pipeline.search_products` on exact local pgvector. Missing or
stale evidence fails before paid/provider work, and retrieved rows never become
relevant merely because they exist.

## Scope and routing

One root-owned vertical slice. Producer, validator, consumer, qrels metrics and
the client claim boundary share one schema and rollback. No subagent is used:
splitting ownership of that schema would add merge risk without parallel
latency benefit.

## Verification status

- Focused unit plus real-pgvector integration: `61 passed`.
- Protected 332-row golden run: P@3 `0.7222`, R@3 `0.8333`, nDCG@3 `0.8333`,
  zero hard failures.
- Protected frozen-20 run: P@3 `0.2667`, R@3 `0.3000`, nDCG@3 `0.2960`, zero
  hard failures. Lower aggregate is expected because non-product openings are
  part of the twenty and remain qrels-negative.
- Both final artifacts pass the offline validator at retrieval contract
  `05f6c8e765c6fdc0d473968ba6e42aee26bea40e5bb3a9aa6819e896fffd97e4`.
- Repository gates passed: Ruff, format, Mypy `174` source files and full Pytest
  `3718 passed, 20 skipped`. Process verification and root slice acceptance
  passed; the latter ran the focused real-pgvector set with `61 passed`.

`docs-reviewed: updated` — the client pack now bounds historical keyword-backed
rounds, and the spec and execution plan record the durable artifact contract.

`project-index: reviewed-no-change` — no production module or stable application
entrypoint was added or moved; both new entrypoints are acceptance scripts.

`graph-reviewed: no-change-needed` — Graphify is not initialized in this repo.

## Risks / defers

No defer accepted. `query_source=frozen_opening` remains an explicit evidence
boundary, not deferred work: this harness does not reproduce an LLM-authored
tool query. Exact-SKU lookup stays owned by the existing direct `get_stock`
route.

The task-owned `treejar-tj-rcg5-pgvector` container was removed after confirming
the temporary `products` table was absent. Its database was disposable and is
not recoverable; protected final artifacts remain under Git common-dir state.
