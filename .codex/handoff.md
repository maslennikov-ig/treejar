# Orchestrator Handoff

Updated: 2026-08-13
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 and the audit fix `tj-w224` are delivered locally with all gates
green; `main` is pushed to `origin/main` with CI green. No deploy or runtime
mutation was authorized or performed. Four measured rounds were read blind with
the owner's authority. They found `tj-fcv8`, `tj-l0e3` and `tj-fcfn`, each
fixed and re-measured, and `tj-jfmv`, opened. Weighted mean 14.6 to 17.5 of 30.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`;
  the prompt and deterministic guards consume the same immutable set.
- The name ask is state-owned. `customer_name_asked` is recorded only when an
  ask reaches the customer, never reconstructed from assistant text.
  `name_chase` reads that slot itself, not the permission derived from it, and
  remains first-turn gated because lifting it changes nothing. The name gate is
  the one re-elicitation trigger: `_store_name_gate_pending_request` clears the
  slot when it parks a request behind the name, so the guard cannot remove the
  gate's own question. A name in the current inbound message joins the
  current-message facts used by rendering and persistence, so a first-turn
  signature cannot receive another name question.
- The opening guard recognises an introduction as our persona *and* our company,
  after URLs are excluded, in Latin or Arabic script. It removes at most one
  sentence and keeps the whole model reply when removal would leave nothing
  meaningful. The company alone was shipped and reverted in `tj-w224`: it
  deleted answering sentences and stripped the opening off quotation replies.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix` fall
  back to the validated deterministic grounding repair. A fallback of only
  Noor's opening plus a question creates the manager handoff; a substantive one
  is sent without.
- `run_repair_judge` notifies on failure by default; only an offline diagnostic
  passes `notify_on_failure=False`. An unavailable judge no longer costs the
  customer their reply, but a paid vendor going dark is still worth hearing
  about. The protected journal lives in the Git common directory and never
  stores dialog text in the working tree.
- `solution_consultation_directive` carries rules 9 and 10 into the
  presentation turn, which the opening directive never reached. One stage only,
  so the two never share a turn or double their one-question bound. It is
  generation-side, so the protected replay cannot see it and does not.
- The paid acceptance round sends the prompt production sends.
  `build_generation_messages` appends `[RUNTIME DIRECTIVES]` from
  `engine._turn_runtime_directives` and `[PERMITTED ASKS THIS TURN]` from
  `permitted_asks_for_turn`, and `_inbound_customer_name` reads a name out of
  the opening itself with the product's own extraction, so a customer who
  signs is not asked. All product functions: a round follows them when they
  change.
- `consultative_opening_directive` takes `opening_states_the_offer`. The caller
  knows whether the deterministic opening will be prepended, so on a first turn
  the directive says the offer is already stated and must not be
  repeated. This is not the self-cancelling condition removed on
  2026-08-08: that one asked the model what it had already said, this one is
  code stating what the reply will begin with.
- A round survives a busy provider. A 200 carrying an `error` object and no
  choices, or a refusal with a busy status, produced no completion, so both are
  retried with backoff and every provider error is recorded; an empty or
  truncated completion is an answer and is never re-rolled, and neither a bad
  request nor one of unknown outcome is repeated.
- `collapse_question_form` runs before the first-turn opening guard, not after,
  under its unchanged `REDUCING` contract still proving `only_asks_were_dropped`.
  The opening guard folds the canonical name question onto the reply; the
  collapse keeps the first question of a line and drops every later one, so the
  old order deleted that fold on every first turn. The one-question bound is the
  directive's own and unchanged: at most one question counting a folded pair as
  one, the name ask being that pair's other half. Only first turns move.
- Catalog-supported skus are removed from a reply before the acceptance
  grounding check reads it: the asserted-number pattern reads inside an
  identifier, so `1.2T` in a quoted sku yielded a bare `2` no price supported.
  An invented identifier still carries what it asserts. The public summary names
  the judge that read the round, taken from the results.

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
- `tj-l0e3`, the largest reachable defect either 2026-08-12 round found: rule 3
  at 0.20/2, because 19 openings of 20 never asked how to address the customer
  while the ask was permitted every time. The cause was not a missing
  instruction. `d11a17f`, subject state-owned reply content, moved the collapse
  after the opening guard, inverted three assertions from `"how should I address
  you" in response.text` to `not in`, renamed the test that guarded the fold,
  and rewrote its docstring to call the fold a surplus -- where the original
  said the cap must not throw it away. Restored; full trail in Beads.
