# Stage tj-ee5f Summary

Updated: 2026-08-03
Status: local review remediation accepted; paid battle and live proof pending
Branch: `codex/tj-ee5f-quality-model-battle`
Beads owner: `tj-ee5f.1`

## Current outcome

The last production S01-S10 run remains failed evidence on exact release
`a2f245c`: mean **18.4/30**, below the required 24.0. No new production run,
model comparison, configuration change, deploy, or live readback occurred in
this local round.

The reviewed deterministic defects now have focused local proofs and an
independent bounded correction re-review with verdict APPROVE:

- `.7` (`R-03`, `R-04`, `R-08`, `R-16`): verified facts constrain a
  model-owned repair pass instead of replacing the answer; a SKU exposes one
  authoritative Zoho stock number per turn or `unconfirmed`; prompt search
  limits no longer contradict runtime; partial plans retain solved families and
  publish a numeric coverage gap plus one closing question.
- `.8` (`R-01`, `R-02`, `R-05`): the code default is
  `dialogue_kernel_mode=enforce` with an empty enforced-flow allowlist; typed
  state is reconciled on the default path while replies remain model-owned;
  refusal persists `declined`, never renders as “on hold”, and quote-only
  details require canonical `granted` consent.
- `.12` (`R-06`, `R-07`): collapsed coverage is blocking and cannot become an
  excellent `/30` score; owner reports publish coverage diagnostics, normalized
  denominators, and `н/д` for inapplicable blocks.
- `.14` (`R-09` through `R-15`, `R-19`, `R-20`, harness portion of `R-17`):
  a challenger can produce `winner` only from a complete unique matrix; sealed
  judge scores and critical gates are applied before durable writes; provider
  cost reconciles a conservative full-payload reservation; carry cannot consume
  an unfinished survivor's allowance; non-finite values fail closed;
  `TRUNCATED` and `UNSUPPORTED` are machine-readable. Reviewer-visible evidence
  exposes only a commitment to a cryptographically random private reveal.

The legacy combined `.7/.8` artifact was corrected: verified catalog facts now
drive a model-owned repair pass, while deterministic recovery replacement alone
uses the explicit functional-failure marker.

## Boundary

The frozen `AC-01..AC-30` snapshot and digest remain unchanged:
`12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
No public REST/webhook contract or database schema changed. Exact scenario text
remains in fixture code or protected evidence, not product code. The product
system prompt shrank.

The code default does not overwrite an existing stored
`dialogue_kernel_mode`. No runtime setting was mutated. The paid battle and a
winner-only production pass remain later authority boundaries.

## Verification

Focused RED/GREEN evidence is stored in the four review-remediation artifacts:

- `.7`: original 759 tests; integrated correction set 823; targeted
  Ruff/format/Mypy passed.
- `.8`: 803 tests; targeted Ruff/format/Mypy passed.
- `.12`: 99 tests; `git diff --check` passed.
- `.14`: 113 tests; scoped Ruff/format and diff check passed.
- Independent bounded correction re-review: 34 passed, 841 deselected; APPROVE.

Combined-tree gate on 2026-08-03:

- `uv run ruff check src/ tests/`: passed.
- `uv run mypy src/`: passed, 165 source files after correction integration.
- `scripts/orchestration/run_process_verification.sh`: passed after the final
  documentation refresh.
- Full Pytest: `2776 passed, 19 skipped, 3 failed`; all three failures were the
  expected `runtime-truth` digest drift caused by the handoff update. After the
  final digest refresh, the exact three failed manifest tests passed.
- Ruff format initially found one worker formatting drift in
  `src/quality/schemas.py`; after the mechanical correction the full check
  reports 327 files already formatted.

The stage is not production-accepted by local tests. S01-S10 remains failed
until a separately authorized winner-only release-bound pass proves otherwise.

## Parallel decomposition

| Stream | Owner | Artifact | Result |
|---|---|---|---|
| `.7` catalog | `tj_ee5f_r07` | `tj-ee5f.7-review-remediation.md` | accepted locally |
| `.8` dialogue | `dialogue-review-remediation` | `tj-ee5f.8-review-remediation.md` | accepted locally |
| `.12` evaluator | `tj-ee5f-r12-review-remediation` | `tj-ee5f.12-review-remediation.md` | accepted locally |
| `.14` harness | `tj-ee5f-r14-review-remediation` | `tj-ee5f.14-review-remediation.md` | accepted locally |

`.13` owns the future paid isolated comparison and still depends on `.7`, `.8`,
`.12`, and `.14`. `.1` owns winner-only production acceptance. `.5` remains the
provider-blocked Wazzup terminal-status proof.

## Next boundary

After the local digest and process closeout, stop. A later task must
obtain exact current authority before any paid OpenRouter call, model
configuration change, push, deploy, production readback, Zoho/PDF/Wazzup
effect, or live message.

## Explicit defers

- `tj-ee5f.13.9` / product-runtime part of `R-17`: model-id, reasoning
  capability, and cache-control cleanup in `src/core/config.py` and
  `src/llm/safety.py`; harness capability/unsupported evidence is implemented.
- `tj-ee5f.5`: wait for Wazzup's provider fix, then prove one protected
  `sent -> delivered -> read` transition.
- Paid comparison, runtime configuration mutation, delivery, deploy, and
  production acceptance are outside this local authority.
- Protected raw production/model evidence remains outside Git.
