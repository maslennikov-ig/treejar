# Orchestrator Handoff

Updated: 2026-08-08
Current branch: `main`
Current stage id: `tj-4e5j`
Status: epic `tj-4e5j` is complete and locally green. Epic `tj-swgu` still has
its release-bound production re-run outstanding, which needs authority that is
not granted.

## Current truth

- **Production is not on Supabase.** The project `vlxgzhbtnwysaqonvlte` is
  INACTIVE, which is why DNS, the pooler, REST and the MCP failed at once and
  looked like a network fault. Production is Postgres in the `noor-db-1`
  container on `noor-server` (ssh config entry), reached as `db:5432` over the
  compose network, so no laptop-reachable URL exists. `.env.noor` and the dead
  `supabase` MCP server were removed 2026-08-08.
- **No real customer has ever written Russian.** Counted 2026-08-08 over the
  production database: of 69 real-phone conversations, **0** carry Cyrillic and 6
  carry Arabic; all 28 Cyrillic messages in the 435 total are our own harness.
  0 of 69 puts the 95% ceiling near 4.3%, so the claim is "no evidence", not
  "impossible". `tj-4e5j.2`.
- **The catalogue is written with Cyrillic lookalikes, and that is load-bearing.**
  7 of 920 SKUs begin with Cyrillic `СН`; 132 names use Cyrillic `х` as the
  dimension separator. The homoglyph maps in `src/llm/engine.py` and
  `src/dialogue/catalog_refs.py` are what let a customer typing Latin `CH 135`
  reach SKU `СН 135`; `tests/test_catalog_homoglyphs.py` guards it.
- **The main model is Luna, and all three layers now say so.** `system_configs`,
  `src/core/config.py` and the production `.env` all name `openai/gpt-5.6-luna`
  as of 2026-08-08. For three days only the database row did, while the source
  said `z-ai/glm-5.2` -- shadowed, so nothing misbehaved and every reader was
  misled. `tj-uidf`.
- **Two judges, do not confuse them.** Acceptance measurement is a blind Claude
  reader panel, never a paid model; an external judge belongs only to the runtime
  `ai_quality_controls` feature, which runs unattended. The panel is also the more
  precise instrument: sd **0.9** to glm-5.2's **1.3**. Compare within one
  instrument only -- two judges, or two differently-prompted panels, share no
  noise estimate. Between-panel drift measured 2026-08-08 is about 0.3.
- **Acceptance stands at 13.4; the gap to 24.0 is 10.6.** Two blind readers over
  both stored builds read 12.6 +/- 0.4; correcting rules 3 and 11 below moves
  `5656c82` to 13.4 and `6a14f2f` to 13.6 without a reader changing a judgement.
  Precision, not accuracy: a bias the readers share is invisible to it. Protocol
  in `docs/reports/2026-08-07-repeated-scoring-and-the-second-reader.md`.
- **The build did not regress, and the per-scenario deltas inside it are not
  evidence.** `6a14f2f` and `5656c82` tie. S05 +3.2 and S07 -3.3 were each
  measured from one generation per side, and generation is stochastic by owner
  decision, so both stand as observations only. `tj-2m5m.6` is P2 and blocked on
  `tj-2m5m.7`. `docs/reports/2026-08-08-did-the-build-regress.md`.
- **Owner decision 2026-08-08: generation stays varied.** `PATH_CORE_CHAT` is
  not pinned to temperature 0 -- a bot that always writes the same sentence stops
  selling, and each customer sees one conversation anyway. The price is that
  comparison needs k runs per scenario per side. `8b8635f` ran S05 three times:
  template turn byte-identical, every model-written turn different, turn 4 in the
  error fallback twice of three.
- **Less caution, more selling, 2026-08-08.** Rule 3 stands down when the
  customer signs their opening message; rule 11 needs a two-family order, not any
  catalog turn; a new always-on directive forbids a reply that only restates the
  customer or states intent, and makes Noor perform the next step her tools can
  do; the consultative opening now also carries rules 9, 10 and a verified
  package -- never a discount. The two dialogue-side changes are unmeasured and
  need a deploy. `docs/reports/2026-08-08-less-caution-more-selling.md`.
