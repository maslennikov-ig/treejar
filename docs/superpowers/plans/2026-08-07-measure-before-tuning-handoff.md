# Measure before tuning — handoff for a fresh context

> Written 2026-08-07 at the end of a long session, to be read cold. Everything
> needed to resume is here; nothing else from that session is required.

## Where things stand

Epic `tj-swgu` — "let the model write the sentence where the guard does not
need to" — is implemented. Eight children and three linked bugs are closed. The
production acceptance it was built for **did not pass**, and the reason turned
out to be as much the instrument as the product.

Deployed and pushed: `5656c82`, on `https://noor.starec.ai`, main model
`openai/gpt-5.6-luna`, fast model `deepseek/deepseek-v4-flash`, app 0.4.0,
migration head `2026_06_04_customer_memory`.

## The three things a fresh context must know

**1. The acceptance judge cannot be trusted at one sample.** One unchanged S03
transcript, scored five times with no live traffic and not a byte of
difference: `15.2, 16.2, 21.5, 21.6, 23.9`. Standard deviation 3.8, range 8.7.
So a single scenario carries roughly ±7 at 95% confidence and the ten-scenario
mean carries roughly ±2.3.

Three acceptance runs on materially different builds scored **18.0** (`c977b07`),
**18.5** (`6a14f2f`), **18.2** (`5656c82`). Those are one number, not three.
Per-scenario deltas in the earlier reports were read as evidence about code and
must not be: S03 went 25.4 → 28.9 → 17.6 across three runs on a path nobody
touched.

**2. The model-written rewrite works, and the proof is structural rather than
judged.** Deterministic turns went 15 → 13 → **9 of 29**; scenarios fully
model-written went 2 → 3 → 3 of 10. That count is counted, not scored.
Read it with `uv run python -m scripts.e2e_acceptance.route_provenance <captures>`.

The nine that remain are seven `name-gate` turns (out of scope by the spec), one
catalog fallback and one detail request.

**3. Two facts about the rewrite that were measured, not reasoned, and that
nothing in the code would tell you.**

- Asking the model to reproduce figures and checking them afterwards is a dead
  end. It now receives the route's sentence with each figure replaced by a
  `{{fN}}` token, writes prose around the tokens, and code substitutes the
  values back. A wrong figure became structurally impossible instead of
  something to detect. (ASPIRO, Vejvar & Fujimoto, EMNLP Findings 2023; the same
  method practitioners use for financial commentary and citations.)
- Given only the rewrite directive, the model carries every token through and
  passes. Given the same directive **underneath the frozen product system
  prompt, it ignores the tokens entirely.** The rewrite therefore runs on its
  own `prose_agent`: no tools, no catalog, no persona. That single change is
  what made the mechanism work. It gets the customer's name and the message it
  is answering, and nothing else.

Functional failures are **0**, down from 2. `tj-g51h` and `tj-v41l` are fixed
and verified in production output.

## The plan

The stream used to run: change the dialogue → run the acceptance → read the
number. That no longer works, because the number does not distinguish builds.
So: **the instrument first, the dialogue second.**

| | task | depends on | live traffic |
|---|---|---|---|
| **P0** | `tj-swgu.9` — repeated scoring, mean with its uncertainty | — | no |
| P1 | `tj-swgu.11` — a criterion the customer ruled out is `n_a`, not a zero | — | no |
| P2 | `tj-r1vk` — reset the conversation between S09 and S10 in the harness | — | no |
| P1 | `tj-swgu.10` — cut judge variance at source: scale, judge model | `.9` | no |
| P1 | `tj-swgu.12` — re-establish the baseline from stored transcripts | `.9` `.10` `.11` | **no** |
| P0 | `tj-ja1v` — the original finding, closed or re-scoped | `.12` | — |

**Nothing up to and including `.12` needs live traffic.**
`evaluate_conversation` is read-only, and the transcripts for both `5656c82`
and `c977b07` are already captured. A trustworthy number for what is deployed
is a rescoring job, not a run.

### What each one is

- **`.9`** — score each conversation k times, take the median, publish the
  spread. Add the rule that no conclusion is drawn from a delta smaller than
  its own uncertainty. Cheap, and it unblocks everything.