- The repair judge, measured four times on stored dialogs 819 and 789, 60 calls
  and $0.0051, every notification suppressed. `tj-3i8m` found why delivery was
  2 of 20 -- a flag arrived as the bare string `future_stock_check` -- and once
  each flag carried `flagged_sentences` and `rules`, delivery was 20 of 20 with
  zero handoffs. Rules are written to be safe if quoted: the judge quotes them
  almost verbatim, and a reverted refinement once produced "assembly is not a
  service we offer", false and caught by no guard.
- `tj-7gpw`: every number this project had measured, the 18.94 baseline
  included, was scored on a prompt missing the runtime directives and the ask
  permission list, which production always sends. Nothing after that fix is
  comparable to 18.94.
- The baseline round of 2026-08-12, `tj-7gpw-parity-baseline-c-20260812`:
  twenty Luna generations plus one repair-judge call, $0.0054, read blind,
  digest `61b6c9229ab295a4…`. That reading found `tj-fcv8`: 18 of 20 replies
  said Treejar's line of business twice, three as a lower-case fragment copied
  out of the directive's own example clause.
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
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff and format clean over `src/ tests/ scripts/`; Mypy clean over 174 source
  files; full Pytest `3686 passed, 19 skipped`; process verification passed. The
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
  one block, then on 2026-08-13 the `tj-l0e3` and `tj-fcfn` rounds. Spent:
  $0.0054, $0.0036, $0.0020 lost to four attempts killed by upstream 429s and a
  503, $0.0025 twice for `tj-l0e3` with the first of that pair discarded under
  `tj-l0e3.2`, and $0.0026 for `tj-fcfn`. Total $0.0166. The `tj-ge07` baseline
  is authorized and deliberately not taken. The canonical runtime target
  remains `https://noor.starec.ai`; it was not contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change` — no module was
  added or moved; `graph-reviewed: no-change-needed` — Graphify is not
  initialized.

## Next recommended

Next stage id: not opened. Recommended action: `tj-jfmv`, the three replies
that still menu, one of them in Arabic. Do not deploy without new authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage only after selecting the next open Beads goal from
current repository truth.

## Explicit defers

- `tj-ge07` part two was stopped before it was built, and the baseline round it
  would have fed was not paid for. It cannot buy what it was opened for. Rule 14
  needs `confirmed_next_step` -- a quote, CRM, a scheduled follow-up or the
  closing stage, every one tool-filled, and the harness forbids tools by
  contract. Rule 15 needs a deferred decision: across all 913 evaluated corpus
  dialogs with a text follow-up exactly one second message defers, and on the
  frozen twenty none does. Thirty real second messages read like "Only 3" and
  "Can you share the details" -- the detector is right, the conversation is not
  there at turn two. Nine of 913 signal a project, so rules 6, 10 and 13 have no
  representative twenty either. The stage is slot-driven and slots are
  tool-filled, so a tool-free second turn stays at `greeting` and
  `solution_consultation_directive` never fires. It would still buy the
  selling-turn guards firing in a measured round for the first time; worth
  having, not what the task was opened for, waiting on a decision. The frozen
  set exists, `tj-ge07-two-turn-20260812`, human mean raw total 5.2, tracked
  and text-free.
- `tj-jfmv`: after `tj-fcfn`, rule 5 is 1.80 against the 1.85 it held before
  the fall, and three replies of twenty still offer a product menu -- dialogs
  1217, 1000 and 1291. The Arabic one is the interesting case: the directive is
  English and the model carries it across languages with the reply, so an
  instruction that lands in English may not land in Arabic. Opened, not fixed.
- `tj-2m5m.4`: the prompt half is delivered and unmeasured, waiting for
  something no round can give -- the solution stage needs slots, slots need
  tools, the harness forbids tools. Deployment and live runtime verification
  were not authorized.
