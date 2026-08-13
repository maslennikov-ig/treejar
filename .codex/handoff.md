# Orchestrator Handoff

Updated: 2026-08-13
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 and the audit fix `tj-w224` are delivered locally with all gates
green; `main` is pushed to `origin/main` with CI green. No deploy or runtime
mutation was authorized or performed. Five measured rounds were read blind
with the owner's authority: four on the frozen twenty, taking the weighted mean
14.6 to 17.5 of 30, and one over the whole Arabic population. They found and
closed `tj-fcv8`, `tj-l0e3`, `tj-fcfn`, `tj-jfmv` and `tj-40gc`, and opened
`tj-z1fn`.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`;
  the prompt and deterministic guards consume the same immutable set.
- The name ask is state-owned. `customer_name_asked` is recorded only when an
  ask reaches the customer, never reconstructed from assistant text.
  `name_chase` reads that slot itself, not the permission derived from it, and
  stays first-turn gated because lifting it changes nothing. The name gate is
  the one re-elicitation trigger: `_store_name_gate_pending_request` clears the
  slot when it parks a request behind the name. A name in the current inbound
  message joins the current-message facts used by rendering and persistence, so
  a first-turn signature cannot receive another name question in either
  language: `tj-40gc` added the Arabic introduction shapes, bounded like the
  English ones so a statement about the request is never read as a sender.
- The opening guard recognises an introduction as our persona *and* our
  company, after URLs are excluded, in either script; it removes at most one
  sentence and keeps the whole reply when removal would leave nothing. The
  company alone was shipped and reverted in `tj-w224`.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix` fall
  back to the validated grounding repair. A fallback of only Noor's opening
  plus a question creates the manager handoff; a substantive one does not.
- `run_repair_judge` notifies on failure by default; only an offline diagnostic
  passes `notify_on_failure=False`. An unavailable judge no longer costs the
  customer their reply, but a vendor going dark is worth hearing about. The
  protected journal lives in the Git common directory, never the working tree.
- `solution_consultation_directive` carries rules 9 and 10 into the
  presentation turn. One stage only, so the two never share a turn or double
  their one-question bound. Generation-side, so the replay cannot see it.
- The paid round sends the prompt production sends: `[RUNTIME DIRECTIVES]`
  from `engine._turn_runtime_directives`, `[PERMITTED ASKS THIS TURN]` from
  `permitted_asks_for_turn`, and `_inbound_customer_name` reading the opening
  with the product's own extraction. All product functions, so a round follows
  them when they change. `FROZEN_SETS` registers which sets may be measured;
  `preflight --set` names one and every later stage counts against it.
- `consultative_opening_directive` takes `opening_states_the_offer`, so on a
  first turn it says the offer is already stated. Not the self-cancelling
  condition removed on 2026-08-08: that asked the model what it had said, this
  is code stating what the reply will begin with. It also states the options a
  discovery question may offer -- kinds of work or space -- positively and with
  no prohibition, under the 2026-08-10 owner observation that this model follows
  a positive instruction and loses a ban.
- A round survives a busy provider: a 200 carrying an `error` and no choices,
  or a busy status, produced no completion and is retried with backoff. An
  empty or truncated completion is an answer and is never re-rolled, and
  neither a bad request nor one of unknown outcome is repeated.
- `collapse_question_form` runs before the first-turn opening guard, not after,
  under its unchanged `REDUCING` contract. The guard folds the canonical name
  question onto the reply and the collapse drops every question after the
  first, so the old order deleted that fold on every first turn. The
  one-question bound is unchanged and is the directive's own: a folded pair
  counts as one, and the name ask is that pair's other half.
