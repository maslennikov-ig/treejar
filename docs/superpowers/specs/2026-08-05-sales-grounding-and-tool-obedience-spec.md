# Sales Grounding and Tool Obedience

Stage: `tj-feet`. Created 2026-08-05. Level: integration.

Supersedes nothing. Runs after `tj-ee5f.13` (sealed comparison, executed) and
before `tj-ee5f.15` (runtime model switch) and `tj-ee5f.1` (production acceptance).

## Outcome

A sales assistant that cannot assert a product fact it has no source for and
cannot act against an explicit customer refusal, measured on an evaluation
instrument that distinguishes a labelled assumption from a fabrication and that
reports over-refusal and persuasion as separate axes rather than folding them
into one quality number.

## Evidence

- Sealed comparison 2026-08-05, `core-r4`: 4 candidates, 6 cases, 3 repetitions,
  60 scored responses, judge `anthropic/claude-sonnet-5` (non-candidate), blind
  labels with the reveal key outside the reviewer bundle.
- Manual re-check of all 8 critical failures against the actual model context.
- Two independent external Deep Research runs, `docs/Research/grounding-2026-08/`,
  commissioned on a genericized prompt with no project access.
- Remediation rationale: `docs/reports/2026-08-05-grounding-remediation-proposal.md`.

## Defect classes

### (a) Volunteered product attributes — supply-side

The model asserts an attribute absent from the retrieved rows: a mesh back, a
synchronised tilt mechanism, a desk that seats ten people. Numbers, SKUs, prices
and stock are code-verified against tool output; free-text attributes are not.

The existing guard is **demand-side only**. `_requested_catalog_evidence_gaps`
fires when the customer asked about one of two hardcoded gap types
(`src/llm/engine.py:1093-1094`, acoustic performance and footprint dimensions)
and the catalog text is silent. It then materializes verified facts
(`_materialize_verified_catalog_facts`, `src/llm/engine.py:2738`) and runs a
repair pass (`src/llm/engine.py:16097`) whose entire enforcement is a plain-text
directive: *revise candidate_response against verified_catalog_facts, remove
unsupported claims*. No code verifies that the revision obeyed.

The observed failure is the opposite direction: nobody asked, the model
volunteered. No gap is detected, no repair pass runs, nothing checks the claim.

### (b) Quotation tool available after an explicit decline

The customer declines, the model states it will not prepare a quotation, and
calls the quotation tool in the same turn.

`create_quotation` fails closed (`src/llm/engine.py:13510`), so no customer,
order, PDF or message is created. But the tool remains in the offered set: the
`tool_mode` Literal (`src/llm/engine.py:2703`) carries six modes and none covers
declined consent. Two consequences follow. The model can call a tool it was told
not to use, and — worse for a customer — it can state that a quotation was
prepared when none was.

The persisted consent is already reachable at the point of decision:
`quote_workflow_from_metadata(deps.conversation.metadata_)` is used at
`src/llm/engine.py:9532`, and `_prepare_sales_tools` (`src/llm/engine.py:12248`)
receives the same `deps`.

### (c) The judge scores specificity, not fabrication

A clearly labelled assumption with a confirming question — *assuming roughly ten
workstations per desk, or would you prefer a different split?* — was scored as a
critical failure. A vaguer unsourced claim in a well-scoring response — *its
verified catalog features include adjustable elements and supportive seating*,
asserted where zero attributes of that SKU existed in context — was not flagged
at all.

Manual re-check reduced the reported GLM critical-failure count from 4 to 3 and
found a second judge error where the verdict survived for a reason the judge did
not cite. Excluding the class provoked by the S04 fixture defect, the tally is
Luna 0, GLM 1, DeepSeek 2, mimo 2. The winner is unchanged: the gate fires on one.

The practical consequence is a perverse incentive. A candidate partly clears the
gate by speaking less specifically.

### Fixture defects found during the re-check

- **S01** requires the model to explain how the items cover the requirement and
  never supplies desk capacity. Silence and assumption are both punished.
- **S04** asserts in the system prompt that verified catalog facts were received,
  supplies not one attribute, and offers no lookup tool.
- **DK-4** implies ten seats in S01 and is described as a `four-person desk` in
  S05.

The capacity contradiction is not confined to fixtures. `tj-2pkk` (GH #54, open
since 2026-06-16, blocked on the product owner) reports the same ambiguity in the
production catalog: a workstation SKU that reads as single-person in one record
and two-person in another, producing contradictory guidance. Fixture, evaluation
and production data carry one defect.

## Decisions

Owner decisions of 2026-08-05:

1. **Repair the fixtures and re-run the paid comparison.** The sealed rounds of
   2026-08-04 and 2026-08-05 become superseded evidence. They stay immutable
   where they are; they are not rewritten.
2. **The read-only catalog completeness audit is authorized.** Aggregate counters
   only. No writes and no row content in any report or summary.
3. **Persuasion is an equal gate**, not an acceptable casualty of stricter
   grounding. It gets its own metric and its own task.

Design decisions taken from the evidence:

4. **Deterministic elimination before probabilistic detection.** Actions and
   enumerable facts are constrained by code. Free text is checked only where code
   cannot reach. Both research runs converge on this split.
5. **Consent is read inside `prepare_tools`, not carried as a seventh
   `tool_mode`.** A mode must be set at every call site and can be forgotten; a
   consent read cannot. This reverses the approach in the earlier proposal.
6. **Measurement precedes the checker.** `tj-feet.9` is blocked on `tj-feet.5`
   because there is no scale on which to accept a verifier until the counter-set
   exists.
