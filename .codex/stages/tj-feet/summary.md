# Stage tj-feet Summary

Updated: 2026-08-06
Status: complete; all ten planned children and all four measured follow-ups
closed, stopped before production acceptance on the new model
docs-reviewed: updated - seven stage reports under `docs/reports/2026-08-0[56]-*`
record the audit, the rubric, the superseded rounds, the sealed re-run, the
counter-set baseline, the marked-assumption result, the paraphrase decision,
the every-turn pricing and the three closed contract gaps; `.codex/handoff.md`
and this summary carry current state. No README, AGENTS.md, runbook, contract,
migration or integration doc changed, because no public facade, schema or ops
procedure changed. `AGENTS.md` was deliberately left unchanged; see the
`tj-feet.11` note below.
Branch: `codex/tj-feet`, worktree `.worktrees/tj-feet`
Base: `codex/tj-ee5f-quality-model-battle` at `ea35d44`
Head: see git log; the re-run evidence is protected and outside Git

## Boundary

A sales assistant that cannot assert a product fact it has no source for and
cannot act against an explicit customer refusal, measured on an instrument that
tells a labelled assumption from a fabrication and reports over-refusal and
persuasion as their own axes.

No runtime model configuration, public REST/webhook contract, database schema,
frozen `AC-01..AC-30` text or digest was changed. The product system prompt did
not grow: the claim contract lives in per-turn runtime directives. No push,
deploy, production mutation, Zoho/PDF/Wazzup effect or live message occurred.

## Base provenance

The specification's exact source locations and the sealed round it analyses
resolve only against `codex/tj-ee5f-quality-model-battle` at `ea35d44` **plus
that worktree's uncommitted state**. Local `main` is 90 commits behind
`origin/main`, and `origin/main` is 19 behind that branch, so neither could
carry this work.

Commit `94c29e6` imports the harness, the judge script and the stage documents
verbatim from that worktree and records what was deliberately not imported: the
tj-ee5f stream's own `.codex` state and its 2026-08-03 spec/plan edits. The
source worktree's files were left untouched. A future merge will have to
reconcile `.codex/handoff.md`, which that stream is editing in parallel.

## Delivered

| task | outcome | commit |
|---|---|---|
| `tj-feet.1` | catalog completeness audit, read-only against production | `c5a4104` |
| `tj-feet.2` | quotation tool withdrawn while consent is declined | `186ac66` |
| `tj-feet.4` | claim rubric, four types, three separate graders | `3083b74` |
| `tj-feet.7` | fixture traps repaired, superseded rounds recorded | `9746a25` |
| `tj-feet.3` | volunteered claims verified against the retrieved row | `8d0bdb7` |
| `tj-feet.5` | counter-set built and measured on the chosen model | `57e065d`, `0f4311c` |
| `tj-feet.8` | sealed re-run executed; winner named | `89ffff7` |
| `tj-feet.6` | marked-assumption move taught on the turn | `4fb74b2` |
| `tj-feet.9` | paraphrase checker measured and declined | `d311b4a` |
| `tj-feet.10` | contract on every catalog turn, shipped off | `24afdf5` |
| `tj-feet.12` | a derivation verified through its inputs | see below |
| `tj-feet.13` | an Arabic surface form is a translation, not a source | see below |
| `tj-feet.14` | an absence statement is its own claim type | see below |
| `tj-feet.11` | current-state re-pin is a step, not a surprise | see below |

## What the audit changed

`tj-feet.1` measured the live catalog and overturned a load-bearing assumption.
344 active SKUs. English is well populated — 99.7% carry a description, 76.5% at
least one feature, 59.0% at least one specification. Arabic carries nothing:
0 of 344 have `name_ar` or `description_ar`, so every Arabic reply was already
grounded in an English row.

Seating capacity is not a catalog field on any SKU. The value the model is shown
as an authoritative price basis is parsed from free text by a regular
expression, and of the 28 SKUs whose description states a capacity token, 25
state two different numbers. That is the evidence `tj-2pkk` has been blocked on
since 2026-06-16, and it is why `tj-feet.3` could not require the field as its
design assumed.

Owner decision of 2026-08-05: capacity may be stated only as a visible
assumption carrying a confirming question, never as a fact.

## Owner decisions taken during the stage

1. The read-only production catalog aggregate was authorized and run.
2. The judge is the orchestrator session, not a paid provider call. Provider
   spend is reserved for candidate models.
