# Orchestrator Handoff

Updated: 2026-08-12
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 are delivered locally with all requested gates green, and the
post-acceptance audit fix `tj-w224` is delivered on top of them. `main` is
pushed to `origin/main` with CI green. `tj-9e15` and `tj-3h0w` are closed. No
deploy or runtime mutation was authorized or performed. A measured round was
taken on 2026-08-12 with the owner's authority, read blind by the root judge,
and it found a customer-visible defect that no earlier round could have seen.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by
  `permitted_asks_for_turn`; the prompt and deterministic guards consume the
  same immutable set.
- The name ask is state-owned. `customer_name_asked` is recorded only when an
  ask actually reaches the customer, and never reconstructed from previous
  assistant text. `name_chase` reads that slot itself, not the permission
  derived from it. The name gate is the one re-elicitation trigger:
  `_store_name_gate_pending_request` clears the slot when it parks a customer
  request behind the name, so the guard cannot remove the gate's own question.
- A name present in the current inbound message participates in the same
  current-message facts used by rendering and later persistence. A first-turn
  signature therefore cannot receive another name question.
- The opening guard recognises an introduction as our persona *and* our company,
  after URLs are excluded, in Latin or Arabic script. It removes at most one
  sentence and preserves the whole model reply when removal would leave no
  meaningful text. Recognising the company alone was shipped and reverted in
  `tj-w224`: it deleted answering sentences and stripped the canonical opening
  off quotation replies.
- `question_form` runs on first turns under its unchanged `REDUCING` contract
  and still proves `only_asks_were_dropped`. `name_chase` remains first-turn
  gated because the recorded evidence shows that lifting it changes nothing.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix`
  outcomes fall back to the validated deterministic grounding repair.
- A fallback containing only Noor's own opening plus a question creates the
  manager handoff. A substantive fallback is sent without a handoff.
- `run_repair_judge` notifies on failure by default; only the diagnostic replay
  passes `notify_on_failure=False`. Production keeps the page: an unavailable
  judge no longer costs the customer their reply, but a paid vendor going dark
  is still worth hearing about. The protected journal is in the Git common
  directory and never stores dialog text in the working tree.
- Guard modes in `src/llm/response_policy.py` did not change.
- `solution_consultation_directive` carries rules 9 and 10 into the
  presentation turn, which the opening directive never reached. One stage only,
  so the two never share a turn or double their one-question bound, and the
  same transactional-narrowing stand-down applies. It is generation-side, so
  the protected replay cannot see it and does not.
- The paid acceptance round now sends the prompt production sends.
  `build_generation_messages` appends `[RUNTIME DIRECTIVES]`, taken from the
  product's own `engine._turn_runtime_directives` over the opening at the
  greeting stage, and `[PERMITTED ASKS THIS TURN]`, taken from
  `permitted_asks_for_turn` with the frozen set's own properties. Both come
  from the product functions rather than restated text, so a round follows them
  when they change.
- `consultative_opening_directive` takes `opening_states_the_offer`. The caller
  knows whether the deterministic opening will be prepended to this reply, so
  on a first turn the directive says the offer is already stated and must not
  be repeated. This is not the self-cancelling condition removed on
  2026-08-08: that one asked the model what it had already said, this one is
  code stating what the reply will begin with.
- A round survives an upstream rate limit. A 200 carrying an `error` object and
  no choices produced no completion, so it is retried with backoff and each
  provider error is recorded; an empty or truncated completion is an answer and
  is never re-rolled, and a request whose outcome is unknown is never repeated.
- Catalog-supported skus are removed from a reply before the acceptance
  grounding check reads it. The asserted-number pattern reads inside an
  identifier, so `1.2T` in a quoted sku yielded a bare `2` that no price
  supported. An invented identifier still carries whatever it asserts.
- The public acceptance summary names the judge that read the round, taken from
  the results rather than asserted.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`.
  It was not re-baselined.
- Current policy replay aggregate is
  `825f26ca85533b6d6499b4606a2e0fcb87df1ee10ce7fba2dbd434381b965900`:
  55 intended records differ across the three stored runs. One current reply is
  grounding-flagged, `tj-vz7o-luna-glm-20260810-rerun/789`, which is the
  baseline's own behaviour restored and is what the repair path exists for.
- Dialogs 28, 436, 789, 875 and 1291 were read individually. The differences
  are bounded to duplicate identity/name asks or question folding described in
  the stage artifact.
- The repair judge, measured four times on stored dialogs 819 and 789, 60 calls
  and $0.0051 in total, every notification suppressed. D6 (8 calls): the judge
  contributed nothing, 8 of 8 deliveries came from the deterministic fallback.
  `tj-3h0w` (20): unanchoring works, no answer was byte-identical to the
  candidate, but delivery was 2 of 20. `tj-3i8m` found why -- a flag arrived as
  the bare string `future_stock_check` -- and after each flag gained
  `flagged_sentences` and `rules`, delivery was 20 of 20 with zero handoffs.
  `tj-b9mg` (32) then read the wording: correct on both dialogs, 8/8 in the
  confirming round. Two refinements were read and reverted; one produced
  "assembly is not a service we offer", which is false and which no guard
  catches. Rules are now written to be safe if quoted, because the judge quotes
  them almost verbatim. `tj-uhbq`, closed: an approval means the judge read the
  reply and found it supported, so the original text is what we send.
