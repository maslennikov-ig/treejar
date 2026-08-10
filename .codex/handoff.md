# Orchestrator Handoff

Updated: 2026-08-10
Current branch: `main`
Current stage id: `tj-4e5j`
Status: 2026-08-09's plan is deployed and measured; 2026-08-10's name-gate
removal is built, committed and green, not deployed. `tj-swgu`'s release-bound
re-run still needs authority that is not granted.

## Current truth

- **Production is not on Supabase.** Project `vlxgzhbtnwysaqonvlte` is INACTIVE,
  which is why DNS, the pooler, REST and the MCP failed at once. It is Postgres
  in `noor-db-1` on `noor-server`, reached as `db:5432`.
- **No real customer has ever written Russian.** Of 69 real-phone conversations
  0 carry Cyrillic, 6 Arabic; all 28 Cyrillic messages are our harness.
  `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes and that is load-bearing**:
  7 of 920 SKUs begin with Cyrillic `СН`, 132 names use `х` as the dimension
  separator, `tests/test_catalog_homoglyphs.py` guards it.
- **The main model is Luna, and all three layers now say so**: `system_configs`,
  `src/core/config.py`, the production `.env`. For three days only the row did,
  while the source said `z-ai/glm-5.2` -- shadowed. `tj-uidf`.
- **Two judges, do not confuse them.** Acceptance is a blind Claude reader panel,
  never a paid model; an external judge belongs only to runtime
  `ai_quality_controls`. Nine readers at 11-12 packets gave disagreement 1.58.
- **A condition on the world is a guard; a condition on what Noor thinks she
  already did is a leak**, since she is both actor and judge. Four rules died on
  their own escape clauses; five tests hold them out. `tj-2m5m.8`.
- **The prompt carries the business's own goal** -- understand the need and
  quote in the shortest time -- plus jobs-to-be-done, SNAP and four facts before
  quoting. `docs/Research/`.
- **Owner decision 2026-08-08: generation stays varied.** `PATH_CORE_CHAT` is
  not pinned to temperature 0; the price is k runs per scenario per side, and
  measured within-scenario sd is about 1.7.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down on a signed
  opening; rule 11 needs a two-family order; an always-on directive forbids a
  reply that adds nothing. `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **This model follows an instruction and loses a prohibition** -- owner,
  2026-08-10. Rule 11 was one permission wrapped in two bans and scored 0.00; it
  now states the act. Six formatting bans duplicated `_format_for_whatsapp`,
  which already converts every one of them on the way out. The consultative
  directive now contains no "never" at all and a test holds it there. Bans that
  are real constraints live once, in the grounding policy. 37 -> 28 of 238.
- **24.0 is retired and the rubric is frozen.** Five changes in one week, all
  raising the number, so nothing before 2026-08-09 is comparable. The fork makes
  rules 6, 10 and 13 inapplicable to an ordinary order and normalises the rest
  back to /30, so `score_by_shape.py` refuses one number. `tj-07bs`.
- **The widening is not what `tj-2m5m.4` was filed as.** Rule 9 is 1.51/2 on 85%
  of reads, up from the 0.40 it was filed on; rule 10 is 0.88 on 29%, third
  rather than first, behind rules 11 and 13.
- **Production runs `8b75888`** (2026-08-09, readback matched, health ok).
- **The round moved nothing in aggregate, and that is the finding.** At
  `8b75888`, 53 packets, two blind reads each over 9 readers: project **20.02
  +/- 1.00** against 19.95, transactional **21.16 +/- 3.49** against 20.77 over
  the same 11 scenarios. Both deltas are far inside their own uncertainty.
  Reader disagreement **1.58**, the lowest yet; applicability came from stored
  state, frozen, and all 106 reads honoured it.
- **The new transactional baseline is 18.94 +/- 3.74 over 7.6 rules across 15
  scenarios**, including `R06`-`R09`. Compare with that, never with 21.16, which
  exists only for the like-for-like eleven.
- **The realistic shapes are the gap, and 2026-08-10 aims at it.** `R07` 7.35,
  `R06` 8.10, `R09` 10.50, `R04` 7.95 against `R02` 29.07 and `S04` 28.48, at the
  same 6-8 applicable rules. Good at a customer who writes a brief, poor at one
  who writes four words and leaves.
- **A guarantee that never runs is worth nothing, and one of ours did not.**
  Rule 11's package line appeared in 0 of 53 packets, read a mapping empty on an
  ordinary selling turn, and was deleted on 2026-08-10 rather than repaired;
  `tj-wvo4` holds the terms for bringing it back. Rule 13's guard did fire, on 3
  packets, moving it **0.00 -> 0.75**, attributable because nothing else touched
  rule 13. `tj-odeq`.
- **The first turn answers, then asks the name in passing** -- owner decision,
  2026-08-10, `58d9a2f`. The gate spent the only reply a third of customers ever
  read; both copies went, the engine short-circuit and the kernel's own flow.
  Ask once and let it go: a customer who ignores it has answered, and
  `refuse_to_chase_the_name` holds that on turns we actually sent. Three defects
  it uncovered are fixed in the same commit and named in its message. Parked
  requests still resume until live conversations age out. `tj-0ai0`, `tj-i653`.