3. Capacity is an explicit assumption only.
4. Russian is dropped. The counter-set is English and Arabic.
5. The full counter-set run happens after the model is chosen, so `tj-feet.5`
   ships as the instrument and the scale, not the measurement.

Decision 5 reverses the specification's ordering, in which `tj-feet.5` blocked
`tj-feet.8`. The Beads dependency was updated to match.

## Acceptance evidence

Run once, at this boundary, on the combined tree:

- `uv run ruff check src/ tests/` — passed
- `uv run ruff format --check src/ tests/` — 335 files already formatted
- `uv run mypy src/` — no issues in 166 source files
- `uv run pytest tests/ -q` — **3079 passed, 19 skipped**
- `scripts/orchestration/run_process_verification.sh` — OK

The seven frontend cases fail in a fresh worktree until `npm ci` runs in
`frontend/admin`; after it they pass. That is environment, not code.

## The sealed re-run

Executed under owner authorization. Rounds `20260805/core-r5` and `bg-r5`.

Core winner **`openai/gpt-5.6-luna`**, the only candidate to finish the matrix
with no critical failure: groundedness 24/24, tool obedience 1.00,
conversational quality 0.867. Background winner `deepseek/deepseek-v4-flash`, a
practical tie with what production already runs.

The perverse incentive the specification identified did not decide the round.
The candidate with the highest conversational quality, `z-ai/glm-5.2` at 0.894 —
the model production runs in the main slot today — has the worst groundedness at
0.83 and four of the seven critical failures.

All seven critical failures were read by hand against the actual model context,
and so were all 18 winner responses. Actual spend **$0.0335** against the $4.00
reservation; the published estimate was $0.04. Detail in
`docs/reports/2026-08-05-sealed-rerun-result.md`.

## The three tasks that finished the planned ten

**`tj-feet.6` — the marked-assumption move.** A per-turn directive, read off the
customer request and never off the reply, teaches the assistant to answer a
stated headcount with an assumption it marks and confirms rather than a decline.
No factual guard was loosened; the claim contract already approved the answer.
Both rounds were re-scored together in one sitting, because the published
`tj-feet.5` persuasion figure turned out not to be comparable across judging
sessions — the responses had not changed, the judge's calibration had. Paired
result: false refusals 0.200 → 0.000, task completion 0.767 → 1.000, persuasion
2.548 → 3.071, next step 3.429 → 3.667, unsupported facts 0.000 and control
compliance 1.000 in both. On the 30 responses whose prompt did not change, drift
was −0.067 and −0.167, which is the error band the effect has to beat and does.
Detail in `docs/reports/2026-08-05-marked-assumption-result.md`.

**`tj-feet.9` — the paraphrase checker, declined.** Measured on a 24-probe EN/AR
set built for it, since the counter-set's unsupported-fact rate of 0.000 left
nothing to improve. `gpt-5.6-luna` scored TPR 1.000, TNR 1.000, false blocks
0.000; `deepseek-v4-flash` 1.000 / 0.972 with its one false block in Arabic.
2.0–2.5 s per claim, $0.000041 per claim. Not adopted: nothing measured says
widening is happening, the price is seconds on the customer's turn, and a
perfect score on probes the judge wrote and labelled cannot accept a checker. A
recorded negative result, which the acceptance criterion allows. Detail in
`docs/reports/2026-08-05-paraphrase-checker-decision.md`.

**`tj-feet.10` — the widened scope, shipped switched off.** Structural trigger,
one `system_configs` row, default unchanged. 7698 ms median added latency,
17319 ms p90, $0.000465 per turn, contract followed on 37 of 42. The blocker is
not the latency: over the 209 claims those turns emitted, 30 of 37 would be
rewritten, and the cause is three gaps in the contract — derived facts, Arabic
surface forms, absence claims — now `tj-feet.12`, `.13` and `.14`. Detail in
`docs/reports/2026-08-05-claim-contract-every-turn.md`.

## The four follow-ups, closed 2026-08-06 with no provider call

