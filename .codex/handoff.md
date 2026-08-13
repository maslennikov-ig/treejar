# Orchestrator Handoff

Updated: 2026-08-13
Current branch: `main`
Current stage id: `tj-q1a2-one-reply-owner`
Status: D1-D6 and the audit fix `tj-w224` are delivered locally with all gates
green; `main` is pushed to `origin/main` with CI green. No deploy or runtime
mutation was authorized or performed. Five measured rounds were read blind
with the owner's authority: six on the frozen twenty, taking the weighted mean
14.6 to 18.7 of 30, and three over the whole Arabic population, 9.6 to 10.6.
`tj-fcv8`, `tj-l0e3`, `tj-fcfn`, `tj-jfmv`, `tj-40gc` and `tj-z1fn` are all
found, fixed and closed. On the twenty, every rule the set can charge now
reads 2.00 except rule 5 at 1.95.

Documentation: no external/versioned boundary — the behavior is owned by the
local reply-policy contract, Python implementation, tests and protected replay.

## Current truth

- Reply asks are derived once before generation by `permitted_asks_for_turn`,
  and the prompt and guards consume the same immutable set. The name ask is
  state-owned: `customer_name_asked` is recorded only when an ask reaches the
  customer, and `_store_name_gate_pending_request` is the one re-elicitation
  trigger. A name in the current inbound message joins the current-message
  facts, so a first-turn signature cannot receive another name question in
  either language -- `tj-40gc` added the Arabic introduction shapes, bounded
  like the English ones so a statement about the request is never a sender.
- The repair judge receives the original reply and flag reason, not the
  deterministic candidate. Unavailable, rejected, empty and `cannot_fix` fall
  back to the validated grounding repair; a fallback of only Noor's opening
  plus a question creates the manager handoff.
- `run_repair_judge` notifies on failure by default; only an offline diagnostic
  passes `notify_on_failure=False`. The protected journal lives in the Git
  common dir, never the working tree.
- `--second-reader` adds the paid reader beside the root, never instead, and is
  off by owner decision. It set the paid model as the judge until 2026-08-13
  and had raised `KeyError` since the vendor split, so no two-reader round had
  ever run.
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
- `solution_consultation_directive` carries rules 9 and 10 into the
  presentation turn, one stage only. Generation-side; the replay cannot see it.
- `collapse_question_form` runs before the first-turn opening guard, not after,
  under its unchanged `REDUCING` contract. The guard folds the canonical name
  question on and the collapse drops every question after the first, so the old
  order deleted that fold on every first turn. The one-question bound is the
  directive's own: a folded pair counts as one, the name ask being its half.

## Protected evidence

- The frozen `tj-t6ug` replay baseline remains
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`, never
  re-baselined. Current aggregate `1b425bd1f66a9189a07436f5d75b3bbcb71d68ca716e94b6f0d4c86627c97866`,
  7 records differing across the three stored runs -- dialogs 28, 875 and 1291,
  each read individually and intended. It was 55 until the guard order was
  restored on 2026-08-13, and the 7 are a strict subset: 48 removed, none
  introduced. One reply is grounding-flagged, which the repair path exists for.
- The repair judge, measured four times on stored dialogs 819 and 789, 60 calls
  and $0.0051, notifications suppressed. Delivery is 20 of 20 with no handoffs
  since each flag carried `flagged_sentences` and `rules`.
- `tj-7gpw`: every number measured before 2026-08-12, the 18.94 baseline
  included, was scored on a prompt missing the runtime directives and the ask
  permission list, so nothing after is comparable to it. The replacement
  baseline is `tj-7gpw-parity-baseline-c-20260812`, digest `61b6c9229ab295a4…`;
  its reading found `tj-fcv8`.
- Six rounds on the same twenty, same reader, each changing exactly one thing,
  all accepted with full coverage. Weighted mean 14.6, 15.0, 16.1, 17.5, 17.7,
  18.7 of 30, the last interval [15.6, 21.7]; raw 10.6 to 13.8; the 11
  low-ceiling openings 75% to 100% of their 9.6 and the 9 others 78% to 99% of
  30.0. Per-round attribution is in Beads. One `tj-l0e3` round is discarded as
  unfaithful under `tj-l0e3.2`.
- The Arabic rounds over `arabic-12`, every Arabic opening the corpus has, 12
  of 1358 -- a population, not a sample. Weighted 9.6 to 10.6, low band 93% to
  99%. That mean is *not* comparable to the twenty's: 11 of 12 sit in the 9.6
  band against 11 of 20, so only the band compares. The hypothesis that an
  English directive fails to reach Arabic is disproved; rule 4 led English
  throughout. What Arabic cost was `tj-40gc` and `tj-z1fn`, both closed.
- `tj-z1fn` is the lesson worth keeping. Quoting the canonical opening helped
  Arabic and cost English rule 7 2.00 to 1.80: four replies answered the
  quotation with a capability list, reading the catalogue as the thing "the
  opening does not cover". Naming what it leaves uncovered -- the customer --
  removed them. Measure both sets before shipping a shared directive.
- No corpus text, request body or reply body is tracked. Durable evidence uses
  dialog ids, integers and digests only.

## Verification

- Ruff and format clean over `src/ tests/ scripts/`; Mypy clean over 174 source
  files; full Pytest `3695 passed, 19 skipped`; process verification passed. The
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
  one block, then on 2026-08-13 the `tj-l0e3`, `tj-fcfn`, Arabic and `tj-z1fn`
  rounds, and the two-reader round. Total spent $0.1908 across ten rounds, of
  which $0.1627 is the single paid second reader and $0.0045 bought nothing: $0.0020 to four attempts killed by upstream 429s and a 503, and
  $0.0025 to the `tj-l0e3` round discarded as unfaithful under `tj-l0e3.2`. The `tj-ge07` baseline
  is authorized and deliberately not taken. The canonical runtime target
  remains `https://noor.starec.ai`; it was not contacted.