- **`tj-jxv7` closed on live evidence**: `R03` 9.00 -> 20.63, every new run above every old one, against within-scenario sd 1.34.
- **`S07` 28.13 -> 21.55 and `R05` 28.13 -> 24.40, outside their own run spread
  and unexplained.** Ruled out by test, not argument: the classifier reclassifies
  every turn of both identically and the guard touched neither. `af4db16` shipped
  between baseline and round unmeasured, so a round measures a build, not a diff.
  `tj-jlx4`.
- **A route answers before it asks, or it stands down.** `tj-ja1v`. The two
  that only asked now read the catalog row first, through read-only wrapped
  lookups -- a failure costs the fact, never the turn. `DeterministicRoute.carries`
  is the contract, `tests/test_deterministic_routes.py` enforces it, and
  `ROUTES_THAT_ONLY_ASK` names the eight still giving a question and nothing
  else so a new one cannot join silently.
- **The model reads what the customer said; code owns catalog facts.**
  `record_customer_requirements` writes the four quoting facts and company
  activity into typed slots, bounded, with a catalog check on the SKU so a
  mis-extraction cannot become a fact. `tj-1osj`, `tj-o29r`.
- **The test was partly wrong, and not the bot's fault.** Against 74 real
  openings: 34% a bare greeting, median 53 chars against our 126, real median 2
  customer turns. S01-S10 are frozen with no threshold; the target moved to the
  nine realistic scenarios. `tj-2m5m.10`, `tj-6f4z`.
- **glm-5.2 adopted for the runtime judge on its sd**, 1.3 against
  deepseek-v4-flash's 3.8. `ai_quality_controls` still names the latter, all
  three scopes `disabled`; repointing it is a separate, unrequested change.
- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`; refuses a verdict
  without repeats. **No movement smaller than its own uncertainty is evidence.**

## Local verification

- 2026-08-10 at `7c34d55`: Ruff and format over 350 files, Mypy over 168
  sources, Pytest `3424 passed, 19 skipped`, `run_process_verification.sh` OK.
  Supersedes earlier figures.

## Active work

- Review children `R-01..R-16`, `R-19`, `R-20`, `tj-ee5f.12` and `.14` are
  closed; `.7`, `.8` and `.1` stay open for release-bound acceptance, `.13`
  depends on them, `.5` is blocked on the Wazzup status bug.
- Closed 2026-08-09: `tj-swgu.11`, `tj-swgu.12`, `tj-2m5m.10`, `tj-jxv7`,
  `tj-ja1v`. Closed 2026-08-10: `tj-2m5m.9`. In progress: `tj-0ai0`, built and
  awaiting a measured round. Open: `tj-6tx6` (half fixed), `tj-odeq`, `tj-jlx4`,
  `tj-wvo4` (guard deleted, terms for reopening in its notes), `tj-i653`.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- The product system prompt grew on 2026-08-09 by owner decision; not again
  without one.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- Run `repin_traceability_sources.py` after moving current state, or three
  manifest tests fail on a digest that says nothing about what changed.

## Next recommended

Next stage id: `tj-ee5f`. What the round measured and why:
`docs/reports/2026-08-09-the-measured-round-at-8b75888.md`. What was built and
the re-measure that redirected it:
`docs/reports/2026-08-09-answer-before-you-ask-and-what-the-re-measure-says.md`.
The ordered plan it all came from:
`docs/superpowers/specs/2026-08-09-deterministic-routes-and-the-forked-rubric-spec.md`.

Recommended action: **measure `7c34d55`.** It aims squarely at the realistic
shapes -- `R07` 7.35, `R06` 8.10, `R09` 10.50, `R04` 7.95 against `R02` 29.07 --
by giving the first turn back to the customer's own question. Compare against
the 15-scenario baseline **18.94 +/- 3.74**, not 21.16. Rules 7, 11 and 13 are
the ones to read per-rule: 7 and 13 should hold, 11 is the test of whether a
positive instruction lands where two prohibitions did not.

Then `tj-jlx4`, where two scenarios fell outside their own spread and nothing in
the diff explains it. `tj-odeq` needs no code, only a customer who answers.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` stage. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, then the reports under Next
recommended. The rules that cost the most: a rubric change and a build change
never ship in the same round; a shape is compared only with itself over the same
scenarios; two transcripts get read by eye every round, which is how three of
the last round's findings were made; a guarantee nobody checked actually fired
is worth nothing; and this model follows an instruction where it loses a ban.
Preserve frozen `AC-01..AC-30`.

## Approval gates

Push, deploy and one acceptance run were granted on 2026-08-09, spent on
`8b75888`, and are closed. `7c34d55` is committed locally and needs a fresh
grant to reach production. No authority is currently granted for paid OpenRouter
calls, model config changes, push, deploy, production mutation, test-only
business effects, or real-user messaging.

## Explicit defers

- Nothing built on 2026-08-10 has met a live conversation. Every effect claimed
  for the name-gate removal and the reworded directives is a headroom estimate
  until a deploy and a repeated run.
- `tj-i653`: the parked-request machinery, about 500 lines, stays reachable
  until no live conversation carries `name_gate_pending_request`.
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
