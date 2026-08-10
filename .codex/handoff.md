# Orchestrator Handoff

Updated: 2026-08-10
Current branch: `main`
Current stage id: `tj-4e5j`
Status: two builds are committed, green and **unmeasured** -- `7c34d55` (the
name gate removed) and `ffb8a2d` (the client-ruler bridge). The corpus of 1400
human dialogues has arrived and reset the headline. `tj-swgu`'s release-bound
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
- **The prompt carries the business's own goal**: understand the need and quote
  in the shortest time, plus JTBD, SNAP and four facts. `docs/Research/`.
- **Owner decision 2026-08-08: generation stays varied.** Not pinned to
  temperature 0; the price is k runs a side, within-scenario sd about 1.7.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down on a signed
  opening; rule 11 needs a two-family order. `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **This model follows an instruction and loses a prohibition** -- owner,
  2026-08-10. Rule 11 was one permission wrapped in two bans and scored 0.00; it
  now states the act. Six formatting bans duplicated `_format_for_whatsapp`. The
  consultative directive now holds no "never" at all, and a test keeps it that
  way. Real constraints live once, in the grounding policy. 37 -> 28 of 238.
- **24.0 is retired and the rubric is frozen.** Five changes in one week, all
  raising the number, so nothing before 2026-08-09 compares. `score_by_shape.py`
  refuses to print one number. `tj-07bs`.
- **The widening is not what `tj-2m5m.4` was filed as.** Rule 9 is 1.51/2 on 85%
  of reads against the 0.40 it was filed on; rule 10 is 0.88 on 29%, third.
- **Production runs `8b75888`** (2026-08-09, readback matched, health ok).
- **The round moved nothing in aggregate, and that is the finding.** At
  `8b75888`: project **20.02 +/- 1.00** against 19.95, transactional **21.16
  +/- 3.49** against 20.77 over the same 11 scenarios, both deltas far inside
  their own uncertainty. Reader disagreement **1.58**, the lowest yet.
- **The new transactional baseline is 18.94 +/- 3.74 over 7.6 rules across 15
  scenarios**, including `R06`-`R09`. Compare with that, never with 21.16, which
  exists only for the like-for-like eleven.
- **The realistic shapes are the gap, and 2026-08-10 aims at it.** `R07` 7.35,
  `R06` 8.10, `R09` 10.50, `R04` 7.95 against `R02` 29.07, at the same 6-8
  applicable rules. Good at a brief, poor at four words and silence. The corpus
  confirms it with n=687: real openings have a median of 21 characters.
- **A guarantee that never runs is worth nothing, and one of ours did not.**
  Rule 11's package line appeared in 0 of 53 packets and was deleted rather than
  repaired. Rule 13's guard did fire, on 3 packets, moving it **0.00 -> 0.75**,
  attributable because nothing else touched rule 13. `tj-odeq`.
- **The first turn answers, then asks the name in passing** -- owner decision,
  2026-08-10, `58d9a2f`. Both gates went, the engine short-circuit and the
  kernel's flow. Ask once and let it go; `refuse_to_chase_the_name` holds that on
  turns we actually sent. Three defects it uncovered are fixed in the same commit
  and named there. Parked requests still resume. `tj-0ai0`, `tj-i653`.
- **Two rulers exist and they are not interchangeable.** We drop the rules that
  did not apply and renormalise to /30; the client scores all fifteen and lets
  an unearned one stand at zero. Our 20.02 and their 6.05 were never the same
  measurement. On theirs the same 53 packets read **13.58 +/- 1.11** against a
  human **6.05**, so 2.2x rather than 3.3x. `raw_total` is the only place that
  arithmetic happens. `tj-vz7o`.
- **The claim is about openings, not selling.** Rules 12, 14 and 15 were
  applicable in **2 reads of 106**: our scenarios never reach the conversion
  phase. +8.57 of the +7.50 gap sits in criteria 1-9 and the bot is -1.26 across
  the conversion criteria. And 87.2% of the corpus carries a WhatsApp
  auto-responder -- with it humans mean 6.40, without it 3.65 -- which scores
  **0.76** on collecting contacts against our **0.02**.
- **The corpus is anti-patterns, not a benchmark**, in the client's own words:
  1400 dialogues, 1247 evaluated by `claude-haiku-4.5`, mean 6.05/30, ~86% of
  outcomes off-channel. At `<git-common-dir>/codex-orchestration/treejar-dialogs-corpus`,
  0700/0600. It carries company names and deal amounts; no commit hooks exist.
- **`tj-jxv7` closed on live evidence**: `R03` 9.00 -> 20.63, every new run above every old one, against within-scenario sd 1.34.
- **`S07` 28.13 -> 21.55 and `R05` 28.13 -> 24.40, outside their own spread and
  unexplained.** Ruled out by test: the classifier reclassifies both identically
  and the guard touched neither. A round measures a build, not a diff. `tj-jlx4`.
- **A route answers before it asks, or it stands down.** `tj-ja1v`. Lookups are
  read-only and wrapped -- a failure costs the fact, never the turn.
  `DeterministicRoute.carries` is the contract, `ROUTES_THAT_ONLY_ASK` names the
  eight that still only ask so a new one cannot join silently.
- **The model reads what the customer said; code owns catalog facts.**
  `record_customer_requirements` writes the quoting facts into typed slots, with
  a catalog check on the SKU so a mis-extraction cannot become one. `tj-1osj`.
- **The test was partly wrong, and not the bot's fault.** 34% of real openings
  are a bare greeting, median 53 chars against our 126, real median 2 customer
  turns. S01-S10 frozen with no threshold. `tj-2m5m.10`, `tj-6f4z`.
- **glm-5.2 is the runtime judge on its sd**, 1.3 against deepseek-v4-flash's
  3.8. `ai_quality_controls` still names the latter, all scopes `disabled`.
- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`; refuses a verdict
  without repeats. **No movement smaller than its own uncertainty is evidence.**

