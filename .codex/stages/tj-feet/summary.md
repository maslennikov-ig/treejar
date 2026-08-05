# Stage tj-feet Summary

Updated: 2026-08-05
Status: in progress; `tj-feet.8` executed and closed, stopped before the
owner-owned model decision
Branch: `codex/tj-feet`, worktree `.worktrees/tj-feet`
Base: `codex/tj-ee5f-quality-model-battle` at `ea35d44`
Head: see git log; the re-run evidence is protected and outside Git

## Boundary

A sales assistant that cannot assert a product fact it has no source for and
cannot act against an explicit customer refusal, measured on an instrument that
tells a labelled assumption from a fabrication and reports over-refusal and
persuasion as their own axes.

No runtime model configuration, public REST/webhook contract, database schema,
frozen `AC-01..AC-30` text or digest was changed. The product system prompt did
not grow: the claim contract lives in per-turn runtime directives. No push,
deploy, production mutation, Zoho/PDF/Wazzup effect or live message occurred.

## Base provenance

The specification's exact source locations and the sealed round it analyses
resolve only against `codex/tj-ee5f-quality-model-battle` at `ea35d44` **plus
that worktree's uncommitted state**. Local `main` is 90 commits behind
`origin/main`, and `origin/main` is 19 behind that branch, so neither could
carry this work.

Commit `94c29e6` imports the harness, the judge script and the stage documents
verbatim from that worktree and records what was deliberately not imported: the
tj-ee5f stream's own `.codex` state and its 2026-08-03 spec/plan edits. The
source worktree's files were left untouched. A future merge will have to
reconcile `.codex/handoff.md`, which that stream is editing in parallel.

## Delivered

| task | outcome | commit |
|---|---|---|
| `tj-feet.1` | catalog completeness audit, read-only against production | `c5a4104` |
| `tj-feet.2` | quotation tool withdrawn while consent is declined | `186ac66` |
| `tj-feet.4` | claim rubric, four types, three separate graders | `3083b74` |
| `tj-feet.7` | fixture traps repaired, superseded rounds recorded | `9746a25` |
| `tj-feet.3` | volunteered claims verified against the retrieved row | `8d0bdb7` |
| `tj-feet.5` | counter-set and seven metrics built; measurement pending | `57e065d` |
| `tj-feet.8` | sealed re-run executed; winner named | `89ffff7` |

## What the audit changed

`tj-feet.1` measured the live catalog and overturned a load-bearing assumption.
344 active SKUs. English is well populated — 99.7% carry a description, 76.5% at
least one feature, 59.0% at least one specification. Arabic carries nothing:
0 of 344 have `name_ar` or `description_ar`, so every Arabic reply was already
grounded in an English row.

Seating capacity is not a catalog field on any SKU. The value the model is shown
as an authoritative price basis is parsed from free text by a regular
expression, and of the 28 SKUs whose description states a capacity token, 25
state two different numbers. That is the evidence `tj-2pkk` has been blocked on
since 2026-06-16, and it is why `tj-feet.3` could not require the field as its
design assumed.

Owner decision of 2026-08-05: capacity may be stated only as a visible
assumption carrying a confirming question, never as a fact.

## Owner decisions taken during the stage

1. The read-only production catalog aggregate was authorized and run.
2. The judge is the orchestrator session, not a paid provider call. Provider
   spend is reserved for candidate models.
3. Capacity is an explicit assumption only.
4. Russian is dropped. The counter-set is English and Arabic.
5. The full counter-set run happens after the model is chosen, so `tj-feet.5`
   ships as the instrument and the scale, not the measurement.

Decision 5 reverses the specification's ordering, in which `tj-feet.5` blocked
`tj-feet.8`. The Beads dependency was updated to match.

## Acceptance evidence

Run once, at this boundary, on the combined tree:

- `uv run ruff check src/ tests/` — passed
- `uv run ruff format --check src/ tests/` — 331 files already formatted
- `uv run mypy src/` — no issues in 166 source files
- `uv run pytest tests/ -v --tb=short` — **2923 passed, 19 skipped**
- `scripts/orchestration/run_process_verification.sh` — OK

The seven frontend cases fail in a fresh worktree until `npm ci` runs in
`frontend/admin`; after it they pass. That is environment, not code.

## The sealed re-run

Executed under owner authorization. Rounds `20260805/core-r5` and `bg-r5`.

Core winner **`openai/gpt-5.6-luna`**, the only candidate to finish the matrix
with no critical failure: groundedness 24/24, tool obedience 1.00,
conversational quality 0.867. Background winner `deepseek/deepseek-v4-flash`, a
practical tie with what production already runs.

The perverse incentive the specification identified did not decide the round.
The candidate with the highest conversational quality, `z-ai/glm-5.2` at 0.894 —
the model production runs in the main slot today — has the worst groundedness at
0.83 and four of the seven critical failures.

All seven critical failures were read by hand against the actual model context,
and so were all 18 winner responses. Actual spend **$0.0335** against the $4.00
reservation; the published estimate was $0.04. Detail in
`docs/reports/2026-08-05-sealed-rerun-result.md`.

## Open, with reasons

- `tj-feet.5` — instrument built and tested; the seven metrics have no numbers
  yet because the generation run waits on the chosen model.
- `tj-feet.6` — persuasion and next_step work has nothing to improve against
  until `tj-feet.5` produces a baseline.
- `tj-feet.9` — the paraphrase checker must not start before that scale exists.
- `tj-feet.10` — new. The claim contract runs on the requested-gap repair
  trigger only; extending it to every catalog turn costs either an extra model
  call per turn or a structured main output, and needs an owner decision.

## Not comparable

Scores produced under `noor-claim-rubric/v1` are not comparable with the
superseded rounds of 2026-08-04 and 2026-08-05 and must never be shown beside
them without that statement. Different fixtures, different rubric, three axes
where there was one blended number. The superseded rounds stay immutable where
they are; `docs/reports/2026-08-05-superseded-sealed-rounds.md` records why.
