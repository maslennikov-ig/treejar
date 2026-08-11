# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Accepted stage id: `tj-mshi-permission-list`
Status: `tj-mshi.1` through `.5`, `tj-mshi`, and `tj-riim` are closed. Stage
readiness, slice closeout, and safe workspace cleanup passed. Stage 2 remains
unopened until this closeout is committed locally.

Documentation: no external/versioned boundary — this stage changes first-party
Python prompt and policy text and uses an existing provider client.

## Current truth

- Every customer-facing reply goes through `src.llm.response_policy.render_reply`.
  Provenance is metadata and cannot select a shorter policy chain.
- Every text guard is bounded: letters or digits in, letters or digits out. It
  catches F5. It does not stop a guard shrinking four sentences to one word --
  `tj-rt7w.14`, recorded rather than promised.
- The opening, selling-turn, closed-question, and premature quote-detail guards
  are pure module functions with explicit state, not engine closures.
- `src/llm/money.py` owns every currency pattern in `src/llm/`, enforced by an
  AST test.
- The unsupported customer-owned-furniture service family remains blocked by
  the unchanged grounding backstop. Its superseded prompt prohibition is gone.
- **F1 and F3 are closed.** One turn is `_Turn` (the shared state and the
  operations over it), `_TurnConfig` (the config reads, taken once) and
  `_QuoteFacts` (the quote facts, read once then amended by the name gate),
  with eleven phase functions over them. Longest function 259 lines;
  `process_message_impl` 163; no closure anywhere in the file. Two tests hold
  that: `test_llm_message_processor_structure.py` for the bound,
  `test_llm_message_processor_patch_points.py` for the patch points.
- `process_message` is still the 40-line public facade and `engine.py` is
  11,849 lines. Both were already true; what is new is that the sequence behind
  the facade is now what the facade claimed.
- The impl is fully type-checked. It imports `src.llm.engine` as a module, so
  the suite's `src.llm.engine.*` patches still land and Mypy still checks.
  `get_system_config` is imported *inside* the two calls that use it for the
  same reason, and a test now derives that rule from the suite.
- Catalog planning/materialization is in `src/llm/catalog_planning.py`; response
  transport is in `src/llm/response_runtime.py`; the turn sequence is in
  `src/llm/message_processor.py`; order/quote routes are in
  `src/llm/order_quote_routes.py`.
- No existing test was edited anywhere in this epic.
- The canonical runtime target remains `https://noor.starec.ai`; nothing has
  been pushed, deployed, or applied to production or staging.
- Production data is Postgres in `noor-db-1` on `noor-server`, not Supabase.
- Luna is the product's generation model; GLM is the alternate-vendor model for
  a second opinion or alternate text. **The judge of a measured round is the
  orchestrating agent itself, reading blind**, and a paid model may only be a
  second reader beside it. That is now the harness default rather than a
  directive: `real_opening_acceptance.py` stops after the generation arm and
  writes `reading-pack.json`, and paying a second reader takes
  `preflight --second-reader`.
- The protected corpus remains outside Git under the git-common-dir
  orchestration state. Tracked evidence may carry `dialog_id` and integers only.
- Both scoring rulers and applicability/rubric logic remain frozen. Never treat
  movement smaller than the measurement uncertainty as evidence.

## Delivered commits

- `d64cec5` — `tj-mshi.2`, fill the ratified 25-entry registry.
- `1b3f34c` — `tj-mshi.3`, turn every entry into a positive permission.
- `6649d2c` — `tj-mshi.4`, remove registry-subsumed prohibitions.
- `5c26f57` — `tj-mshi.5`, run and report the blind paired measurement.

Each closed child has a validated artifact under `.codex/stages/*/artifacts/`.

## Verification

- `.5` gates: Ruff and format clean over `src/ tests/`; Mypy clean over 173
  source files; Pytest `3561 passed, 19 skipped`; process verification passed.
- `.4` protected replay: all 60 stored raw assistant outputs re-render through
  the full policy chain with zero changes, digest `1b0b2963…`.
- `test_llm_grounding_output.py` stayed byte-identical and passed all 107 tests.
- Stage closeout passed 107 affected-package, 29 security, and 145 integration
  tests, then readiness and process verification.

## The measured round, `tj-mshi.5`

Run at `6649d2c` on the frozen seed-`20260810` twenty: **20 Luna calls,
zero judging calls, $0.005458**. Report:
`docs/reports/2026-08-11-permission-list-measured-round.md`.

- 20/20 responses, 20/20 root evaluations, 20/20 language; the root read all
  20 replies and 300 criteria blind with zero red flags.
- Criticals did not rise: baseline 1, candidate 1. Dialog 28 no longer promises
  recruitment routing or callback; dialog 789 remains fixed.
