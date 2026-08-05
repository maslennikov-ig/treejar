# Orchestrator Handoff

Updated: 2026-08-05
Current branch: `codex/tj-feet`
Current stage id: `tj-feet`
Status: stage `tj-feet` implementation complete; all ten planned children are
closed, four measured follow-ups are recorded, and the stage stops before
production acceptance on the newly switched model

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

- `.7` catalog/materializer: original 759 focused tests; integrated correction
  set 823 passed; targeted Ruff/format/Mypy passed.
- `.8` dialogue/quotation: 803 focused tests; targeted Ruff/format/Mypy passed.
- `.12` evaluator/reporting: 99 focused tests; diff check passed.
- `.14` model-battle harness: 113 focused tests; scoped Ruff/format/diff passed.
- Independent bounded correction re-review: APPROVE; 34 passed, 841 deselected.
- Combined tree: Ruff lint passed; Ruff format reports 327 files formatted;
  Mypy passed over 165 source files; canonical process verification passed
  after the final documentation refresh.
- Full combined Pytest produced `2776 passed, 19 skipped, 3 failed`; all three
  failures were traceability `runtime-truth` digest drift caused by the handoff
  rewrite. After the final digest refresh, the exact three failed manifest tests
  passed.
- Full format initially found only `src/quality/schemas.py`; it was mechanically
  reformatted. The current full format check passes.

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

Local remediation and documentation closeout are complete. Stop here; the next
work is the separately authorized paid model battle.

Next stage id: `tj-ee5f`

Recommended action: keep the stage open for the separately authorized paid
model battle. After a sealed winner decision, request separate authority for
model configuration, push, deploy, and winner-only production acceptance. Do
not fold the bounded product-runtime `R-17` defer into the paid run.

## Stage tj-feet

Grounding, tool obedience and evaluation repair. Branch `codex/tj-feet`, based
on `codex/tj-ee5f-quality-model-battle` at `ea35d44`. All ten planned children
are closed. Full detail, every number and the four follow-ups are in
`.codex/stages/tj-feet/summary.md` and the reports it names.

- The customer-visible change: the assistant no longer offers the quotation tool
  after an explicit decline and restores it only on a new explicit request; an
  asserted product attribute must name a field path present on the row actually
  retrieved; an unknown attribute produces a useful partial answer rather than a
  refusal; seating capacity may be offered only as a marked assumption with a
  confirming question, and a stated headcount now gets that assumption instead
  of a decline.
- `.6` paired re-score: false refusals `0.200` to `0.000`, task completion
  `0.767` to `1.000`, persuasion `2.548` to `3.071`, next step `3.429` to
  `3.667`, with unsupported facts `0.000` and control compliance `1.000` in
  both rounds. The published `tj-feet.5` persuasion figure is not comparable
  with these: the responses did not change, the judge's calibration did, so
  both rounds were re-scored together and only that pairing is valid.
- `.9` not adopted, a recorded negative the criterion allows. `.10` implemented
  and shipped switched off behind one `system_configs` row
  `claim_contract_scope`; nothing moves until the owner sets it.
- A live defect was found by the `.10` measurement and fixed: literal
  containment withheld a stored price quoted as `AED 800` against `800.00`, on
  16 of 37 measured turns, and a stock count on 10. That comparison is shared
  with the shipped narrow repair path.
- Runtime main model switched to `openai/gpt-5.6-luna` under explicit owner
  authority; one row in production `system_configs`, no deploy or restart, read
  back through the deployed runtime. `tj-ee5f.15` closed. Production S01-S10
  acceptance on the new model has NOT been run and stays with `tj-ee5f.1`.
- The 2026-08-05 catalog audit found no seating-capacity field on any of 344
  active SKUs and no Arabic catalog text at all. `tj-2pkk` now has the evidence
  it has been blocked on since 2026-06-16.
- Sealed rounds of 2026-08-04 and 2026-08-05 are superseded, immutable, and not
  comparable with anything scored under `noor-claim-rubric/v1`.
- Local acceptance on the combined tree at stage close: Ruff, format over 334
  files, Mypy over 166 source files, and Pytest `3035 passed, 19 skipped`.
- Total provider spend for the whole stage `$0.0663`, against a `$4.00`
  reservation. The judge was the orchestrator session throughout and cost
  nothing, which is why the specification's dollar-scale figure was two orders
  of magnitude high.

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

- `tj-feet.13` (P1), `.12`, `.14`: three gaps in the claim contract, each found
  by measurement on 2026-08-05 and each blocking the widened `tj-feet.10` scope.
  `.13` also affects the shipped narrow repair path.
- `tj-feet.11`: `.codex/stages/tj-ee5f/traceability-manifest.json` pins
  whole-file digests of `.codex/orchestrator.toml` and `.codex/handoff.md`,
  which the repository contract declares to be current state. Any stage that
  updates either breaks three manifest tests. `tj-feet` re-pinned them twice to
  keep the gate green; the design question belongs to the `tj-ee5f` stream.
- `tj-feet.10`, enabling it: the switch exists and is measured. Turning it on is
  the owner's call and should wait for `.12`, `.13` and `.14`. Option (b) from
  the task design, a structured main output that removes the second call, was
  not built and is now the more attractive of the two.
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
