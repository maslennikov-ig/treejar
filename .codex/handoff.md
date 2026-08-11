# Orchestrator Handoff

Updated: 2026-08-10
Current branch: `codex/tj-vz7o-corpus-bridge`
Accepted stage id: `tj-vz7o-openings`
Status: the real-opening rerun passed its frozen contract -- 20/20 replies,
**2 critical failures down to 0**, paired score +0.82 +/- 1.45 so it did not
move. Judge is Claude by owner instruction; GLM is a second reader and sits
**+2.05 raw points below me on all twenty**. `tj-vz7o.4` authority stays
declined.

## Current truth

- **Production is not on Supabase.** Project `vlxgzhbtnwysaqonvlte` is INACTIVE,
  which is why DNS, pooler, REST and MCP failed at once. It is Postgres in
  `noor-db-1` on `noor-server`, reached as `db:5432`.
- **No real customer has ever written Russian.** Of 69 real-phone conversations
  0 carry Cyrillic, 6 Arabic; all 28 Cyrillic messages are ours. `tj-4e5j.2`.
- **Cyrillic lookalikes in the catalogue are load-bearing**: 7 of 920 SKUs begin
  with Cyrillic `СН`, 132 names use `х` as the dimension separator;
  `tests/test_catalog_homoglyphs.py` guards it.
- **The main model is Luna, and all three layers now say so**: `system_configs`,
  `src/core/config.py`, the production `.env`. For three days only the row did,
  while the source said `z-ai/glm-5.2` -- shadowed. `tj-uidf`.
- **Claude judges acceptance** -- owner, 2026-08-10. `claude-haiku-4.5` is the
  client's; `glm-5.2` is runtime QA and a second reader only. On the 2026-08-10
  rerun I sat **+2.05 raw points above glm-5.2 on all twenty**, systematic, not
  noise. So **18.71 and 11.0 are not comparable either way**: different judge
  *and* different set. Share of ceiling travels between judges far better than
  the level does: 87/86 and 64/60. Map-free panel disagreement 1.08 over 53
  double-read packets; the older 1.58 is on the weighted ruler.
- **A curly apostrophe cost four of twenty customers their whole reply.**
  `_strip_legacy_identity` knew only `I'm`, the model writes `I’m`, so its own
  intro survived and `_has_identity` then blanked the body. All four were bare
  greetings -- 34% of real traffic. Fixed in `tj-vz7o.11`; found by eye, not by
  the detector, which passed all 20. `tj-vz7o.12` holds four more reader
  findings, the sharpest being an unverified offer to buy used furniture.
- **An opening's ceiling is not 30.** Below the coverage floor
  `calculate_weighted_score` stops renormalising, so 11 of the 20 real openings
  top out at 9.6/30 however well written. `attainable_weighted_score` computes
  it from the frozen scorer; every score is published beside its ceiling and no
  level is averaged across ceilings. `tj-vz7o.10.2`.
- **A condition on the world is a guard; a condition on what Noor thinks she did
  is a leak**, since she is both actor and judge. Four rules died on their own
  escape clauses; five tests hold them out. `tj-2m5m.8`.
- **The prompt carries the business's goal**: understand the need and quote fast,
  plus JTBD, SNAP and four facts. `docs/Research/`.
