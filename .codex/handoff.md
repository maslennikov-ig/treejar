# Orchestrator Handoff

Updated: 2026-08-11
Current branch: `main`
Current stage id: `tj-0s42-repair-retry`
Status: the build scores 15.3/30 weighted on the frozen twenty. The repair
path now retries once and records what actually failed.

Documentation: no external/versioned boundary — this stage changes first-party
Python prompt and policy text and uses an existing provider client.

## Current truth

- Every customer-facing reply goes through `src.llm.response_policy.render_reply`.
  Provenance is metadata and cannot select a shorter policy chain.
- The six text guards now declare their effect. Closed-question, premature
  quote details, first-turn opening, and the additive company question are
  replacing; the question fold and the name-chase refusal are reducing and
  prove they took only the reply's own asks; grounding-output is removing and
  exposes a flag. `.3` removed the legacy application bridge: only a flagged
  turn reaches the second vendor, and an unflagged turn makes no repair call.
- Every text guard is bounded: letters or digits in, letters or digits out. It
  catches F5. The second vendor now supplies the semantic half by approving or
  rewriting the complete reply, while deterministic reclassification remains
  the formal lower bound. One protected correction was read and accepted, so
  `tj-rt7w.14` closes with the recorded evidence.
- Every text guard is a pure module function with explicit state, not a closure.
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
- `tj-t6ug` — declare the three selling-turn guards apart, and add the third
  guard mode with an executable reduction proof.

Each closed child has a validated artifact under `.codex/stages/*/artifacts/`.

## Verification

- Current gates at `tj-0s42`: Ruff and format clean over `src/ tests/ scripts/`;
  Mypy clean over 174 source files; Pytest `3619 passed, 19 skipped`; process
  verification and stage closeout passed.
- Protected replay, run from `scripts/corpus_bridge/replay_policy_chain.py`:
  all 60 stored raw outputs re-render unchanged, digest `1fc87c04…`. The one
  `grounding_output` flag on dialog 789 is `tj-n7p4.3`'s recorded change.
- `test_llm_grounding_output.py` has stayed byte-identical through every stage
  since `tj-mshi.4` and passes all 107 tests.
- Stage closeouts across `tj-mshi`, `tj-n7p4`, `tj-t6ug`, `tj-vhto` and
  `tj-0s42` passed the affected-package, security, integration and
  database/migration groups, plus documentation, project-index,
  blocking-review, cleanup and debt checks.
- Paid calls to date: `tj-mshi.5` $0.005458, `tj-n7p4` $0.006709, `tj-vhto`
  $0.005386. `tj-t6ug` and `tj-0s42` made none.

## The measured round, `tj-vhto`

Run at `3682203` on the frozen seed-`20260810` twenty: **20 Luna calls, one
repair-judge call, zero scoring calls, $0.005386**. Report:
`docs/reports/2026-08-11-where-the-bot-stands-on-the-shipped-build.md`.

- Weighted **15.3/30** (12.6-17.9); raw **12.8/30** (12.0-13.5); 20/20 coverage,
  language and blind criterion reads.
- By attainable ceiling: greeting-only openings 9.5 of 9.6 (99%); openings with
  a real request 22.4 of 30 (75%). The missing quarter is one behaviour - the
  bot asks quantity, not what the customer is trying to do.
- Paired raw delta -0.60, interval excluding zero, on a change that cannot
  affect a first turn. That is the instrument's floor, measured, and it retires
  the earlier round's +0.50 raw as a result.
- Five openings carry all the movement: 819 at -22.5 is a failed repair call,
  28 at -12.2 is reader drift, 366 at +5.6 is generation variance. `tj-0s42`
  fixed the first: one bounded counted retry, the failure class recorded
  instead of blamed on the provider, reasoning off for that path and its
  budget at 1200 tokens. The cause remains unproved until it fires again.
- Criticals 1 to 1 against both baselines, the one being `tj-2p4c`. Rules 14
  and 15 applicable on 0/20 again; `tj-ge07`.

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

Both were delivered. Specs, plan and the ratified list live under
`docs/superpowers/specs/2026-08-11-*` and `docs/plans/2026-08-11-*`; the
combined orchestrator prompt at `docs/plans/2026-08-11-orchestrator-prompt.md`
is spent and kept only as the record of what was asked for.

**Paid calls.** The advance authorisation for `tj-mshi` and `tj-n7p4` is spent
and those stages are closed; `tj-vhto` was authorised separately in session.
Any further round needs fresh authority. The **scoring** judge is the
orchestrator reading blind and costs nothing -- `--second-reader` is never
passed. The **repair** judge is a different thing, paid, and fires on a flag.

## Next recommended

Next stage id: not opened; first candidate `tj-2m5m`. `tj-t6ug`, `tj-vhto` and
`tj-0s42` are accepted.
Recommended action: start a new task from current Beads truth for `tj-2m5m`,
then `tj-swgu`, `tj-vz7o.12`, `tj-wvo4`, and `tj-odeq`.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-2m5m` after inspecting current Beads truth.

## Explicit defers

- `tj-2p4c`: supported SKU digits can falsely trip numeric grounding.
- `tj-9dp2`: root-only public summaries carry a stale GLM judge label.
- `tj-4q79`: the root judge drifts between sittings by more than the paired
  deltas being reported; this bounds every single-round claim.
- `tj-ge07`: no frozen set has a second turn, so the selling-turn guards and
  rules 14/15 are unobservable.
- Deterministic-route retirement: explicitly outside this stream.
- Deployment and any live proof: not authorized or performed here.
