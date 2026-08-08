# Orchestrator Handoff

Updated: 2026-08-08
Current branch: `main`
Current stage id: `tj-4e5j`
Status: epic `tj-4e5j` is complete and locally green. Epic `tj-swgu` still has
its release-bound production re-run outstanding, which needs authority that is
not granted.

## Current truth

- **Production is not on Supabase.** Project `vlxgzhbtnwysaqonvlte` is INACTIVE,
  which is why DNS, the pooler, REST and the MCP failed at once and looked like a
  network fault. Production is Postgres in the `noor-db-1` container on
  `noor-server` (ssh config entry), reached as `db:5432` over the compose
  network, so no laptop-reachable URL exists. `.env.noor` and the dead `supabase`
  MCP server were removed 2026-08-08.
- **No real customer has ever written Russian.** Counted 2026-08-08 in
  production: of 69 real-phone conversations **0** carry Cyrillic and 6 Arabic;
  all 28 Cyrillic messages in the 435 total are our own harness. 0 of 69 puts the
  95% ceiling near 4.3% -- "no evidence", not "impossible". `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes, and that is load-bearing.**
  7 of 920 SKUs begin with Cyrillic `СН`; 132 names use Cyrillic `х` as the
  dimension separator. The homoglyph maps in `src/llm/engine.py` and
  `src/dialogue/catalog_refs.py` are what let a customer typing Latin `CH 135`
  reach SKU `СН 135`; `tests/test_catalog_homoglyphs.py` guards it.
- **The main model is Luna, and all three layers now say so.** `system_configs`,
  `src/core/config.py` and the production `.env` all name `openai/gpt-5.6-luna`
  as of 2026-08-08. For three days only the database row did, while the source
  said `z-ai/glm-5.2` -- shadowed, so nothing misbehaved and everyone was misled.
  `tj-uidf`.
- **Two judges, do not confuse them.** Acceptance measurement is a blind Claude
  reader panel, never a paid model; an external judge belongs only to the runtime
  `ai_quality_controls` feature. Compare within one instrument only -- two
  judges, or two differently-prompted panels, share no noise estimate.
- **Acceptance stands at 15.4; the gap to 24.0 is 8.6.** Measured on `a830001`
  2026-08-08: S01-S08 three times each, S09/S10 once, 52 blind scorings. Paired
  against the corrected `5656c82` baseline of 13.4 the delta is **+1.95 +/- 1.58**
  -- real, but thinner than it looks, because this panel disagreed with itself by
  a mean of 2.86 points against the previous panel's sd 0.9, probably from
  scoring 26 packets each instead of 10. Generation noise, finally measured, is
  the smaller one: within-scenario sd **0.84** over three runs.
  `docs/reports/2026-08-08-the-first-run-that-saw-the-directives.md`.
- **Rules 6, 7 and 13 did not move on a live run.** Rule 13 is 0.00 across all 22
  applicable scorings and rule 7 is 0.08 of 2, unchanged from before the
  directive that names all three in plain English. Something drops the
  instruction before the reply or loses it against a competing one; S08's
  bulleted echo survives its own directive the same way. Next investigation,
  and it now has evidence. Rule 11 broke zero for the first time in 70+ scorings
  (0.33) and rule 15 doubled (0.50), so the mechanism works when it lands.
- **`6a14f2f` and `5656c82` tie; the deltas inside them (S05 +3.2, S07 -3.3) came
  from one generation per side and are not evidence. `tj-2m5m.6` is P2.**
  `docs/reports/2026-08-08-did-the-build-regress.md`.
- **Owner decision 2026-08-08: generation stays varied.** `PATH_CORE_CHAT` is
  not pinned to temperature 0 -- a bot that always writes the same sentence stops
  selling, and each customer sees one conversation anyway. The price is k runs
  per scenario per side, measured at a within-scenario sd of 0.84.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down when the
  customer signs their opening message; rule 11 needs a two-family order, not any
  catalog turn; a new always-on directive forbids a reply that only restates the
  customer or states intent, and makes Noor perform the next step her tools can
  do; the consultative opening now also carries rules 9, 10 and a verified
  package -- never a discount. `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **Production runs `a830001` as of 2026-08-08.** Owner-authorised push, deploy
  and acceptance run; CI green, `/opt/noor/.release-sha` reads back `a830001`,
  health ok. Both authorities are spent and closed again.
- **`tj-r1vk` is closed.** S09 and S10 need the real protected chat, so the
  runner now calls the product's own reset before each: the old conversation is
  renamed `#archived-`, closed and its escalations resolved, a fresh one opens,
  nothing is deleted. Verified over all 26 transcripts of the run.
- **No figure published 2026-08-07 was real**: normalised twice by `808b07d`
  plus a manual 30/24, so 18.0/18.5/18.2 were 15.8/16.1/16.1, from a judge
  reading four points generous at sd 3.8. `tj-swgu.13`, closed.
- **The rule.** No movement smaller than its own uncertainty is evidence.
- **glm-5.2 adopted for the runtime judge, on its sd**: k=5 on the stored
  `5656c82` transcripts, sd 1.3 and mean 11.2 +/- 0.4 against incumbent
  deepseek-v4-flash's 3.8. Cost argues the other way ($0.0114 against $0.0045
  per evaluation); the argument is independence, since Luna writes the replies
  and a judge sharing its model is measuring itself. See the glm52 report.