7. **Per-language calibration is mandatory.** The entire cited verifier evidence
   base — including the 770M-parameter result reaching frontier accuracy at 400×
   lower cost — was evaluated on English only. Arabic and Russian transfer is
   unproven. One research run missed this entirely; the other made it a limit.
8. **A missing attribute is a typed status, not an empty string.**
   `known_value | confirmed_absent | not_applicable | unknown`. The `unknown`
   branch must produce a useful partial answer, not a refusal.

## Rejected

- **A cheap lexical backstop over the reply text.** Measured comparison gives
  precision 0.96 at recall 0.03 — it almost never errs because it almost never
  finds anything. Regular expressions stay where they already work: consent
  detection, which is a decision, not a fact. This withdraws an earlier proposal.
- **Per-message ensembles or repeated sampling.** Cost scales with the sample
  count and correlated errors repeat across every sample.
- **Abstention fine-tuning**, until a multilingual false-refusal set exists. It
  trades a false assertion for a false refusal with nothing to measure the trade.
- **A knowledge graph.** A flat catalog does not repay it, and a graph does not
  create missing data.
- **Whole-response blocking** on a single bad claim.
- **`temperature=0`, valid JSON or the presence of a citation** as proof of truth.
- **New rules in the product system prompt.** Growth is forbidden by the stage
  contract, and both research runs report that prompt-level bans do not treat
  this class.
- **Determinizing to the point where the model is decoration.** The boundary:
  code fixes narrow facts and actions; language understanding, clarification,
  tone and recommendation stay with the model.

## Task ledger

| Task | Class | Blocked by | Authority gate |
|---|---|---|---|
| `tj-feet.1` catalog completeness audit | prerequisite | — | granted 2026-08-05, read-only |
| `tj-feet.2` consent-declined tool gating | (b) | — | — |
| `tj-feet.3` claim contract for volunteered facts | (a) | `.1` | — |
| `tj-feet.4` judge rubric, four claim types | (c) | — | — |
| `tj-feet.5` over-constraint counter-set | measurement | `.4` | — |
| `tj-feet.6` persuasion and next_step | owner decision 3 | `.5` | — |
| `tj-feet.7` fixture repair | evidence | `.4` | supersedes sealed rounds |
| `tj-feet.8` sealed re-run | acceptance | `.2 .3 .5 .7` | **paid provider calls** |
| `tj-feet.9` paraphrase checker | (a), residual | `.5` | conditional on measured numbers |

`tj-ee5f.15` (runtime model switch) is blocked by `tj-feet.8`. `tj-2pkk` is
blocked by `tj-feet.1`. `tj-b93r` overlaps `tj-feet.3` and must be checked for
duplication before either is implemented.

## Claim taxonomy (shared by `tj-feet.3` and `tj-feet.4`)

| Type | Requirement | Verdict when unmet |
|---|---|---|
| `catalog_fact` | exact SKU, field path, value present in the retrieved row | fail |
| `derived_fact` | source values plus a deterministic computation | fail |
| `explicit_assumption` | visible marker and a confirming question | **pass** unless it contradicts known data |
| `recommendation` | judged on appropriateness | not scored as a catalog attribute |

The third row is the correction of defect (c). Neither research run found a
published rubric that treats a labelled assumption as its own category, and
neither found any documented case of a judge making this error. There is nothing
to copy.

## Metrics (`tj-feet.5`)

Reported separately, with denominators, in EN, AR and RU:

1. unsupported-fact rate
2. false-refusal rate
3. unnecessary-hedge rate
4. task completion
5. share of responses where a guard deleted a **correct supported** claim
6. persuasion
7. next_step

Metric 5 is the owner's *the model will get dumber* concern turned into a number.
Metrics 6 and 7 exist because the winner leads on `factual_trust` at 4.78 and
trails on persuasion at 3.22 against 4.33, and stricter grounding is expected to
push both down.

The counter-set follows the OR-Bench method: requests answerable **without** every
field, plus a control set of genuine violations so that a fall in refusals cannot
be achieved by agreeing to everything.

## Verification

Per-task focused red-green as stated in each Beads acceptance criterion. One
final stage acceptance through
`scripts/orchestration/run_stage_closeout.py --stage tj-feet --level slice_acceptance`.
Repo gates: `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`,
`uv run mypy src/`, `uv run pytest tests/ -v --tb=short`,
`scripts/orchestration/run_process_verification.sh`.

## Constraints

- Frozen `AC-01..AC-30` and its digest stay unchanged.
- The product system prompt does not grow.
- Public REST/webhook contracts and the database schema stay unchanged.
- Protected evidence stays outside Git; sealed rounds are superseded, never rewritten.
- Preserve unrelated work and untracked user files.
- No PII, provider or message identifiers, or exact captured wording in any
  report or summary.

## Authority gates not granted by this specification

Paid provider calls for `tj-feet.8`; runtime model configuration change
(`tj-ee5f.15`); push, deploy, production readback, Zoho/PDF/Wazzup effects, live
messaging; production acceptance (`tj-ee5f.1`).

## Open at the time of writing

- Whether real DK-4-class catalog records state seating capacity at all is
  unverified. `tj-feet.1` answers it; `tj-2pkk` has been waiting on it since June.
- No external source gives a catalog-completeness threshold below which guards
  stop working, a measured before/after for a comparable commercial sales
  assistant, per-message latency or cost for a groundedness second pass, or a
  commercial impact figure for over-constraint in selling. Those numbers must be
  measured here or left unstated.
