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
- `.14` is the model-battle harness repair task added by the review round.
  Create a new task for a runtime configuration change only after evidence
  shows that a challenger actually won.

## Review remediation round (added 2026-08-03)

The independent Opus 5 review of `f831e6c..3701c1e` is incorporated. Its
findings `R-01`..`R-20` are in the spec under "Review outcome". Tasks 1-4 below
stay as written; this round is the delta needed before Task 5 can be claimed.

| Stream | Beads | Findings |
|---|---|---|
| Dialogue and quote state | `.8` | `R-01`, `R-02`, `R-05` |
| Catalog and materializer | `.7` | `R-03`, `R-04`, `R-08`, `R-16` |
| Evaluator and reporting | `.12` | `R-06`, `R-07` |
| Model battle harness repair | `.14` | `R-09`..`R-15`, `R-17`, `R-19`, `R-20` |
| Stage documents | epic | `R-18` |

Harness repair is `tj-ee5f.14`, a direct child of the epic rather than of
`.13`. Blocking propagates from parent to child, and `.13` is correctly blocked
by `.7/.8/.12` because it owns the paid run; repairing harness code is not the
paid run and must stay workable in parallel. `.13` now depends on `.14`, so the
comparison still waits for both. The issues kept their original `tj-ee5f.13.x`
ids after reparenting.

Order matters in two places. `R-01` decides whether the `.8` fixes are live at
all, so resolve it first and record the answer. `R-12` unblocks the budget
mechanics, so it precedes `R-20`.

Owner resolution (2026-08-03): the code default becomes
`dialogue_kernel_mode=enforce`; the enforced-flow allowlist remains empty so
typed state is live without replacing model-owned replies. No stored runtime
configuration is changed by this local remediation.

Only `S05` of the six deterministic failures is currently closed. Do not claim
a failure remediated without a focused test that reproduces the original
customer-visible symptom and then shows it gone.

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
- Cover cheapest-first ordering, release of unused request reservation to the
  next candidate, unchanged per-model caps, and `TRUNCATED` handling.
- Prove comparison paths cannot call business adapters or mutate runtime config.

**Implementation**

- Add core-hard and background-gold profiles to the existing harness.
- Support ordered multi-turn fixtures and staged replication.
- Add free metadata/cost preflight and sealed evidence fields.
- Keep `max_tokens=2200`. Reserve the next call conservatively, then reconcile
  to provider-reported actual cost; unused batch allowance carries forward but
  cannot raise any model above its own USD 1 cap.
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
3. Run round 0 for core and background candidates in ascending exact-provider
   estimated cost.
4. Eliminate hard failures; run only prescribed survivor replications.
5. Blind-audit scores and applicability.
6. Publish redacted comparison and separate main/fast winners.
7. Create `.14` only if configuration actually changes.

The complete production S01-S10 suite is not part of the candidate battle. It
runs only for the winning main/background pair in Task 7.

The budget mechanics are owner-confirmed and recorded in the spec under
"Budget decisions for the paid battle". In short: `max_tokens=2200` stays;
candidates run cheapest first; the USD 1 per-model cap is never raised; a
conservative reservation is replaced by provider-reported actual cost after
each response and the freed difference returns to the shared allowance;
carry-forward can never lift a candidate above its own cap; a response cut off
by `max_tokens` is `TRUNCATED`, a harness budget event rather than a model
quality failure. `R-12` must land before any of this can be measured, because
`usage.cost` is not currently requested from the provider.

## Task 7: production acceptance — deploy/live authority gate

Stop and request exact authority for fresh fetch, non-force push, deploy,
production readbacks, paid live inference, test-only Zoho/PDF/Wazzup effects,
and cleanup.

After approval, deploy the reviewed SHA, verify readback, run S01-S10 once with
the winning pair plus provider canaries, and reconcile all test-only effects.
Close `.1` only on the stated score and functional gates. Keep stage/epic open
for `.5` until Wazzup supplies terminal status webhooks and a fresh retest
passes.
