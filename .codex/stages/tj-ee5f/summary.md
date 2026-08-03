# Stage tj-ee5f Summary

Updated: 2026-08-03
Status: local remediation accepted; paid model selection pending
Branch: `codex/tj-ee5f-quality-model-battle`
Beads owner: `tj-ee5f.1`

## Current outcome

The fresh S01-S10 production run against exact release `a2f245c` completed all
ten scenarios but failed acceptance: mean **18.4/30** versus required 24.0.
The deterministic causes behind S01, S03, S04, S05, S08, and S10 are now
remediated locally: catalog decisions are typed and stock-consistent, quote
collection requires explicit consent, and evaluator applicability comes from
typed events with exact `/30` normalization.

Technical integration paths already proven by that run remain valid: S09 Zoho
contact/order/PDF readback and cleanup passed, S10 CRM readback and cleanup
passed, Arabic catalog, exact SKU without quotation, honest no-match, and voice
transcription worked. Failed raw evidence stays protected outside Git.

The isolated model-battle harness is also ready. It seals separate main-chat
and background-model decisions, pins first-party providers, fails on missing
critical facts, reserves worst-case cost before calls, and cannot access Noor,
Zoho, Wazzup, or production storage. No paid comparison has been run yet.

## Boundary

This is one integration stage. It preserves the frozen `AC-01..AC-30` snapshot
and digest
`12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
No criterion is added, removed, or renumbered.

The local remediation and isolated comparison remain inside `tj-ee5f`.
`tj-ee5f.5` is a separate external boundary: Wazzup support confirmed that
terminal status webhooks are affected by a provider bug with no current
workaround. Existing `sent` rows are not relabelled.

## Parallel decomposition matrix

| Stream | Owner | Material benefit | Write isolation | Dependency |
|---|---|---|---|---|
| `.7` + `.8` catalog/dialogue | `engine-remediation` | shared routing context and one owner for `engine.py` | dialogue, catalog/quote engine regions, focused tests | none |
| `.12` evaluator | `evaluator-remediation` | independent scoring domain | `src/quality/*`, evaluator tests | consumes compatible typed state |
| `.13` model battle | `model-battle-remediation` | independent harness and evidence boundary | `scripts/model_battle*`, battle tests | runs only after `.7/.8/.12` |
| integration | root orchestrator | cross-stream review and one release proof | docs, Beads, stage state | all local streams |

The evaluator uses a backward-compatible typed-state adapter while the dialogue
stream is parallel. Model battle never calls business adapters or production.

## Scope ledger

- `.7`: catalog decision, search budget, stock snapshots, planner, materializer.
- `.8`: sales-stage reconciliation, slots, quote consent and lifecycle.
- `.12`: rule applicability, coverage diagnostics, exact `/30` arithmetic.
- `.13`: isolated main/background model profiles and sealed report.
- `.13` depends on `.7/.8/.12` and blocks `.1`.
- `.1`: winner-only production acceptance after separate authority.
- `.5`: future bounded Wazzup terminal-status retest.
- `.14` is created only if a challenger wins and runtime configuration changes.

## Verification contract

Each implementation stream records focused RED/GREEN evidence only. The one
release gate was executed. Its first full pytest pass exposed 79 integration
regressions (`2665 passed`, `19 skipped`); after the bounded correction, only
the failed surfaces were repeated and are green:

```text
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
```

- Ruff check and format check: passed.
- Mypy: passed for all `src/`.
- Previously failing dialogue/quotation set: 68 passed.
- Exact affected dialogue subset in its isolated stream: 856 passed.
- Replay fixtures: 11 passed; frontend regressions: 11 passed; acceptance
  manifests: 44 passed.
- Process verification and all three new artifact validators: passed.

The full suite is not repeated a second time because the verification contract
requires minimal reruns after a bounded defect, not another broad pass.

Paid comparison, runtime configuration mutation, push, deploy, production
readbacks, Zoho/PDF/Wazzup effects, and live messages require fresh exact
authority. The stage cannot close while `.5` lacks terminal provider proof.

## Next stage

Remain in `tj-ee5f`. Request paid-model-battle authority and run the sealed
isolated comparison. Production acceptance follows only after a winner decision
and separate push/deploy/live authority.

## Explicit defers

- `tj-ee5f.5`: wait for Wazzup's provider fix, then prove one protected
  `sent -> delivered -> read` transition.
- Production and paid comparison are not part of the current local authority.
- Existing raw production/model evidence remains outside Git.