- **No published figure was ever real.** Every mean published 2026-08-07 was
  normalised twice (`808b07d` moved the /30 into `calculate_weighted_score`; the
  reports kept the manual 30/24 on top), so 18.0/18.5/18.2 were really
  15.8/16.1/16.1 -- from a judge reading four points generous at sd 3.8.
  `tj-swgu.13`, closed.
- **The rule.** No movement smaller than its own uncertainty is evidence about
  code: +/- 3.3 for the old judge, +/- 0.4 here.
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

- `tj-swgu.9`, 2026-08-07: Ruff and format over 411 files, Mypy over 167
  sources, Pytest `3259 passed, 19 skipped`, and
  `scripts/orchestration/run_process_verification.sh` OK. Earlier per-stage and
  per-child figures are superseded by this one.

## Active work

- Review children `R-01..R-16`, `R-19`, and `R-20` are closed. `tj-ee5f.12`
  and `.14` are closed; parent `.7` and `.8` remain open only because their
  acceptance also requires a separately authorized release-bound production
  retest.
- `tj-ee5f.13`: future paid isolated core/background comparison; depends on
  `.7`, `.8`, `.12`, and `.14`.
- `tj-ee5f.1`: later winner-only release-bound production acceptance.
- `tj-ee5f.5`: blocked on the provider-confirmed Wazzup terminal-status bug.

Accepted design and executable plan:

- `docs/superpowers/specs/2026-08-07-model-written-prose-over-verified-facts-design.md`
- `docs/superpowers/plans/2026-08-07-model-written-prose-over-verified-facts.md`
- `docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md`
- `docs/superpowers/plans/2026-08-03-noor-e2e-remediation-and-model-comparison.md`

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

Recommended action: epic `tj-2m5m`. `.1`, `.2`, `.4` and `.5` are written and
green; `.3` is now folded into them, since nothing in the working tree has ever
met a live conversation. Everything left needs the same thing: **deploy
authority, then one repeated run** -- k runs per scenario, panel-scored, against
the stored `5656c82` baseline of 13.4. Fix `tj-r1vk` before that run or S09 and
S10 will be scored on a polluted conversation again. `tj-ee5f.1` is the same
production pass seen from the older stage; do not fold the bounded
product-runtime `R-17` defer into either.

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

No authority is currently granted for paid OpenRouter calls, model
configuration changes, push, deploy, staging/production mutation or readback,
test-only business effects, or real-user messaging.

## Explicit defers

- Rule 11 was settled on 2026-08-08: the owner declined a discount, so the
  directive offers a package of verified rows at their combined total instead,
  and the rubric charges the rule only on a two-family order. No directive
  written since `tj-swgu.14` has met a live conversation; every effect claimed
  for them is a headroom estimate until a deploy and a repeated run.
- `tj-swgu` has no stage scaffold: `.codex/stages/tj-swgu/` does not exist and
  `workspace.current_stage_id` is still `tj-feet`, so `check_stage_ready.py` and
  `run_stage_closeout.py` both refuse the stage. Pre-existing, and left alone
  here: creating it means writing another stream's manifest and ledger. Whoever
  closes `tj-swgu` has to scaffold it first.
- Correcting the superseded 18.0/18.5/18.2 figures where they are quoted
  outside this handoff is `tj-swgu.13`, and belongs with `tj-swgu.12`. Sealed
  rounds are superseded, never rewritten.
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
  `src/llm/safety.py`. Harness capability evidence is complete; product-runtime
  cleanup is separate and must not be implied by `.14`.
- `tj-ee5f.5`: after Wazzup announces its fix, run one bounded protected
  `sent -> delivered -> read` proof.
- Paid comparison, model configuration, push, deploy, production readback, and
  winner-only S01-S10 acceptance are future authority boundaries.
- Existing raw production/model evidence remains protected outside Git.
- Repository-history privacy cleanup remains a separate destructive decision.