- **`.11`** — S06 asked for one exact SKU with no alternatives; S09 asked for a
  specific quotation and got it. Both are scored zero for not consulting. The
  evaluator already marks rules `n_a` and drops wholly non-applicable blocks
  from the comparable denominator; what is missing is the trigger. Read the
  customer request, never the reply. Worth about two points of the mean, and it
  is the removal of a penalty for obeying the customer, not an uplift.
- **`.10`** — repeated scoring makes the noise visible, it does not reduce it.
  Levers, in the order the LLM-as-judge literature puts them: the lowest
  precision scale that still separates the cases, one binary reading-
  comprehension question per criterion, a worked example for the non-obvious
  ones, a stronger judge where the call is genuinely hard. **The fifteen client
  criteria are not ours to change in substance — the scale and the judge are.**
- **`.12`** — rescore both builds the same way and compare like with like.

### Deliberately not in the plan

Further dialogue changes. Seven of the nine remaining deterministic turns are
`name-gate`, which the spec puts out of scope. Nothing more should be tuned
until there is something to measure it with.

## Constraints that still bind

- The frozen product system prompt does not grow; new guidance is per-turn
  `runtime_directives` only. `AC-01..AC-30` and its digest are unchanged.
- No side effect moves, becomes conditional on model output, or runs later than
  it does today.
- Rejected and still rejected: lexical backstop over reply text, per-message
  ensembles, abstention fine-tuning, knowledge graph, whole-response blocking.
- Sealed acceptance rounds are superseded, never rewritten; protected evidence
  stays outside Git; no PII, provider or message identifiers, or captured
  wording in reports.
- Beads is the tracker. `uv` always as `env -u VIRTUAL_ENV uv run ...`.

## Authority

- **Needed to start:** paid judge calls against the production database, read
  only — roughly 50–100 calls for `.9` and `.12`, cents at the observed rate.
  No customer messages, no Zoho writes, no deploy.
- **Separate ask, later:** push and deploy, once `.10` or `.11` change `src/`.
- **Separate ask, much later:** any live S01–S10 run. Real WhatsApp, real Zoho.
  Reset the S09/S10 conversation first or those two scores are meaningless.

## Where things are

- Reports: `docs/reports/2026-08-07-production-acceptance-6a14f2f.md`,
  `docs/reports/2026-08-07-slot-rewrite-and-judge-variance.md`
- Spec and original plan:
  `docs/superpowers/specs/2026-08-07-model-written-prose-over-verified-facts-design.md`,
  `docs/superpowers/plans/2026-08-07-model-written-prose-over-verified-facts.md`
- Current state: `.codex/handoff.md`
- Route registry: `src/llm/deterministic_routes.py` — a new deterministic route
  fails a test unless it is declared with a dated re-check.
- Provenance reader: `scripts/e2e_acceptance/route_provenance.py`
- The rewrite: `_verified_prose_mask` / `_verified_prose_render` /
  `_verified_prose_directive` / `prose_agent` in `src/llm/engine.py`
- Captures (outside Git, protected):
  `.git/codex-orchestration/noor-e2e-acceptance/remediation-live/tj-swgu-final2-5656c82-20260807t1512z/`
  and `.../tj-ee5f-final-c977b07-20260807t0745z/`
- Scoring helper used all session:
  `remote_score.py` in the protected `remediation-live` tree, run with
  `ssh noor-server "docker exec -e CONV_ID=<id> -i noor-app-1 python -" < remote_score.py`

## Local verification at the time of writing

Ruff, format, Mypy over 167 sources, Pytest `3238 passed, 19 skipped`, and
`scripts/orchestration/run_process_verification.sh` OK. Everything through
`8f7d584` is pushed to `main`; this document is committed locally and not
pushed.

## Starting instruction

> Read `docs/superpowers/plans/2026-08-07-measure-before-tuning-handoff.md`,
> then `bd show tj-swgu.9`. Start there: repeated scoring of the stored
> transcripts, reporting the mean with its uncertainty. `.11` and `tj-r1vk` are
> independent and can go in parallel. No live traffic is needed for any of it.
> Ask before the first paid judge call, and again before any push or deploy.
