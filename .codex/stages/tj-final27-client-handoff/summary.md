# Stage `tj-final27-client-handoff`

Status: delivered; formal acceptance blocked by P1 `tj-08ve` and P0
`tj-final27.19`. P2 `tj-final27.20` is tracked separately.

## Outcome

- The pinned opening is `Chairs from AED 139, desks and workstations from AED
  58.` It is executable for one buyer because every winning row has a non-zero
  price and at least one unit. Rows below five units carry an explicit limited
  stock and volume-price qualification.
- R04/R02 return verified catalog SKU/price options with at most one question,
  rather than a model-written form.
- The owner-approved referral exclusion is verbatim in handoff and client pack;
  `tj-final27.6` is closed.
- The client pack states 8/15 opening rules, names the seven unreachable rules,
  and limits deal-outcome evidence to 192/1400 dialogues.
- The bounded anchor task `tj-final27.18` and pack/E2E task `tj-final27.9` are
  closed; their parent stage remains blocked by the separately tracked P0/P1.

## Measurement

Protected path:
`.git/codex-orchestration/corpus-bridge/tj-final27.18-round-20260814b`.
Preflight was 19 priced / 1 withheld. Root read 20/20 blind, without a second
reader. Raw paired delta against `tj-399z` was 0.00 per opening and weighted
delta +0.10, both inside the 2.0 reader gap. Fourteen of twenty reached their
own ceiling. Paid cost was $0.006703: 20 Luna generation calls and one triggered
repair call.

The price anchor contradicted no cited row and all required low-stock warnings
were present. The round is not accepted because dialog 293 changed substantive
reply language, one critical failure now tracked as P1 `tj-08ve`.

## Verification

- focused anchor/guard/harness: 119 passed
- repeated R04/R02 state and answer checks: passed
- ruff check and format: passed
- mypy: passed
- full pytest: 3822 passed, 20 skipped, 0 failed
- protected replay: current `1b425bd1…` versus frozen `1fc87c04…`, the same
  seven differences only on dialogs 28, 875 and 1291
- process verification: passed
- root stage closeout: 71 passed, 1 skipped; process verification passed
- production: GitHub Actions run `31798763684` deployed `68800f29…`; health
  returned that exact SHA and public API smoke passed 8/8
- controlled E2E: anchor and literal R04 readback passed; zero pending synthetic
  conversations and zero pending escalation rows

The +19 full-test delta from 3803/20/0 is fully named: 16 direct regressions for
anchor, rounded grounding evidence, scarcity, R04/R02, cost cap and
failed-language reporting, plus three registry parameterizations created by the
new deterministic route. Skips are unchanged.

## Documentation and graph review

- `docs-reviewed: updated` — handoff, client pack, root-reading convention and
  this artifact record current behavior and measured evidence.
- `project-index: reviewed-no-change` — no stable entrypoint or module ownership
  boundary changed; `.codex/orchestrator.toml` only points at this stage.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Explicit defers

`tj-08ve` needs a deterministic customer-language guard and a fresh paired
round. The 20 generation calls authorized for this stage are exhausted, so that
measurement needs new owner authority. P0 `tj-final27.19` needs Telegram URL
redaction and credential rotation under fresh authority. P2 `tj-final27.20`
tracks one bare greeting with two question marks; R04/R02 passed their
one-question criterion. The delivery is complete, but the P0 and P1 prevent
marking the stage accepted.