- **`ai_quality_controls` names `deepseek/deepseek-v4-flash`** in production, all
  three scopes `disabled`, moved off the delisted `xiaomi/mimo-v2-flash` on
  2026-08-08. Pointing the row at glm-5.2 and enabling `bot_qa` is a separate,
  unrequested change.
- Instrument: `scripts/e2e_acceptance/score_uncertainty.py`, 22 tests. Reads either
  score-file shape onto one /30 axis, states the interval its repeats justify, and
  refuses a verdict without repeats.

## Local verification

- 2026-08-08 at `a830001`: Ruff and format over 347 files, Mypy over 167 sources,
  Pytest `3336 passed, 19 skipped`, `run_process_verification.sh` OK, and the
  same gates green in CI before the deploy. Supersedes earlier figures.

## Active work

- Review children `R-01..R-16`, `R-19`, `R-20`, `tj-ee5f.12` and `.14` are
  closed; `.7` and `.8` stay open only for their release-bound acceptance.
- `tj-ee5f.13`: future paid isolated core/background comparison; depends on
  `.7`, `.8`, `.12`, and `.14`. `.1`: later winner-only release-bound
  acceptance. `.5`: blocked on the provider-confirmed Wazzup status bug.

Accepted design and executable plan, in `docs/superpowers/`:
`specs|plans/2026-08-07-model-written-prose-over-verified-facts*` and
`specs|plans/2026-08-03-noor-e2e-remediation-and-model-comparison*`.

## Constraints

- Preserve exact scenario wording in fixtures/protected evidence only.
- Do not grow the product system prompt; the local change reduced it.
- Public REST/webhook contracts and the database schema remain unchanged.
- Preserve unrelated work and untracked user files.
- The local fixes are not production acceptance; the failed S01-S10 evidence
  stays immutable until a new authorized release-bound pass exists.

## Next recommended

Next stage id: `tj-ee5f`

The paid comparison has since run under `tj-feet.8` and the main model was
switched, so the battle this section used to point at is done.

Recommended action: epic `tj-2m5m`, and the next question is no longer what to
write but **why written directives do not reach the reply**. Rules 6, 7 and 13
are flat after a live run, and S08's echo survives a directive aimed at it,
while rules 11 and 15 moved. Find the difference between the two groups before
writing another word of prompt. Second: the panel needs its precision back --
2.86 mean reader disagreement over 26 packets each is not a usable instrument;
split the load. `tj-ee5f.1` is the same production pass seen from the older
stage; do not fold the bounded product-runtime `R-17` defer into either.

## Stage tj-feet

Closed 2026-08-06. Capacity-as-marked-assumption, the `gpt-5.6-luna` switch and
`tj-feet.10` staying off are all in `.codex/stages/tj-feet/summary.md`. One
decision is live policy and is recorded nowhere else:

- **Owner decision 2026-08-06: a spoiled reply is worse than a model error.**
  The claim contract blocks only what a retrieved row *refutes*; what it cannot
  confirm ships and lands in `ContractResult.unverified`, logged every turn.
  This reverses the original `tj-feet.3` criterion, so an invented attribute the
  catalog is silent about reaches the customer. Turns rewritten fell to `4/42`,
  all four the capacity rule.
  `docs/reports/2026-08-06-claim-contract-gaps-closed.md`.

Run `scripts/orchestration/repin_traceability_sources.py` after moving current
state.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` stage. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, the stage summary and manifest, the
accepted remediation artifacts, the model-comparison specification, and Beads
`.1`, `.5`, `.7`, `.8`, `.13`, `.13.9`, and `.14`. Preserve frozen
`AC-01..AC-30`. A challenger decision does not authorize a model-config change,
and the free exact-provider metadata preflight does not authorize the paid
battle behind it.

## Approval gates

Push and deploy were granted once on 2026-08-08 and spent on `a830001`; they are
closed again. No authority is currently granted for paid OpenRouter calls, model
configuration changes, push, deploy, further staging/production mutation,
test-only business effects, or real-user messaging. An acceptance run against
the deployed runtime is live traffic and needs its own grant.

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
  in the same frozen registry, so a one-line addition breaks three manifest
  tests and needs a deliberate re-pin of another stream's provenance.
- `tj-feet.10` stays off. The owner approved enabling it conditional on the
  confirming round backing the projection; the round measured `12/42` turns
  rewritten against a projected `1/37`, so the condition was not met. Option
  (b), a structured main output removing the second call, is still unbuilt and
  still the more attractive of the two.
- `codex/tj-feet` and `codex/tj-ee5f-quality-model-battle` both edit
  `.codex/handoff.md`; the other stream's edits are uncommitted in its own
  worktree and will need reconciling at merge.
- `tj-ee5f.13.9` / product-runtime `R-17`: validate and centralize model ids,
  reasoning capabilities, and cache-control support in `src/core/config.py` and
  `src/llm/safety.py`. Separate from `.14`, which must not be read as implying it.
- `tj-ee5f.5`: after Wazzup announces its fix, run one bounded protected
  `sent -> delivered -> read` proof.
- S09 and S10 ran once, not three times: repeating them multiplies real business
  effects (a PDF to the test chat, a CRM opportunity) nobody has authorised.
- Existing raw production/model evidence stays protected outside Git, and
  repository-history privacy cleanup is a separate destructive decision.