- **Owner, 2026-08-08: generation stays varied.** Not temperature 0; the price
  is k runs a side, within-scenario sd about 1.7.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down on a signed
  opening; rule 11 needs a two-family order. `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **This model follows an instruction and loses a prohibition** -- owner,
  2026-08-10. Rule 11 was a permission wrapped in two bans and scored 0.00; it
  now states the act, the consultative directive holds no "never" at all, and a
  test keeps it so. Real constraints live once, in grounding. 37 -> 28 of 238.
- **24.0 is retired and the rubric is frozen.** Five changes in one week, all
  raising it, so nothing before 2026-08-09 compares. `tj-07bs`.
- **The widening is not what `tj-2m5m.4` was filed as.** Rule 9 is 1.51/2 on 85%
  of reads against the 0.40 filed; rule 10 is 0.88 on 29%, third. Production
  runs `8b75888` (2026-08-09, readback matched, health ok).
- **The round moved nothing in aggregate, and that is the finding.** At
  `8b75888`: project **20.02 +/- 1.00** against 19.95, transactional **21.16
  +/- 3.49** against 20.77 over the same 11 scenarios, both far inside their own
  uncertainty. Reader disagreement **1.58**, the lowest yet.
- **The transactional baseline is 18.94 +/- 3.74 over 7.6 rules, 15 scenarios**,
  including `R06`-`R09`. Never compare with 21.16: that is the eleven only.
- **The realistic shapes are the gap.** `R07` 7.35, `R06` 8.10, `R09` 10.50,
  `R04` 7.95 against `R02` 29.07 at the same 6-8 applicable rules. Good at a
  brief, poor at four words; a real opening has a median of 21 characters.
- **A guarantee that never runs is worth nothing, and one of ours did not.**
  Rule 11's package line appeared in 0 of 53 packets and was deleted rather than
  repaired. Rule 13's guard did fire, on 3 packets, moving it **0.00 -> 0.75**,
  attributable because nothing else touched rule 13. `tj-odeq`.
- **The first turn answers, then asks the name in passing** -- owner decision,
  2026-08-10, `58d9a2f`. Both gates went, engine short-circuit and kernel flow.
  Ask once and let go; `refuse_to_chase_the_name` reads turns we actually sent.
  Three defects it uncovered are fixed there. Parked requests still resume.
- **The first confound is removed.** With no applicability map, all 1590/1590
  criterion reads across the same 53 packets and 19 scenarios were scored. The
  raw result is **18.71 +/- 0.31** on a re-read and **18.71 +/- 1.66** on another
  scenario draw. The paired correction from **13.58** is **+5.13 +/- 0.25** on
  the fixed set and **+5.13 +/- 1.35** on another scenario draw. It moved; this
  is a measurement correction, not a build change. `tj-vz7o.3`.
- **The second confound remains.** Human **6.05 +/- about 0.85** is from 1247
  evaluated dialogues across five manager groups, one at about 67%, read by
  `claude-haiku-4.5`. Do not subtract it from 18.71 until `tj-vz7o.4` bridges the
  judge. `raw_total` is client-facing; `calculate_weighted_score` is build-only.
- **The strongest opening claim is coverage and speed.** Humans replied to
  **8452/9477** customer messages in 1400 dialogues: **89.18%, 84.22%-90.46%**
  over seven manager labels; first reply median **1080 s, 840-1890 s** over
  1223/1358. Noor: **141/141**, **100%**, median **15.61 s, 9.99-21.51 s**; on
  20 real openings median **1.906 s**. `tj-vz7o.6`.
- **The corpus is anti-patterns, not a benchmark**, per the client: 1400
  dialogues, 1247 evaluated by `claude-haiku-4.5`, mean 6.05/30, ~86% of
  outcomes off-channel. At `<git-common-dir>/codex-orchestration/treejar-dialogs-corpus`,
  0700/0600, carrying company names and amounts; no commit hooks exist.
- **`tj-jxv7` closed on live evidence**: `R03` 9.00 -> 20.63, every new run above every old one, against sd 1.34.
- **`S07` 28.13 -> 21.55 and `R05` 28.13 -> 24.40, outside their own spread and
  unexplained.** Ruled out by test: the classifier reclassifies both identically
  and the guard touched neither. A round measures a build, not a diff. `tj-jlx4`.
- **A route answers before it asks, or stands down.** `tj-ja1v`. Lookups are
  read-only and wrapped -- a failure costs the fact, never the turn.
  `DeterministicRoute.carries` is the contract; `ROUTES_THAT_ONLY_ASK` freezes
  the eight that still only ask.
- **The model reads what the customer said; code owns catalog facts.**
  `record_customer_requirements` writes the quoting facts into typed slots, with
  a catalog check on the SKU so a mis-extraction cannot become one. `tj-1osj`.
- **The test was partly wrong, not the bot.** 34% of real openings are a bare
  greeting, median 53 chars against our 126, real median 2 turns. S01-S10 frozen
  with no threshold. `tj-2m5m.10`, `tj-6f4z`.
- **glm-5.2 is the runtime judge on its sd**, 1.3 against deepseek-v4-flash's 3.8; `ai_quality_controls` still names the latter, all scopes `disabled`.
- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`; refuses a verdict
  without repeats. **No movement smaller than its own uncertainty is evidence.**

