# Orchestrator Handoff

Updated: 2026-08-09
Current branch: `main`
Current stage id: `tj-4e5j`
Status: epic `tj-4e5j` is complete and locally green. Epic `tj-swgu` still has
its release-bound production re-run outstanding, which needs authority that is
not granted. The ordered plan of 2026-08-09 is delivered on the code side and
unmeasured: nothing in it has met live traffic.

## Current truth

- **Production is not on Supabase.** Project `vlxgzhbtnwysaqonvlte` is INACTIVE,
  which is why DNS, the pooler, REST and the MCP failed at once and looked like a
  network fault. It is Postgres in the `noor-db-1` container on `noor-server`,
  reached as `db:5432` over the compose network.
- **No real customer has ever written Russian.** Of 69 real-phone conversations
  **0** carry Cyrillic, 6 Arabic; all 28 Cyrillic messages are our own harness.
  "No evidence", not "impossible". `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes, and that is
  load-bearing.** 7 of 920 SKUs begin with Cyrillic `СН`, 132 names use Cyrillic
  `х` as the dimension separator, and `tests/test_catalog_homoglyphs.py` guards
  the maps that let Latin `CH 135` reach it.
- **The main model is Luna, and all three layers now say so**: `system_configs`,
  `src/core/config.py` and the production `.env`. For three days only the row
  did, while the source said `z-ai/glm-5.2` -- shadowed. `tj-uidf`.
- **Two judges, do not confuse them.** Acceptance is a blind Claude reader
  panel, never a paid model; an external judge belongs only to runtime
  `ai_quality_controls`. Compare within one instrument.
- **The acceptance figure is two figures, and 24.0 is retired.** At `ac36265`,
  two reads per packet across six readers: **project 19.95 +/- 0.93 over 11.0
  applicable rules, transactional 20.77 +/- 4.41 over 7.6**. The fork made rules
  6, 10 and 13 inapplicable to an ordinary order and the arithmetic normalises
  what remains back to /30, so two conversations scored a perfect 30 over the
  eight easy rules alone. `score_by_shape.py` refuses to print one number.
  Reader disagreement fell 2.86 -> **1.96** at 13 packets each. **The rubric is
  frozen**: five changes in one week, all raising the number, the last with no
  build change at all -- nothing before 2026-08-09 is comparable. `tj-07bs`.
- **Rules die on their own escape clauses, and four did.** **A condition on the
  world is a guard; a condition on what Noor thinks she already did is a leak**,
  since she is both actor and judge. Four removed 2026-08-08, five tests hold
  them out. `tj-2m5m.8`.
- **The prompt carries the business's own goal** -- understand the need and
  quote in the shortest time -- plus jobs-to-be-done, SNAP and four facts before
  quoting, and a ban on naming any method to the customer. SPIN, Challenger,
  MEDDIC and Sandler stay out. `docs/Research/`.
- **Owner decision 2026-08-08: generation stays varied.** `PATH_CORE_CHAT` is
  not pinned to temperature 0. The price is k runs per scenario per side;
  measured within-scenario sd is about 1.7.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down on a signed
  opening; rule 11 needs a two-family order; an always-on directive forbids a
  reply that adds nothing; the consultative opening carries rules 9, 10 and a
  verified package, never a discount. `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **Production runs `0c4dd32`** (2026-08-09, readback matched, health ok).
- **A route answers before it asks, or it stands down.** `tj-ja1v`. Three of
  its eight routes were already gone and four already write their prose through
  the model. The two that only asked now read the catalog row first:
  `product-quantity-clarify` states price and live stock before asking the
  quantity, and the two missing-details routes say what the quotation covers and
  what it comes to before asking for a name and an address. Both lookups are
  read-only and wrapped -- a failure costs the fact, never the turn. The
  contract is `DeterministicRoute.carries`, enforced by
  `tests/test_deterministic_routes.py`; `ROUTES_THAT_ONLY_ASK` names the eight
  that still give a question and nothing else, written out so a new one cannot
  join silently.
- **A SKU typed without a space was not a product question**, so
  "hi do u have ch616 in black" ran on the verified-answer branch under *answer
  only from the FAQ, do not invent prices* against an empty FAQ, with no turn
  directives attached at all. The whole of `tj-jxv7`, and the second half of
  `tj-6f4z`. The hypothesis that issue filed does not hold. Letters and digits
  must stay adjacent, or "for 12" and "AED 300" become SKUs.
- **The widening was re-measured, and it is not what it was filed as.** From
  the stored `ac36265` panel scores, 82 reads over 41 packets, no live traffic:
  rule 9 is **1.51/2** on 85% of reads, up from the 0.40 `tj-2m5m.4` was filed
  on, so half that issue is closed. Rule 10 is 0.88 on 29%, confirmed and now
  third. Ahead of it, **rule 11 at 0.28** (`tj-wvo4`) and **rule 13 at 0.00 on
  every one of its twelve reads** (`tj-odeq`) -- directives that never fire,
  which is where rule 7 was before the opening guard carried the value
  proposition deterministically.
- **The realistic set is nine.** Added: `R06` two messages and gone, `R07` a
  voice note with a SKU the catalog does not hold, `R08` Arabic switching to
  English mid-thread, `R09` delivery only. `S01`-`S10` untouched, none of the
  four yet run. `tj-2m5m.10`.
- **The model reads what the customer said; code owns catalog facts.** Owner
  call after three parser failures in one day. `record_customer_requirements`
  writes quantity, budget, deadline, sign-off and company activity into typed
  slots, bounded, with a catalog check on the SKU so a mis-extraction cannot
  become a fact. Invented USD ranges are gone; budget questions are answered
  from catalog rows in AED. `tj-1osj`, `tj-o29r`.