**`tj-feet.12`, `.13`, `.14` — the three gaps that made the widened scope
unsafe.** A derived fact is now verified through the inputs it names, with the
arithmetic recomputed, so listing inputs cannot decorate an unsupported figure;
an operation the runtime cannot restate stays withheld. An Arabic surface form
carries the English value it translates, and the branch opens only for a
non-Latin surface so `source_value` cannot become an escape hatch — words are
translation, a figure is a fact in any script. An absence statement is its own
claim type checked against the row's status, with no lexical detection of
absence wording, and denying an attribute the row does state is still withheld.
The owner decision on capacity survives every new route: a per-product capacity
may not be an input to a derivation from either side.

A fourth class fell out of the same replay: `field_path=sku, value=CH-A` was
withheld because the identifier is never flattened into the fields the model is
shown. The row *is* that SKU.

Replaying the 209 stored claims of `20260805/claimpass-r1` through the fixed
contract, turns that would be rewritten fall from **30 of 37 to 1 of 37**. The
before-number is exact; the after-number is an **upper bound**, because the
stored claims predate the fields the fixes need and it assumes the model fills
them correctly every time — most of all for derived facts, which were 36 of the
52 withholdings. Detail in
`docs/reports/2026-08-06-claim-contract-gaps-closed.md`.

**`tj-feet.11` — the manifest pins that kept breaking.**
`scripts/orchestration/repin_traceability_sources.py` records that current state
moved: `--check` reports drift and writes nothing, a plain run re-pins
`.codex/orchestrator.toml` and `.codex/handoff.md` and reloads the result
through the real validator. It refuses every other source, which is the property
under test — a frozen requirement drifting still fails loudly, so this is not a
way to launder a change. It was exercised for real on this stage's own handoff
update: three digests, three lines.

Listing it in the `AGENTS.md` Operational State inventory was tried and
reverted. `AGENTS.md` is pinned as `repo-contract` in the same frozen registry,
so a one-line addition to an operational list breaks three manifest tests and
would need a deliberate re-pin of another stream's acceptance provenance. That
the fix for this trap was caught by the trap is the best evidence yet for the
design question, which stays with `tj-ee5f`.

## Open

- Enabling `tj-feet.10` remains the owner's call. `.12`, `.13` and `.14` no
  longer block it; what is missing is a measurement rather than a fix.

## One live defect fixed on the way

Literal containment withheld a stored price quoted as `AED 800` against a stored
`800.00` — on 16 of the 37 measured turns — and a stock count on 10. That
comparison is shared with the shipped narrow repair path, so a customer could
have been told the catalog does not state a price it does state. A value whose
numbers are all stored numbers is now covered; a different number is still
withheld, and both directions are pinned by tests.

This is also the first non-empty denominator for counter-set metric 5, *the
guard deleted a correct claim*. It reported `n/a` on 42 responses because
nothing was ever withheld. The widened scope produced the observations.

## Spend

`$0.0663` for the whole stage: sealed re-run `$0.0335`, counter-set baseline
`$0.0039`, counter-set with the directive `$0.0052`, paraphrase checker
`$0.0081`, claim-pass pricing `$0.0195`. The judge was the orchestrator session
throughout and cost nothing.

## The counter-set, measured

42 responses on the chosen model, $0.0039. Unsupported-fact rate **0.000**
(0/42) with control compliance **1.000** (12/12), so the clean sheet is not
caution in disguise. False-refusal rate **0.200** (6/30), every one of them the
labelled-hypothesis category. Task completion 0.767, persuasion 3.262 of 5,
next step 3.833 of 5. Metric 5 reports an empty denominator, not a zero.

The finding that matters: the over-refusal is **not** caused by the guards. The
claim contract permits a marked capacity assumption with a confirming question;
the model declined on its own caution. Detail in
`docs/reports/2026-08-05-counter-set-baseline.md`.

## Runtime model

Switched to `openai/gpt-5.6-luna` on 2026-08-05 under explicit owner authority
(`tj-ee5f.15`, closed). One row in production `system_configs`; no deploy, no
restart, no `.env` change; verified against the deployed source and read back
through the deployed runtime. Revert by deleting that row. Winner-only S01-S10
production acceptance under `tj-ee5f.1` has **not** been run.

## Not comparable

Scores produced under `noor-claim-rubric/v1` are not comparable with the
superseded rounds of 2026-08-04 and 2026-08-05 and must never be shown beside
them without that statement. Different fixtures, different rubric, three axes
where there was one blended number. The superseded rounds stay immutable where
they are; `docs/reports/2026-08-05-superseded-sealed-rounds.md` records why.
