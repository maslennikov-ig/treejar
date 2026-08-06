# Orchestrator Handoff

Updated: 2026-08-06
Current branch: `codex/tj-feet`
Current stage id: `tj-feet`
Status: stage `tj-feet` complete; all ten planned children and all four measured
follow-ups are closed, and the stage stops before production acceptance on the
newly switched model

## Current truth

- Canonical runtime is `https://noor.starec.ai`; exact last tested release is
  `a2f245cde301457ef19abda221732368986d7f9d`.
- The last S01-S10 production run remains failed evidence: mean **18.4/30**,
  below the required 24.0, with functional failures in S01, S03, S04, S05,
  S08, and S10. No new production proof exists.
- Frozen scope remains `AC-01..AC-30`, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- The local remediation for reviewed findings `R-01` through `R-16`, `R-19`,
  and `R-20` is accepted after focused proof and an independent bounded
  re-review. `R-17` is the only code defer and is bounded below.
- Owner decision for `R-01`: code default
  `dialogue_kernel_mode=enforce`; keep `dialogue_kernel_enforced_flows` empty.
  Typed reconciliation/write-back now runs on the default path while replies
  stay model-owned. No stored runtime configuration was changed.
- Explicit quote refusal persists `declined` and never renders “on hold”. Quote
  detail collection requires canonical `granted` consent; malformed canonical
  state fails closed, while narrowly trusted legacy exact/sales-order quote
  state is canonicalized before adapters.
- Verified catalog facts no longer replace the answer wholesale. They drive a
  model-owned repair pass with separate text provenance. Within one turn a SKU
  exposes one Zoho-confirmed stock number or `unconfirmed`; partial plans retain
  solved families and state an exact uncovered quantity.
- Low evaluator coverage is blocking and cannot publish a normal excellent
  `/30` result. Owner reports show coverage, normalized denominators, and `н/д`
  for inapplicable blocks.
- The isolated harness can return a non-incumbent `winner`: a complete unique
  model/case/repetition matrix is required; sealed judge scores and critical
  gates are applied before durable writes; actual provider cost reconciles a
  full-payload conservative reservation; carry-forward cannot consume an
  unfinished candidate's allowance; non-finite accounting fails closed;
  `TRUNCATED` and `UNSUPPORTED` are machine-readable. Blind permutations use
  cryptographic entropy and keep the `0600` reveal outside the reviewer bundle.
- Product-runtime model-id/reasoning/cache capability cleanup from `R-17` is not
  implemented and must remain a bounded Beads/handoff defer. The harness part
  of `R-17` is implemented.
- No paid or metadata provider request, model configuration mutation, push,
  deploy, production readback, Zoho/PDF/Wazzup effect, or live message occurred
  in this round.

## Local verification

- `tj-ee5f` children at their own close: `.7` 823 passed, `.8` 803, `.12` 99,
  `.14` 113, targeted Ruff/format/Mypy each; independent correction re-review
  APPROVE. That round's combined tree was `2776 passed, 19 skipped, 3 failed`,
  the three being traceability digest drift, green after the refresh. All
  superseded by the stage-close numbers below.

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

Recommended action: keep `tj-ee5f` open for `tj-ee5f.1`, winner-only
release-bound S01-S10 production acceptance on `openai/gpt-5.6-luna`, and
request that authority separately. Do not fold the bounded product-runtime
`R-17` defer into it.

## Stage tj-feet

Grounding, tool obedience and evaluation repair. Branch `codex/tj-feet`, based
on `codex/tj-ee5f-quality-model-battle` at `ea35d44`. All ten planned children
and all four follow-ups are closed. Detail in
`.codex/stages/tj-feet/summary.md` and the reports it names.

- Customer-visible: no quotation tool after an explicit decline until a new
  explicit request; an unknown attribute produces a useful partial answer, never
  a refusal; seating capacity only as a marked assumption with a confirming
  question, which a stated headcount now gets. An asserted attribute is checked
  against the retrieved row but blocked only when refuted — see the reversal.
- `.6` paired re-score: false refusals `0.200` to `0.000`, task completion
  `0.767` to `1.000`, persuasion `2.548` to `3.071`, next step `3.429` to
  `3.667`, unsupported facts `0.000` and control compliance `1.000` in both.
  The published `tj-feet.5` persuasion figure is not comparable: responses did
  not change, the judge's calibration did, so only the re-scored pairing holds.