- The candidate harness code on dialog 1067 is a numeric-detector false
  positive on a catalog-supported SKU. It remains in the frozen result and is
  tracked as `tj-2p4c`.
- Paired weighted delta +0.32, 95% CI -0.86 to +1.82; raw delta +0.25,
  95% CI -0.10 to +0.70. Both are inconclusive.
- Rules 14 and 15 stayed 0 to 0 and were applicable on 0/20 openings. This
  frozen first-turn set cannot decide whether the list is too tight.
- The public summary's stale GLM judge label is tracked as `tj-9dp2`; protected
  run-state proves `root-orchestrator` and zero judging calls.

## Constraints

- No push, PR, deploy, production/staging mutation, model-configuration change,
  or real-user message occurred or is implied by these local commits.
- Do not retire deterministic routes in this stream; that separate 8,259-line
  scope remains intentionally deferred.
- Preserve unrelated owner work and keep corpus text outside the repository.
- After every handoff edit, run
  `python3 scripts/orchestration/repin_traceability_sources.py`.

## Documentation and graph review

- `docs-reviewed: updated` — report, handoff, stage summary and artifact state
  the paired result, protected evidence boundary, and instrument limitations.
- `project-index: reviewed-no-change` — no module added, moved or renamed.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Two owner decisions of 2026-08-11, and what they queued

**Say what Noor may promise, not what he may not.** Prohibitions hold badly on
Luna, and the list of things Treejar does not do has no end. Epic `tj-mshi` is
ratified; `.1`–`.4` are accepted and `.5` is measured. `COMMERCIAL_CAPABILITIES`
holds all 25 ratified entries in five modes, phrased as permissions with their
conditions.

**No automatic deletions.** Where a check finds doubt, a judge reads it and
either approves the text or writes the correction. Epic `tj-n7p4`. Audited on
the 60 stored replies: a guard removes a sentence from **28 of 60**, all of them
duplicate identity lines the anchor replaces, so that one is *replacing* and
stays deterministic; `grounding_output` removes and replaces nothing, once in
sixty, and that is where the judge belongs.

Documents, ready to hand over:

- **One prompt for both stages, run in sequence:**
  `docs/plans/2026-08-11-orchestrator-prompt.md`. Passes
  `orch-prompts prompt-check`.
- Specs: `docs/superpowers/specs/2026-08-11-what-noor-may-promise-spec.md` and
  `docs/superpowers/specs/2026-08-11-nothing-is-deleted-without-a-judge-spec.md`.
- `docs/plans/2026-08-11-permission-list-plan.md`, and the ratified list at
  `docs/plans/2026-08-11-promise-types-for-ratification.md`.

**Paid calls are authorised in advance**, owner, 2026-08-11: 20 Luna generation
calls per measured round; up to 25 second-vendor repair-judge calls across
`tj-n7p4`; ceiling $2.00 for both stages, against about $0.05 expected. The
**scoring** judge is the orchestrator reading blind and costs nothing --
`--second-reader` is never passed. The **repair** judge in `tj-n7p4` is a
different thing, paid, and fires only on a flag.

## Next recommended

Next stage id: `tj-n7p4-judged-repairs`; stage 1 is accepted and stage 2 stays
unopened until the closeout commit is recorded.

Recommended action: commit the accepted stage 1 closeout, then open
`tj-n7p4-judged-repairs` and begin `tj-n7p4.1`.

After stage 2, the product track that has waited behind the cleanup: two P0 epics
(`tj-2m5m`, `tj-swgu`), then the reader findings this round confirmed still live
— `tj-vz7o.12`, `tj-wvo4`, `tj-odeq`. `tj-riim` closes in `tj-mshi.5`, and
`tj-rt7w.14` inside `tj-n7p4.3`.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-mshi-permission-list` and epic `tj-mshi`.
Hand `docs/plans/2026-08-11-orchestrator-prompt.md` verbatim. It covers both
stages and gates the second on the first being accepted; the repo contract's
single-active-stage rule and the fact that both touch the same reply path are
why they are sequential rather than parallel. The first measured round is
complete and comparable with 2026-08-11 because the judge is the same.

## Explicit defers

- `tj-rt7w.14`: the R2 bound has no semantic half; a fix owes a measured round.
- `tj-2p4c`: supported SKU digits can falsely trip numeric grounding.
- `tj-9dp2`: root-only public summaries carry a stale GLM judge label.
- `tj-n7p4`: the judged-repair architecture, specified and queued behind
  `tj-mshi`.
- Deterministic-route retirement: explicitly outside this stream.
- Deployment and any live proof: not authorized or performed here.
