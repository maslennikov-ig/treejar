# Noor E2E Remediation and Model Comparison Plan

> Implement in stage `tj-ee5f` against current `origin/main`. Preserve all
> unrelated and untracked user files. Production and paid work require separate
> explicit authority.

**Spec:** `docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md`

**Level:** integration

## Boundary and streams

One cohesive stage owns the local remediation and sealed comparison tooling.
`tj-ee5f.5` remains a separate external Wazzup proof boundary.

| Stream | Beads | Write area | Proof |
|---|---|---|---|
| Dialogue, quote, catalog | `.7`, `.8` | `src/dialogue/*`, relevant `src/llm/engine.py`, focused tests | typed state and deterministic catalog decisions |
| Evaluator | `.12` | `src/quality/*`, evaluator tests | rule applicability and exact `/30` normalization |
| Model battle | `.13` | `scripts/model_battle*`, battle fixtures/tests | isolated profiles, sealed evidence, deterministic selection |
| Integration | `.1` | stage docs, Beads, cross-stream verification | one local release gate, later winner-only live proof |

The first two product areas share one implementation owner because their
routing and materialization paths overlap in `src/llm/engine.py`.

## Scope ledger

- Preserve the frozen `AC-01..AC-30` texts and digest.
- `.7` owns catalog/search/stock/materializer remediation.
- `.8` owns stage reconciliation, slots, and quote consent/lifecycle.
- `.12` owns evaluator applicability and score normalization.
- `.13` depends on `.7`, `.8`, and `.12`, and blocks `.1`.
- `.1` owns winner-only production acceptance.
- `.5` remains blocked on the provider fix and does not disappear from the epic.
- Create `.14` only after evidence shows that a challenger won and a runtime
  configuration change is necessary.

## Task 1: typed dialogue and quotation state

**Tests first**

- Add legacy-to-v2 and v2 round-trip tests for consent/lifecycle.
- Prove selected items without opt-in do not open detail collection.
- Prove exact SKU plus refusal causes no quote side effect.
- Prove budget cannot become address and product wording cannot change customer
  type.
- Prove quotation creation rejects non-granted consent before external IO.

**Implementation**

- Add typed enums and versioned persistence.
- Add a pure event-based state reconciler.
- Gate quote details and quote execution on explicit consent.
- Keep legacy hold reads compatible; remove new legacy hold writes.
- Reuse typed intents for refusal, objection, delivery, and correction.

**Focused verification**

Run only the affected dialogue/engine tests and `git diff --check`.

## Task 2: catalog decision and recommendation integrity

**Tests first**

- Cover the family-derived search budget.
- Cover complete and partial quantity fulfillment.
- Cover one authoritative stock snapshot per SKU per turn.
- Cover constraint-first ordering, budget, and minimal SKU count.
- Prove an unsupported model recommendation is marked as fallback/FAIL rather
  than silently replaced.

**Implementation**

- Add `CatalogDecision` and `StockSnapshot` internal types.
- Reconcile Treejar identity/price with Zoho stock.
- Derive the search budget without changing the tool signature.
- Add typed near-limit/exhausted signals.
- Validate the model answer and make safe fallback evidence explicit.

**Focused verification**

Run only affected catalog/engine tests and `git diff --check`.

## Task 3: evaluator correctness

**Tests first**

- Cover rule-level applicability from EN/AR/RU typed events.
- Cover an entirely not-applicable block.
- Verify remaining weights normalize exactly to `/30`.
- Verify low coverage stays in aggregate results and raises evaluator failure.
- Verify blind score/applicability disagreement blocks acceptance.

**Implementation**

- Replace block-wide language/keyword applicability with per-rule typed input.
- Normalize only across applicable weights.
- Publish coverage diagnostics without filtering scenarios.
- Add stable disagreement evidence.

**Focused verification**

Run only quality/evaluator tests and `git diff --check`.

## Task 4: isolated model-battle profiles

**Tests first**

- Cover the four main and five background candidate manifests.
- Verify first-party pinning, no fallback, required parameters, reasoning off,
  and omitted unsupported sampling parameters.
- Cover multi-turn fixtures, retries, all-attempt accounting, cost caps, blind
  mapping, terminal polling, elimination, ties, and separate winners.
- Prove comparison paths cannot call business adapters or mutate runtime config.

**Implementation**

- Add core-hard and background-gold profiles to the existing harness.
- Support ordered multi-turn fixtures and staged replication.
- Add free metadata/cost preflight and sealed evidence fields.
- Produce separate main/fast recommendations without applying them.

**Focused verification**

Run only model-battle tests and `git diff --check`. Do not make paid requests.

## Task 5: integrate and verify locally

1. Review each stream against its write boundary and focused evidence.
2. Integrate commits into the dedicated stage worktree.
3. Resolve shared types at the narrowest interface.
4. Update Beads, stage manifest, scope ledger, summary, and current handoff.
5. Run once:

   ```text
   uv run ruff check src/ tests/
   uv run ruff format --check src/ tests/
   uv run mypy src/
   uv run pytest tests/ -v --tb=short
   scripts/orchestration/run_process_verification.sh
   ```

6. Fix any failures with focused tests; rerun the minimal failed gate, then the
   release set once more only if its evidence is stale.

## Task 6: paid battle — authority gate

Stop and request explicit authority for the estimated paid OpenRouter calls.
After approval:

1. Run free metadata and price preflight.
2. Seal prompt copy/hash and randomized blind mapping outside Git.
3. Run round 0 for core and background candidates.
4. Eliminate hard failures; run only prescribed survivor replications.
5. Blind-audit scores and applicability.
6. Publish redacted comparison and separate main/fast winners.
7. Create `.14` only if configuration actually changes.

## Task 7: production acceptance — deploy/live authority gate

Stop and request exact authority for fresh fetch, non-force push, deploy,
production readbacks, paid live inference, test-only Zoho/PDF/Wazzup effects,
and cleanup.

After approval, deploy the reviewed SHA, verify readback, run S01-S10 once with
the winning pair plus provider canaries, and reconcile all test-only effects.
Close `.1` only on the stated score and functional gates. Keep stage/epic open
for `.5` until Wazzup supplies terminal status webhooks and a fresh retest
passes.
