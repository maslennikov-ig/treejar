# Stage `tj-dak8-loosen-opening`

Status: accepted and delivered.
Base: `main` at `db55e1f`.
Acceptance owner: root orchestrator, reading blind.

Documentation: no external/versioned boundary — repository code, the frozen
twenty and the protected replay define this stage.

## Why this stage exists

Owner decision of 2026-08-14: the bot works badly under hard rules, and the
direction is to loosen them rather than add more. The two hardest were named by
the owner from a written list of what is currently fixed.

## What changed

- `src/llm/opening_guard.py`. The canonical identity and capability sentence is
  prepended only when the model did not introduce us itself. When it did, its
  words stand: nothing is stripped and nothing is added in front. The name ask
  now attaches to the model's own words rather than to whichever part comes
  last, and folds into a question already standing there.
- `src/dialogue/claim_contract.py` and `src/llm/engine.py`. The directive can no
  longer promise a prepended sentence, so it asks for the introduction in the
  model's own words. One prohibition was dropped in favour of the positive form
  standing beside it, under the owner's 2026-08-10 observation that this model
  follows a positive instruction and loses a ban.
- The catalog anchor carries its low-stock qualification as one paragraph
  instead of two.

The fallback is what earns the loosening. Rule 7 measured zero in 26 transcripts
of 26 while it was a request with nothing behind it, so the sentence still
arrives whenever the model does not write one.

Revert is one line: `opening_states_the_offer=False` in `_turn_runtime_directives`.

## Measurement

Protected path:
`.git/codex-orchestration/corpus-bridge/tj-loosen1-round-20260814e`.

- Preflight: 19 priced / 1 withheld, exact AED 139 / 58 anchor.
- Paid execution: 20 Luna generation calls, no repair or scoring calls,
  `$0.004955`. An earlier attempt was aborted by a coverage check this stage
  then fixed, at roughly `$0.003`; both are inside the `$0.05` cap.
- Root read 20/20 blind and free. No second reader.
- Acceptance: 20/20 replies in the selected turn language, zero critical
  failures, exactly one question marker in every reply.
- Raw mean 12.8, weighted mean 15.4. Paired against
  `tj-08ve-round-20260814c`: raw delta +0.10, inside the 2.0 reader gap, so no
  total-score claim is made.
- Rule score / paired delta: r1 2.00/0.00; r2 1.90/+0.05; r3 2.00/0.00;
  r4 2.00/0.00; r5 1.85/+0.10; r7 1.85/-0.15; r8 (n=6) 2.00/+0.33;
  r9 (n=6) 2.00/0.00.

Named defect movement:

- Gone: two discovery subjects stacked into one question on 442 and 819, which
  returns rule 8 to its ceiling on all six dialogues that charge it; role
  discovery continuing after a recruitment redirect on 28; the silently dropped
  assembly and delivery needs on 819, now named as unconfirmed.
- New: on 293, 1022 and 875 the model states the offer and then repeats it as a
  capability list, which is the predicted cost of removing the ban. On 1067 a
  raw internal SKU string reaches the customer.
- Unchanged: a row outside the customer's family on 436; catalog-category
  discovery on 420 and 1000.

The reading convention was extended for the cases this round introduced:
authorship of the opening does not change how rules 1 and 7 are read, a single
introduction that names a few product families is one statement, and printing an
internal SKU is the machinery-leak shape.

## Verification and delivery

- Ruff check and format: passed.
- Mypy: passed over 177 source files.
- Full pytest: 3846 passed, 20 skipped, 0 failed. The +4 over the deployed
  3842/20/0 is this stage's focused cases.
- Process verification and stage closeout: passed.
- GitHub Actions run `31822779522`: passed and deployed
  `c87ea878abffc8015d347bbca75e70917ea93727`.
- Production `/api/v1/health`: OK with that exact SHA, redis and database ok.
- Protected replay: the loosening changes how every first turn renders, so the
  frozen `1fc87c04…` pin went to 55 differences of 60. Under explicit owner
  authorization of 2026-08-14 the raw convention was re-pinned to
  `caaa8e44…` in `tj-wvuk-replay-baseline-20260814.json`; the replay is clean
  against it. The 2026-08-11 `tj-t6ug` baseline is left untouched as history.

## Documentation and graph review

- `docs-reviewed: updated` — handoff, reading convention and this summary.
- `project-index: reviewed-no-change` — no entrypoint or ownership boundary moved.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Explicit defers

- `tj-wvuk` (P3): the anchor now lands after the discovery question. The reply
  is one WhatsApp message, so the question is still visible above it; every
  alternative ordering costs something else. Recorded, not fixed.
- `tj-c58g` covers the internal SKU reaching the customer on 1067.
- Rule 7's `-0.15` is deliberately not chased. It is fifteen words of ordinary
  sales copy and chasing it would restore the ban this stage removed.
- `tj-jlx4` remains excluded by the owner.