- **The test was partly wrong, and not the bot's fault.** Against 74 real
  openings: 34% a bare greeting where none of ours is, median 53 chars against
  our 126, real median 2 customer turns. Owner decision 2026-08-09: S01-S10
  frozen as a regression set with no threshold, and the target moves to the
  realistic set built to the measured shape. `tj-2m5m.10`, `tj-6f4z`.
- **glm-5.2 adopted for the runtime judge on its sd**: 1.3 against
  deepseek-v4-flash's 3.8. The argument is independence. But
  `ai_quality_controls` still names `deepseek/deepseek-v4-flash` with all three
  scopes `disabled`; repointing it and enabling `bot_qa` is a separate,
  unrequested change.
- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`; refuses a verdict
  without repeats. **No movement smaller than its own uncertainty is evidence.**

## Local verification

- 2026-08-09 at the route and classifier work: Ruff and format over 348 files,
  Mypy over 167 sources, Pytest `3406 passed, 19 skipped`,
  `run_process_verification.sh` OK. Supersedes earlier figures.

## Active work

- Review children `R-01..R-16`, `R-19`, `R-20`, `tj-ee5f.12` and `.14` are
  closed; `.7` and `.8` stay open only for their release-bound acceptance.
  `.13`: future paid isolated core/background comparison, depends on `.7`, `.8`,
  `.12`, `.14`. `.1`: later winner-only release-bound acceptance. `.5`: blocked
  on the provider-confirmed Wazzup status bug.

- `tj-swgu.11`, `tj-swgu.12` and `tj-2m5m.10` closed 2026-08-09 -- verified,
  superseded and delivered, as the ordered plan directed. `tj-jxv7` and
  `tj-ja1v` stay open for their live verification alone. Earlier accepted
  artifacts remain under `docs/superpowers/`.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- The product system prompt grew on 2026-08-09 by owner decision; not again
  without one.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- Run `repin_traceability_sources.py` after moving current state, or three
  manifest tests fail on a digest that says nothing about what changed.

## Next recommended

Next stage id: `tj-ee5f`. The ordered plan is
`docs/superpowers/specs/2026-08-09-deterministic-routes-and-the-forked-rubric-spec.md`;
what was delivered against it and the re-measure that redirects the rest is
`docs/reports/2026-08-09-answer-before-you-ask-and-what-the-re-measure-says.md`.

Recommended action: **spend a measured round.** The code side of the ordered
plan is done and none of it has met live traffic, so the honest state of every
claim above is a headroom estimate. One acceptance run against the two
baselines -- project 19.95, transactional 20.77 -- says whether the route work
moved anything, and it needs its own grant.

After that, and only one at a time: `tj-odeq` (rule 13 at 0.00) then `tj-wvo4`
(rule 11 at 0.28). Both are directives that never fire and both want the
name-gate treatment -- a deterministic guarantee carrying what a salesperson
carries. Neither was attempted on 2026-08-09 because neither could be shown to
work in the same round as the route changes.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` stage. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, then the ordered plan and the report
linked under Next recommended. Between them they carry the two baselines and
the seven rules of engagement; the three that cost the most are that a rubric
change and a build change never ship in the same measured round, that a shape
is only ever compared with itself, and that two transcripts get read by eye
every round. Preserve frozen `AC-01..AC-30`.

## Approval gates

Push, deploy and one acceptance run were granted on 2026-08-08 and spent; all
are closed again. No authority is currently granted for paid OpenRouter calls,
model configuration changes, push, deploy, production mutation, test-only
business effects, or real-user messaging. An acceptance run is live traffic and
needs its own grant each time.

## Explicit defers

- Rule 11 was settled on 2026-08-08: the owner declined a discount, so the
  directive offers a package of verified rows at their combined total instead,
  and the rubric charges the rule only on a two-family order. No directive
  written since `tj-swgu.14` has met a live conversation; every effect claimed
  for them is a headroom estimate until a deploy and a repeated run.
- `tj-swgu` has no stage scaffold: `.codex/stages/tj-swgu/` does not exist and
  `workspace.current_stage_id` is still `tj-feet`, so `check_stage_ready.py` and
  `run_stage_closeout.py` both refuse the stage. Whoever closes `tj-swgu` has to
  scaffold it first, which means writing another stream's manifest and ledger.
- Correcting the superseded 18.0/18.5/18.2 figures quoted outside this handoff
  is `tj-swgu.13`, with `tj-swgu.12`. Sealed rounds are superseded, never
  rewritten.
- Registering `repin_traceability_sources.py` in the `AGENTS.md` Operational
  State inventory. Tried and reverted: `AGENTS.md` is pinned as `repo-contract`
  in the same frozen registry, so one added line breaks three manifest tests.
- `tj-feet.10` stays off: the owner's condition was the confirming round backing
  the projection, and it measured `12/42` turns rewritten against a projected
  `1/37`. Option (b), a structured main output removing the second call, is
  unbuilt and still the more attractive of the two.
- `codex/tj-feet` and `codex/tj-ee5f-quality-model-battle` both edit this
  handoff; the other stream's edits are uncommitted in its own worktree.
- `tj-ee5f.13.9` / product-runtime `R-17`: validate and centralize model ids,
  reasoning capabilities and cache-control support in `config.py` and
  `safety.py`. Separate from `.14`, which must not be read as implying it.
- `tj-ee5f.5`: after Wazzup announces its fix, run one bounded protected
  `sent -> delivered -> read` proof.
- S09 and S10 ran once, not three times: repeating them multiplies real business
  effects (a PDF to the test chat, a CRM opportunity) nobody has authorised.
- Existing raw production/model evidence stays protected outside Git, and
  repository-history privacy cleanup is a separate destructive decision.