- `tj-7gpw`: every number this project has measured, the 18.94 baseline
  included, was scored on a prompt missing two blocks production always sends.
  On a greeting opening that is the substantive-reply directive, which fires on
  every turn that has text, the consultative opening and project directives
  where the opening earns them, and the whole ask permission list. Directive
  work read as unmeasured because the paid round did not send it either. The
  consequence is recorded rather than hidden: after this fix a round is not
  comparable to the 18.94 baseline, and the fixed harness needs its own
  baseline before any build change is measured on it. The recorded
  `generation_prompt_set_digest` will differ from every earlier round, so the
  break is visible in the evidence itself.
- The measured round of 2026-08-12, `tj-7gpw-parity-baseline-c-20260812`:
  twenty Luna generations plus one repair-judge call, $0.0054, judged by the
  root orchestrator reading blind. Weighted mean 14.6/30, 95% interval
  [12.0, 17.1]; raw mean 10.6; 11 openings against a 9.6 ceiling reach 7.2
  (75% of it) and 9 openings against a 30.0 ceiling reach 23.5 (78%). Zero
  critical failures, 20/20 in the customer's language, accepted.
  `generation_prompt_set_digest` is
  `61b6c9229ab295a41b71ad2b8097e8e111949c142916a8449855dbc362be8e15`, which
  differs from every earlier round because those rounds sent a prompt
  production does not send. This round is the new baseline; the 18.94 figure is
  not comparable to it, and neither is any paired delta taken against it.
  Three earlier attempts at this round died on upstream rate limits and cost
  thirteen further generations, journalled in the `-` and `-b-` directories.
- What the reading found: 18 of 20 replies say Treejar's line of business
  twice, three of them as a lower-case fragment copied out of the directive's
  own example clause, because the directive still claimed the opening does not
  say what Treejar does. That is `tj-fcv8`, fixed but not yet re-measured. And
  19 of 20 never ask how to address the customer although the ask was permitted
  every time, which is rule 3 at nearly zero across the set and is not yet
  opened as work.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff check and format are clean over `src/ tests/ scripts/`; Mypy is clean over
  174 source files; full Pytest is `3678 passed, 19 skipped`; process
  verification passed. Re-run after `tj-w224`, `tj-9e15`, `tj-7gpw`, `tj-1fad`,
  `tj-2p4c`, `tj-9dp2` and `tj-fcv8`. The protected policy replay aggregate is
  unchanged at `825f26ca85533b6d…` against the frozen `1fc87c04…` baseline:
  today's work is generation-side and harness-side, and the deterministic reply
  chain did not move.

## Constraints

- Push to `origin/main` was authorized by the owner on 2026-08-12 and performed.
  No PR, deploy, production/staging mutation, model-configuration change or
  real-user message is authorized or performed.
- Paid calls: eight for D6 plus twenty authorized for `tj-3h0w`, all on stored
  dialogs 819 and 789, all with the failure page suppressed. The owner then
  authorized a re-baseline round on the frozen twenty on 2026-08-12, followed
  by `tj-ge07`; the re-baseline is spent, at $0.0054 plus $0.0012 lost to the
  three rate-limited attempts. No paid call outside `tj-ge07` is permitted
  without new authority, and the paired round that would confirm `tj-fcv8` is
  not among them.
- The canonical runtime target remains `https://noor.starec.ai`; it was not
  contacted or changed.

## Documentation and graph review

- `docs-reviewed: updated` — the stage summary, artifact and this handoff record
  the durable policy and privacy-safe proof.
- `project-index: reviewed-no-change` — no module was added, removed or moved.
- `graph-reviewed: no-change-needed` — Graphify is not initialized.

## Next recommended

Next stage id: not opened

Recommended action: select the next open Beads goal from current repository
truth. Do not push or deploy this stage without new authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage only after selecting the next open Beads goal from
current repository truth.

## Explicit defers

- `tj-fcv8`: the directive fix is delivered and unverified. Its acceptance asks
  for a paired round on the same twenty openings, and no paid call is
  authorized for it.
- Rule 3, the name ask, is missing from 19 of 20 openings while permitted every
  time. Read in today's round, not yet opened as work, and not fixed.

- `tj-2m5m.4`: separate out-of-scope discovery work remains tracked in Beads.
- `tj-2m5m.4`: the prompt half is delivered and unmeasured. The owner decided
  on 2026-08-12 that the structural gate waits for the numbers rather than
  preceding them, so the required job slot is not built. The measured round it
  waits for cannot be run yet: `tj-7gpw` is fixed, but the frozen set is
  twenty first-turn greeting openings, and `solution_consultation_directive`
  fires on the solution stage. `tj-ge07`, the frozen multi-turn set, is the
  blocker and needs its own paid-call authority.
- Deployment and live runtime verification are outside this local stage and
  were not authorized.