## Local verification

- 2026-08-10 on `codex/tj-vz7o-corpus-bridge`: Ruff and format over 429 files,
  Mypy over 168 sources, Pytest `3503 passed, 19 skipped`, process verification
  passed. Supersedes earlier figures.

## Active work

- Review children `R-01..R-16`, `R-19`, `R-20`, `tj-ee5f.12`/`.14` closed;
  `.7`, `.8`, `.1` open for release-bound acceptance, `.13` depends on them,
  `.5` blocked on the Wazzup status bug.
- Closed 2026-08-10 under `tj-vz7o`: `.3`, `.6`, `.7`, `.10.1`, `.10.2`, `.11`.
  `.10` reran at `b244711` for $0.180: 20/20, zero critical failures, contract
  met. `.4` authority declined; `.5` dependent. `.8`/`.9` drafted, unsent.
  `.12` holds four reader findings the detector cannot see.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- The product system prompt grew on 2026-08-09 by owner decision; not again
  without one.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- Run `repin_traceability_sources.py` after moving current state, or three
  manifest tests fail on a digest that says nothing about what changed.

## Next recommended

Next stage id: `tj-rt7w-overcomplication`. Owner call, 2026-08-11: audit the
over-complication, then run a fix cycle. Measured audit in
`docs/superpowers/specs/2026-08-11-what-grew-too-big-and-how-we-cut-it-back-spec.md`,
epic `tj-rt7w`, seven children. **Three of the four response exits skip grounding
entirely** (`.5`) -- the structure that let the "UAE delivery with installation"
clause out; nothing bounds what a guard may delete (`.2`); money is parsed by four
regex families (`.3`); the guards are closures in a 1827-line `process_message`
(`.4`, `.6`). Only 41 lines of `engine.py` are dead: every step replaces live code.

Recommended action: `.1`, the unverified used-furniture offer and the one safety
item, then `.2`, `.3`, `.4`, `.5` alone because it changes behaviour, and `.7`,
a paired round expecting **no** score movement. `.6` may be deferred. Also owed:
measure `7c34d55` against baseline **18.94 +/- 3.74** on rules 7, 11, 13.

## Starter prompt for next orchestrator

Use $orchestrator-stage for `tj-rt7w-overcomplication`. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, and the 2026-08-11 over-complication
spec with its six rules. Preserve both rulers, keep corpus text outside Git,
never compare runs across judges, and never let a refactor and a behaviour
change ride in the same measured round.

## Approval gates

No second 20 Luna + 20 GLM round is authorized. `tj-vz7o.4` Haiku authority was
explicitly declined. No authority is granted for further paid calls, push,
deploy, production mutation, model configuration, or real-user messaging.

## Explicit defers

- Nothing built on 2026-08-10 has met a live conversation. Every effect claimed
  for the name-gate removal and the reworded directives is a headroom estimate
  until a deploy and a repeated run.
- `tj-i653`: the parked-request machinery, about 500 lines, stays reachable
  until no live conversation carries `name_gate_pending_request`.
- `tj-swgu` has no stage scaffold: `.codex/stages/tj-swgu/` does not exist.
  Whoever closes it must scaffold that separate stream first.
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
