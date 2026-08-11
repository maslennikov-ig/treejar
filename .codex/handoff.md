# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Current stage id: `tj-n7p4-judged-repairs`
Status: both requested stages are accepted and their epics are closed. Stage 2
used one repair-judge call for $0.001265216 and none in its measured round.

Documentation: no external/versioned boundary — this stage changes first-party
Python prompt and policy text and uses an existing provider client.

## Current truth

- Every customer-facing reply goes through `src.llm.response_policy.render_reply`.
  Provenance is metadata and cannot select a shorter policy chain.
- The six text guards now declare their effect. Closed-question, premature
  quote details, first-turn opening, and deferred commitment are replacing;
  selling-turn and grounding-output are removing and expose flags. `.3`
  removed the legacy application bridge: only a flagged turn reaches the
  second vendor, and an unflagged turn makes no repair call.
- Every text guard is bounded: letters or digits in, letters or digits out. It
  catches F5. The second vendor now supplies the semantic half by approving or
  rewriting the complete reply, while deterministic reclassification remains
  the formal lower bound. One protected correction was read and accepted, so
  `tj-rt7w.14` closes with the recorded evidence.
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
- In `.3`, the owner authorized two stale assertion updates: they now require
  original visible text plus a non-visible repair candidate instead of silent
  deterministic deletion. A local repair-judge stand-in keeps ordinary tests
  isolated from the network.
- Judge unavailability, `cannot_fix`, or a rejected correction now persists a
  counted manager handoff before replacing the unsafe draft with a localized
  customer notice. An active handoff is reused; no old deletion path returns.
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
- `7248844` — `tj-n7p4.1`, split grounding classification from repair.
- `d81a744` — `tj-n7p4.2`, declare replacing and removing guard contracts.
- `f12cc5c` — `tj-n7p4.3`, add the second-vendor repair judge.
- `a1d9532` — `tj-n7p4.6`, hand unresolved repairs to a manager.
- `0764ce2` — `tj-n7p4.4`, align the harness with production repair.
- `5c7a099` — `tj-n7p4.5`, measure the judged-repair architecture.

Each closed child has a validated artifact under `.codex/stages/*/artifacts/`.

## Verification

- `.5` gates: Ruff and format clean over `src/ tests/`; Mypy clean over 173
  source files; Pytest `3561 passed, 19 skipped`; process verification passed.
- `.3` gates: Ruff and format clean over `src/ tests/`; Mypy clean over 174
  source files; Pytest `3585 passed, 19 skipped`; process verification passed.
- `.3` protected replay: 60/60 source digests matched; exactly one reply was
  flagged, corrected, changed and root-read. The single GLM call cost
  $0.001265216; no corpus text entered Git.
- `.6` gates: 17 repair tests and 849 affected response tests passed; full
  Pytest `3590 passed, 19 skipped`; no paid call; process verification passed.
- `.4` gates: production parity and two 20-case journal simulations passed;
  full Pytest `3594 passed, 19 skipped`; no paid call; process passed.
- `.4` protected replay: all 60 stored raw assistant outputs re-render through
  the full policy chain with zero changes, digest `1b0b2963…`.
- `.5` measured round: 20/20 generation, root reading and language; 20 Luna,
  zero repair and scoring calls; zero flags, fallbacks and rewrites; $0.005444.
- `.5` paired result: criticals 1 to 1; weighted delta +1.16 (95% CI -0.28 to
  +3.00); raw delta +0.50 (95% CI +0.05 to +1.10). The one candidate critical
  is the known SKU-detector false positive on dialog 1067.
- `test_llm_grounding_output.py` stayed byte-identical and passed all 107 tests.
- Stage closeout passed 107 affected-package, 29 security, and 145 integration
  tests, then readiness and process verification.
- Stage-2 closeout also passed 13 database/migration tests plus documentation,
  project-index, blocking-review, cleanup, and debt checks. `tj-n7p4` and the
  fully delivered `tj-rt7w` parent epic are closed.

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

Next stage id: not opened; first candidate `tj-2m5m`.
Recommended action: start a new task from current Beads truth for `tj-2m5m`,
then `tj-swgu`, `tj-vz7o.12`, `tj-wvo4`, and `tj-odeq`.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-2m5m` after inspecting current Beads truth.

## Explicit defers

- `tj-2p4c`: supported SKU digits can falsely trip numeric grounding.
- `tj-9dp2`: root-only public summaries carry a stale GLM judge label.
- Deterministic-route retirement: explicitly outside this stream.
- Deployment and any live proof: not authorized or performed here.