- `.9` not adopted, a recorded negative. `.10` implemented and shipped off
  behind one `system_configs` row `claim_contract_scope`. A live defect it found
  and fixed: containment withheld a stored price quoted `AED 800` against
  `800.00`, 16 of 37 turns, on the path already shipped.
- Runtime main model switched to `openai/gpt-5.6-luna` under explicit owner
  authority; one row in production `system_configs`, no deploy or restart, read
  back through the deployed runtime. `tj-ee5f.15` closed. Production S01-S10
  acceptance on the new model has NOT been run and stays with `tj-ee5f.1`.
- The 2026-08-05 catalog audit found no seating-capacity field on any of 344
  active SKUs and no Arabic catalog text at all; `tj-2pkk` now has the evidence
  it has been blocked on since 2026-06-16. Sealed rounds of 2026-08-04/05 are
  superseded and not comparable with `noor-claim-rubric/v1`.
- `.12`, `.13`, `.14` closed 2026-08-06. A derivation is verified through its
  inputs with its arithmetic recomputed; an Arabic surface form carries the
  English value it translates; an absence statement is its own claim type
  checked against the row's status; a claim naming the SKU is supported.
- **Owner decision 2026-08-06: a spoiled reply is worse than a model error.**
  The contract now blocks only what a row *refutes*; what it cannot confirm
  ships and lands in `ContractResult.unverified`, logged every turn. This
  reverses the original `tj-feet.3` criterion, so an invented attribute the
  catalog is silent about reaches the customer. Turns rewritten: `30/37` as
  shipped, `12/42` after the gap fixes, **`4/42`** now, all four the capacity
  rule. Confirming round `claimpass-r2`, `$0.0250`, showed the offline replay's
  `1/37` wrong by an order of magnitude. See
  `docs/reports/2026-08-06-claim-contract-gaps-closed.md`.
- `.11` closed with `scripts/orchestration/repin_traceability_sources.py`. Run
  it after moving current state: `--check` reports drift, a plain run re-pins
  `.codex/orchestrator.toml` and `.codex/handoff.md` and revalidates, and it
  refuses every other source so frozen drift still fails loudly.
- Escalation audit 2026-08-06, verified read-only against production. Manager
  alerts **do** reach Telegram: all 15 escalations of the last 30 days were on
  the allowed inbound line. `tj-rkh3`, `tj-oq9x` closed as wrong findings of
  mine; `tj-itbu`, `tj-fwkh`, `tj-zyxz` closed by fixes. An undelivered alert
  now logs `MANAGER NOT NOTIFIED` with a reason; the allowlist takes a list and
  escalation gating fails open, while routine quality alerts stay strict.
- Operational, not code: 10 of 15 escalations sit `pending`, oldest 2026-07-08,
  none assigned, `manager_reviews` has one row all time. Managers reply in
  WhatsApp, invisible to the bot's database, so whether those customers were
  answered cannot be known from here.
- Stage close: Ruff, format over 336 files, Mypy over 166 sources, Pytest
  `3092 passed, 19 skipped`. Provider spend `$0.0913` against `$4.00`.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the active `tj-ee5f` stage. Read `AGENTS.md`,
`.codex/orchestrator.toml`, this handoff, the stage summary and manifest, the
accepted remediation artifacts, the model-comparison specification, and Beads
`.1`, `.5`, `.7`, `.8`, `.13`, `.13.9`, and `.14`. Preserve frozen
`AC-01..AC-30`. Ask separately before any paid OpenRouter call, model-config
change, push, deploy, production readback, external side effect, or live
message.

A later task may run the free exact-provider metadata preflight. It must request
exact current authority before the bounded paid battle. A challenger decision
does not authorize a model-config change. Push, deploy, production readback,
Zoho/PDF/Wazzup actions, and live messages remain separate authority gates.

## Approval gates

No authority is currently granted for paid OpenRouter calls, model
configuration changes, push, deploy, staging/production mutation or readback,
test-only business effects, or real-user messaging.

## Explicit defers

- Registering `repin_traceability_sources.py` in the `AGENTS.md` Operational
  State inventory. Tried and reverted: `AGENTS.md` is pinned as `repo-contract`
  in the same frozen registry, so a one-line addition breaks three manifest
  tests and needs a deliberate re-pin of another stream's provenance. Owned by
  `tj-ee5f`, with the design question behind it.
- `tj-feet.10` stays off. The owner approved enabling it conditional on the
  confirming round backing the projection; the round measured `12/42` turns
  still rewritten against a projected `1/37`, so the condition was not met and
  the switch was not touched. Option (b), a structured main output removing the
  second call, was not built and is still the more attractive of the two.
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