## Local verification

- 2026-08-10 at `ffb8a2d`: Ruff and format over 421 files, Mypy over 168
  sources, Pytest `3441 passed, 19 skipped`, `run_process_verification.sh` OK.
  Supersedes earlier figures.

## Active work

- Review children `R-01..R-16`, `R-19`, `R-20`, `tj-ee5f.12`/`.14` closed;
  `.7`, `.8`, `.1` open for release-bound acceptance, `.13` depends on them,
  `.5` blocked on the Wazzup status bug.
- Closed 2026-08-09: `tj-swgu.11`, `tj-swgu.12`, `tj-2m5m.10`, `tj-jxv7`,
  `tj-ja1v`. Closed 2026-08-10: `tj-2m5m.9`. In progress: `tj-0ai0`, built and
  awaiting a measured round. Open: `tj-6tx6` (half fixed), `tj-odeq`, `tj-jlx4`,
  `tj-wvo4` (superseded as engineering by `tj-vz7o.8`), `tj-i653`. New epic
  `tj-vz7o`, seven open children; `.1` and `.2` closed in `ffb8a2d`.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- The product system prompt grew on 2026-08-09 by owner decision; not again
  without one.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- Run `repin_traceability_sources.py` after moving current state, or three
  manifest tests fail on a digest that says nothing about what changed.

## Next recommended

Next stage id: `tj-ee5f`. The work is specified and queued:
`docs/superpowers/specs/2026-08-10-the-clients-ruler-and-the-corpus-bridge-spec.md`,
with the handoff prompt at
`docs/superpowers/prompts/2026-08-10-corpus-bridge-orchestrator-handoff.md`.
What the last round measured: `docs/reports/2026-08-09-the-measured-round-at-8b75888.md`.

Recommended action: **`tj-vz7o.3` first** -- re-read the 53 stored packets with
no applicability map. 13.58 is a lower bound until that exists, because the
reads behind it were told which rules to skip. Then `tj-vz7o.4`, the client's
judge over our packets, which is the only arm with no extrapolation and the one
thing that needs authority.

Still owed and unrelated to the corpus: **measure `7c34d55`** against the
15-scenario baseline **18.94 +/- 3.74**, reading rules 7, 11 and 13 per-rule.
Then `tj-jlx4`, two scenarios outside their own spread with nothing in the diff
to explain it.

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
`8b75888`, and are closed. `7c34d55` and `ffb8a2d` are committed locally and
need a fresh grant to reach production. `tj-vz7o.4` needs its own grant: 53 paid
`claude-haiku-4.5` calls to bridge the judge. No authority is currently granted for paid OpenRouter
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