- Catalog-supported skus are removed from a reply before the acceptance
  grounding check reads it: the asserted-number pattern reads inside an
  identifier, so `1.2T` in a quoted sku yielded a bare `2` no price supported.
  An invented identifier still carries what it asserts.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`, never
  re-baselined. Current aggregate is
  `1b425bd1f66a9189a07436f5d75b3bbcb71d68ca716e94b6f0d4c86627c97866`, and 7
  records differ across the three stored runs: dialogs 28, 875 and 1291, all
  read individually and all intended. It was 55 under
  `825f26ca85533b6d…` until the guard order was restored on 2026-08-13, and the
  7 are a strict subset of those 55 -- 48 differences removed, none introduced.
  One current reply is grounding-flagged,
  `tj-vz7o-luna-glm-20260810-rerun/789`, which is the baseline's own behaviour
  restored and is what the repair path exists for.
- `tj-l0e3`: rule 3 sat at 0.20/2 because `d11a17f` moved the collapse after
  the opening guard, then inverted the three assertions and the docstring that
  guarded the fold. Restored; full trail in Beads.
- The repair judge, measured four times on stored dialogs 819 and 789, 60 calls
  and $0.0051, every notification suppressed. `tj-3i8m` found why delivery was
  2 of 20: a flag arrived as the bare string `future_stock_check`, and once each
  flag carried `flagged_sentences` and `rules` it was 20 of 20 with no handoffs.
  Rules are written to be safe if quoted; the judge quotes them near-verbatim.
- `tj-7gpw`: every number measured before 2026-08-12, the 18.94 baseline
  included, was scored on a prompt missing the runtime directives and the ask
  permission list, so nothing after is comparable to it. The replacement
  baseline is `tj-7gpw-parity-baseline-c-20260812`, $0.0054, digest
  `61b6c9229ab295a4…`, whose reading found `tj-fcv8`: 18 of 20 replies said
  Treejar's line of business twice, three as a lower-case fragment.
- Three paired rounds followed, each on the same twenty with the same reader,
  each changing exactly one thing, each 20/20 and 20/20 with zero critical
  failures and accepted. `tj-fcv8-paired-b-20260812`, $0.0036, directive: rule 7
  +0.45, rules 2 and 4 +0.15, fragments 0 against 3, rule 5 -0.15 as the first
  sighting of `tj-fcfn`. `tj-l0e3-name-fold-b-20260813`, $0.0025, guard order,
  digest `23122559c37a9dd5…`: rule 3 0.20 to 2.00, and the cost recorded not
  rounded away, rule 5 -0.25 and rule 8 -0.33.
  `tj-fcfn-job-options-20260813`, $0.0026, directive: rule 5 recovers to 1.80
  and rules 9 (+0.33), 8 (+0.11) and 7 (+0.05) rise with it while nothing falls
  -- an option naming a kind of space *is* the job to be done, so one sentence
  charges both rules.
- Weighted mean over the four rounds 14.6, 15.0, 16.1, 17.5 of 30, the last
  interval [14.4, 20.6]; raw 10.6 to 13.2; the 11 low-ceiling openings 75% to
  97% of their 9.6 and the 9 others 78% to 92% of 30.0. A first `tj-l0e3` round,
  $0.0025, is discarded as unfaithful under `tj-l0e3.2`: it asked dialogs 28 and
  875 for names their own openings had given.
- The Arabic round, `tj-jfmv-arabic-round-20260813` over `arabic-12`: every
  Arabic opening the corpus has, 12 of 1358, a population and not a sample.
  $0.0015, 12/12, zero critical failures, accepted. Its weighted mean is *not*
  comparable to the twenty's -- 11 of 12 sit in the 9.6 band against 11 of 20 --
  so what compares is that band, n=11 both sides: English 97%, Arabic 93%. The
  hypothesis that an English directive fails to reach Arabic is disproved: five
  of twelve ask a space-based question in fluent Arabic, and rule 4 is 2.00
  against English 1.95. What Arabic costs is `tj-40gc` and `tj-z1fn`.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff and format clean over `src/ tests/ scripts/`; Mypy clean over 174 source
  files; full Pytest `3691 passed, 19 skipped`; process verification passed. The
  protected replay moved once and on purpose, toward the frozen `1fc87c04…`
  baseline: 55 differing records to 7, the 7 a strict subset of the 55, so 48
  were removed and none introduced. It has not moved since; `tj-fcfn` is
  generation-side and the aggregate stands at `1b425bd1…`.

## Constraints

- Push to `origin/main` was authorized on 2026-08-12 and performed. No PR,
  deploy, production/staging mutation, model-configuration change or real-user
  message is authorized or performed.
- Paid calls: 60 on the repair judge, all on stored dialogs 819 and 789 with the
  failure page suppressed. The owner then authorized, on 2026-08-12, a
  re-baseline round, the paired `tj-fcv8` round and the `tj-ge07` baseline as
  one block, then on 2026-08-13 the `tj-l0e3`, `tj-fcfn` and Arabic rounds.
  Spent:
  $0.0054, $0.0036, $0.0020 lost to four attempts killed by upstream 429s and a
  503, $0.0025 twice for `tj-l0e3` with the first of that pair discarded under
  `tj-l0e3.2`, $0.0026 for `tj-fcfn` and $0.0015 for the Arabic population.
  Total $0.0181. The `tj-ge07` baseline
  is authorized and deliberately not taken. The canonical runtime target
  remains `https://noor.starec.ai`; it was not contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change` — no module was
  added or moved; `graph-reviewed: no-change-needed` — Graphify is not
  initialized.

## Next recommended

Next stage id: not opened. Recommended action: `tj-z1fn`, the Arabic offer
restated. Do not deploy without new authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage only after selecting the next open Beads goal from
current repository truth.

## Explicit defers

- `tj-ge07` part two was stopped before it was built and its round not paid
  for: it cannot buy what it was opened for. Rule 14 needs
  `confirmed_next_step` -- a quote, CRM, a scheduled follow-up or the closing
  stage, every one tool-filled, and the harness forbids tools by contract. Rule
  15 needs a deferred decision: across all 913 evaluated corpus dialogs with a
  text follow-up exactly one second message defers, and on the frozen twenty
  none does. Thirty real second messages read like "Only 3" -- the detector is
  right, the conversation is not there at turn two. Nine of 913 signal a
  project, so rules 6, 10 and 13 have no representative twenty either. The
  stage is slot-driven and slots are tool-filled, so a tool-free second turn
  stays at `greeting` and `solution_consultation_directive` never fires. Its
  frozen set is now loadable: `FROZEN_SETS` would take a registered shape. It would still buy the
  selling-turn guards firing in a measured round for the first time; worth
  having, not what the task was opened for, waiting on a decision. The frozen
  set exists, `tj-ge07-two-turn-20260812`, human mean raw total 5.2, tracked
  and text-free.
- `tj-z1fn`: the Arabic reply restates the offer in 2 of 12 against 0 of 20 in
  English. Opened, not fixed. `tj-40gc` is closed and was proved free: the
  extractor fires once over the frozen twelve, on the dialog that needed it,
  and the ask is then forbidden before generation.
- Rule 5's achievable ceiling on the frozen twenty is 1.90, not 2.00: dialogs
  28 and 1000 score 1 in all four rounds, one a job application with no
  furniture need and the other a price asked with no item named, and rule 5 is
  charged on both. The measured 1.80 sits one dialog below it, and that dialog
  scores 2, 1, 2, 1 across the rounds. The rubric is not changed for it.
- `tj-2m5m.4`: the prompt half is delivered and unmeasured, waiting for
  something no round can give -- the solution stage needs slots, slots need
  tools, the harness forbids tools. Deployment and live runtime verification
  were not authorized.
