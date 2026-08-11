# Stage tj-rt7w-measured-round

Status: accepted
Base: `main` at `33c8f1f`
Acceptance owner: root orchestrator (Claude)

Documentation: no external/versioned boundary — internal first-party Python and
a repo-local report; no new dependency, no public contract changed.

docs-reviewed: updated — the round's report, the handoff, and `AGENTS.md` now
carry the judge rule and the round's result.
project-index: reviewed-no-change — no module added, moved or renamed.
graph-reviewed: no-change-needed — Graphify is not initialised.

## Goal

`tj-rt7w.7`. One measured round after the structural work, on the frozen
seed-`20260810` twenty real customer openings, to answer whether the cleanup
changed the product's behaviour. The expected result was no movement.

## What the owner decided, and what it changed

The owner had authorised 20 Luna + 20 GLM calls (about $0.18) and, asked which
shape to run, chose to **drop the paid second reader and be judged only by the
agent**, then asked for that rule to be recorded wherever possible.

So it is a default now rather than a directive.
`scripts/corpus_bridge/real_opening_acceptance.py` judges with the root
orchestrator unless told otherwise: `run` stops after the generation arm and
writes a blind `reading-pack.json`, `ingest-judgment` takes the reading back
through the same scoring, applicability and critical-failure code the paid
reader would have fed, and paying a second reader takes
`preflight --second-reader`. A test holds the default and the flag. The rule is
also in `AGENTS.md`, the handoff, and `bd remember`.

## The round

20 Luna calls, zero judging calls, **$0.004661** against $0.18 authorised.
Scenario digest `2ba7e4fe…`, identical to the stored baseline's.

| | required | observed |
|---|---|---|
| Luna responses | 20/20 | 20/20 |
| Evaluations | 20/20 | 20/20 |
| Correct language | 20/20 | 20/20 |
| Critical failures | zero | **1**, in 1/20 |

Weighted 15.7/30 (95% CI 13.2–17.9); `raw_total` 12.8 (12.2–13.4); time to first
reply 1.598 s median (1.466–1.908). Share of attainable ceiling: **99%** on the
eleven bare-greeting openings, **77%** on the nine richer ones.

**No paired delta is reportable.** The stored baseline was scored by
`z-ai/glm-5.2` and this round by the agent; the project forbids comparing across
judges, and two judges on the same texts differed by 3.8 points systematically.
This round is the baseline for the next.

## The failure, and what it is not

`tj-riim`. On the recruitment opening the reply promises to route the CV to a
team and to call back if shortlisted. Neither is supported and neither is
possible — the same class as the used-furniture promise `tj-rt7w.1` removed, and
invisible to the deterministic detector because every number is grounded.

Not attributable to this epic: nothing in it touches recruitment, and the stored
`8e50dea` reply on that opening was honest. Luna is stochastic and this is one
draw each. It is a live defect regardless.

## What the round was for

- The epic changed no behaviour it did not mean to.
- `tj-rt7w.1` holds **in the live path**, not only in the stored replay: the
  used-furniture opening is now declined and redirected.
- The three out-of-scope `tj-vz7o.12` defects reproduce unchanged, which is what
  a behaviour-preserving refactor should do to them. One new detail: the
  missing-quote defect is inconsistent rather than absent — four openings on the
  same run did quote priced catalog rows.

## Verification

- Ruff, format, Mypy clean; the corpus-bridge, quality and containment sets pass.
- No opening text, company name or amount entered the repository;
  `test_corpus_stays_outside_the_repository.py` passes and the report carries
  `dialog_id`s, integers, and Noor's own sentences only.
- Protected evidence at
  `<git-common-dir>/codex-orchestration/corpus-bridge/tj-rt7w-round-20260811`,
  modes 0700/0600.

## Delivery

One local commit on `main`. No push, PR, merge, deploy, production or staging
mutation, or real-user message. Paid calls: 20, authorised by the owner in this
session, $0.004661 spent of the ~$0.18 authorised.
