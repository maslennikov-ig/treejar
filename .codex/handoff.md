# Orchestrator Handoff

Updated: 2026-08-03
Current branch: `codex/tj-ee5f-quality-model-battle`
Active stage: `tj-ee5f`
Status: local remediation accepted; paid isolated model selection pending

## Current truth

- Canonical runtime is `https://noor.starec.ai`; exact last tested release is
  `a2f245cde301457ef19abda221732368986d7f9d`.
- The fresh S01-S10 run completed 29 turns using 100,008 conversation tokens,
  USD 0.083774 conversation cost, and 34 tool calls.
- Mean quality was **18.4/30**. Functional failures remain in S01, S03, S04,
  S05, S08, and S10. Required acceptance is every scenario at least 20/30,
  mean at least 24/30, and no functional failure or unresolved P0/P1.
- S09 Zoho/order/PDF and S10 CRM readbacks and safe cleanup passed. Raw
  evidence and identifiers are protected outside Git.
- Frozen scope remains `AC-01..AC-30`, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- Local fixes now cover typed catalog decisions, authoritative per-turn stock,
  explicit quote consent/lifecycle, and typed evaluator applicability. The
  isolated main/background model-battle harness is ready; no paid run occurred.

## Active work

- `tj-ee5f.7` (`in_progress`): coherent catalog plans, authoritative per-turn
  stock, search budget, coverage, and recommendation validation.
- `tj-ee5f.8` (`in_progress`): typed quote consent/lifecycle, reconciled state,
  no premature detail collection, and safe slot conflicts.
- `tj-ee5f.12` (`in_progress`): language-independent rule applicability and normalized
  `/30` scoring.
- `tj-ee5f.13` (`in_progress`): isolated core/background model-battle profiles;
  it depends on `.7/.8/.12` and blocks `.1`.
- `tj-ee5f.1` (`in_progress`): later winner-only production acceptance.
- `tj-ee5f.5` (`blocked`): provider-confirmed Wazzup terminal-status bug.

The accepted design and executable plan are:

- `docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md`
- `docs/superpowers/plans/2026-08-03-noor-e2e-remediation-and-model-comparison.md`

## Constraints

- Exact scenario wording remains only in fixtures/evidence.
- Do not grow the product system prompt.
- Public REST/webhook contracts and DB schema remain unchanged.
- Model battle cannot call Treejar, Zoho, Wazzup, or production storage and
  cannot mutate runtime model settings.
- Preserve unrelated and untracked user files.

## Verification

The one broad release attempt recorded `2665 passed`, `19 skipped`, and 79
integration failures. After bounded correction, all failed surfaces are green:
68 dialogue/quotation tests, 11 replay tests, 11 frontend tests, and 44 manifest
tests. The isolated dialogue stream additionally passed 856 tests. Ruff,
format, Mypy, process verification, and all new artifact validators pass.

## Approval gates

Reversible local code, tests, docs, Beads, and free metadata inspection are
authorized. Stop before paid model calls, runtime configuration changes,
non-force push, deploy, production readback, test-only Zoho/PDF/Wazzup effects,
or live messages and request exact authority.

## Next recommended

Next stage id: `tj-ee5f`

Recommended action: request authority for the bounded paid OpenRouter model
battle. After a sealed winner decision, request separate delivery, deploy, and
live-acceptance authority. Do not create another umbrella task.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` integration stage. Read the
current specification, plan, handoff, stage manifest, scope ledger, and Beads
`.1`, `.5`, `.7`, `.8`, `.12`, `.13`. Preserve AC-01..AC-30 and stop before
paid, push, deploy, or live actions until the owner grants exact authority.

## Explicit defers

- `tj-ee5f.5`: after Wazzup announces its fix, run one bounded protected status
  transition retest; do not rerun the commercial suite for that proof.
- Existing nonterminal outbound audits remain `sent`.
- Repository-history privacy cleanup remains a separate destructive decision.