## Documentation and graph review

- `docs-reviewed: updated`; `project-index: reviewed-no-change` — no module was
  added or moved; `graph-reviewed: no-change-needed` — Graphify is not
  initialized.

## Next recommended

Next stage id: not opened. Recommended action: re-read one stored round under
`docs/root-reading-convention.md` and report the drift. No deploy authority.

## Starter prompt for next orchestrator

Use $orchestrator-stage after selecting the next open Beads goal.

## Tracker after the 2026-08-13 audit

- 27 live issues audited against current state; 16 closed with recorded
  reasons, 1 deferred. Nothing was closed on a title alone. Verified in code:
  `tj-6f4z`, `tj-07bs`, `tj-g3f`. Superseded by measurement or owner decision:
  `tj-wvo4`, `tj-odeq`, `tj-vz7o.8`, `tj-vz7o.9`, `tj-vz7o.10`, `tj-vz7o.13`,
  `tj-swgu.14`, and the P0 epics `tj-2m5m` and `tj-swgu`, all children closed.
  Not to be done as written: `tj-vz7o.4` and `tj-vz7o.5`, the client's own
  judge; `tj-ge07`; `tj-2m5m.4`. `tj-i653` deferred: it needs live state.
- A candidate explanation was rejected rather than used: `tj-jlx4` looked like
  reader variance, but the gap is 2.0 raw points while S07 moved 6.58 with
  non-overlapping ranges, and the bead already diagnosed a content choice -- a
  closing turn offering two coffee tables to a lab that asked about fume hoods.
  Open at P2; it needs a rig with tools.
- Priority inversion named: `tj-final27.6` is engineering-complete, disabled
  safe and policy-gated, and waits on one written client sentence -- a referral
  policy or an explicit exclusion -- which blocks `tj-final27.9`, the final
  acceptance pack. Raised to P1 for what it blocks.
- `tj-vz7o.12` narrowed and retitled: the reply sometimes has catalog rows and
  quotes none -- dialog 436 had three and quoted none while 366, 420 and 1067
  quoted. Same question as `tj-6tx6`'s remainder; treat them together.

## Owner decisions of 2026-08-13

- Referrals are deferred until the owner's own separate message. Do not chase
  and do not read the missing policy as a defect; `tj-final27.6` is
  engineering-complete and is the only thing blocking `tj-final27.9`.
- Rule 11: disposition 3. A discount is a manager's decision or is already in
  the catalog price, so Noor never offers one and the zero is policy. Every
  score prints the policy cap of 28/30 beside it. The permitted shape ships:
  verified rows as one package at the catalog price, no concession.
- The client document was decided rather than asked. It leads with the Zoho
  deal export: outcomes are visible for 192 of 1400 dialogues, so we can say
  Noor does what the rubric asks but not that Noor sells. The four-criteria
  statistic is reframed on the owner's point that people not doing a thing is
  no evidence against it. The evaluator prompt is withdrawn.
- Deploy and live verification are authorized. Production is current, not
  stale: CI deploys automatically on any push to `main` touching `src/`, and
  the job succeeded on `d19bfdb`, the last such commit, which carries every fix
  of 2026-08-12 and 2026-08-13. `/api/v1/health` reads ok, redis and database
  ok. `tj-9scy`: no endpoint reports the deployed SHA, which is why a stale
  assumption about the live build survived a session unchecked.

## Explicit defers

- Seven rules of fifteen cannot be charged by any rig this project has: 14 and
  15 need a tool-filled next step or a deferred decision (one second message in
  913 defers), 6, 10 and 13 a project signal (9 of 913), 11 a two-family order
  (16 of 106), 12 a later turn. This bounds what any opening round can claim
  and it closed four beads. The two-turn set is kept for a tools-enabled rig.
- The reader gap is a number now, `tj-4q79`: one round carried both readings,
  the root judge blind and `z-ai/glm-5.2` paid beside it at $0.1627. Mean
  absolute gap 2.0 raw points per opening, worst 4.0; rules 1, 2 and 8 agree
  exactly, the paid reader harsher on rule 4 (-0.80), rule 9 (-0.70) and rule 5
  (-0.50). A paired delta under about 2 raw points is inside reader variance:
  the session series clears it, raw 10.6 to 13.8, but no single round should be
  defended by its total. No second reader again by owner decision, so
  `docs/root-reading-convention.md` holds the 0/1/2 standard. The re-read that
  would make that a drift number is still owed.
- Rule 5's ceiling on the frozen twenty is 1.95, not 2.00: dialog 28 is a job
  application with no furniture need and rule 5 is charged anyway. The measured
  1.95 is that ceiling; the rubric is not changed for it.
- Deploy and live runtime verification were not authorized and were not done.
  `tj-ee5f.1` needs real transports and production producers; `tj-ee5f.5` waits
  on the Wazzup provider fixing delivered/read callbacks, which is theirs.
