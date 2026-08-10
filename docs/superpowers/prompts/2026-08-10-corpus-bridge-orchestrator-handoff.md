# Codex handoff prompt — bridge our score onto the client's ruler

**Date:** 2026-08-10
**Target runtime:** Codex CLI in `/home/me/code/treejar`
**Kind:** handoff (cross-runtime, manual)
**Validation:** `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind handoff`
→ pass, with one residual warning: the prompt runs over the 1500-character
target. The excess is the constraints block. Trimming it would remove safety
content — the corpus is real customer data and this repository has no
commit-time net — so the length is kept deliberately.

## How to launch

The role loads from `.codex/orchestrator.toml`: `role = "orchestrator-stage"`,
baseline `balanced-v2.19`, `default_mode = "hybrid"`. Start Codex in
`/home/me/code/treejar` and paste the prompt below.

Do not run the stage-closeout scripts. `workspace.current_stage_id` is still
`tj-feet` and no scaffold exists for this work; that is a tracked defer in
`.codex/handoff.md`, not something to fix on the way past. Beads is the unit of
work here and `bd` is the declared source of truth.

The epic is `tj-vz7o`, seven open children. Two more are already closed and
their code is in `ffb8a2d`.

## Prompt

```text
Target: Codex gpt-5.6 orchestrator
Audience: fresh Codex session, repo `/home/me/code/treejar`

Goal: Turn a suggestive comparison into a defensible one. Our bot reads 13.58
on the client's own scoring convention; the client's 1400 unfiltered dialogues
between their salespeople and real customers read 6.05. Two confounds stand
between that and a measurement, and this work removes them in order.

Success criteria:
- `tj-vz7o.3` closed: the 53 stored packets re-read with no applicability map,
  15 criteria per file, no `n_a`, reader disagreement printed, and the delta
  against 13.58 stated with its interval.
- `tj-vz7o.6` and `tj-vz7o.7` closed: response coverage and time-to-first-reply
  for both sides; a frozen scenario set drawn from real customer openings, with
  its selection seed recorded and a baseline taken.
- `tj-vz7o.4` either done under granted authority or left open with the ask
  recorded. `tj-vz7o.5` follows it.
- `tj-vz7o.8` and `tj-vz7o.9` drafted, not sent.
- Gates green, working tree clean, nothing pushed.

Context: read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, then
`docs/superpowers/specs/2026-08-10-the-clients-ruler-and-the-corpus-bridge-spec.md`.
That spec is the contract; where this prompt and the spec disagree, the spec
wins. Claim each issue with `bd update <id> --claim` before starting it.

The first confound is ours: the 106 reads behind 13.58 were handed a frozen
applicability map, so 6.7 rules per packet carry a zero no reader examined. The
second is the judge: theirs is claude-haiku-4.5, ours is an Opus-class blind
panel, and this project has already measured a 3.8-point shift between two
judges on identical text — half the gap being claimed.

Constraints:
- The corpus stays out of the working tree. It lives at
  `<git-common-dir>/codex-orchestration/treejar-dialogs-corpus`, mode 0700/0600,
  and carries client company names and deal amounts. Derived artefacts carry
  `dialog_id` and integers, not a message, a company or an amount. There are no
  commit hooks here and `.gitignore` does not match `dialogs.jsonl`, so
  `tests/test_corpus_stays_outside_the_repository.py` is the only net and it
  stays green. A leak is not fixable afterwards.
- Two rulers exist and are not interchangeable. Client-facing numbers go through
  `raw_total`; build-versus-build goes through `calculate_weighted_score`. Do
  not call `read_comparable_score` on the raw axis, and do not run
  `compare_runs` across two judges — both already refuse, correctly.
- `tj-vz7o.4` is 53 paid model calls. Ask for that authority by naming the exact
  action, and wait. Do not start it and do not work around it.
- No deploy, no push, no production mutation, no run against live traffic, no
  messaging a real user. Commit locally only.
- Claim nothing about conversion, revenue, deal size or close rate: 86% of the
  client's outcomes happen off-channel and the data holds no outcome variable.
  Claim nothing about the bot closing deals — rules 12, 14 and 15 were
  applicable in 1 packet of 53. The evidence supports a claim about openings.
- Leave the rubric and `_build_applicability_assessment`
  (`src/quality/evaluator.py:442`) alone; both are frozen for comparability, and
  a text fallback for rules 9/10/11 would be a scoring decision dressed as a
  fact.
- Every number carries its denominator. 53 packets are 19 scenarios; 1400
  dialogues are 1247 evaluated across 5 managers with one desk at 67%. A
  within-set interval quoted where a between-scenario one belongs makes a number
  ten times more confident than its evidence.
- Verify before each commit: `uv run ruff check src/ tests/ scripts/`,
  `uv run ruff format --check src/ tests/ scripts/`, `uv run mypy src/`,
  `uv run pytest tests/ -q`, `bash scripts/orchestration/run_process_verification.sh`.
  If you edit `.codex/handoff.md`, it has a hard limit of 200 lines and
  `scripts/orchestration/repin_traceability_sources.py` must be run afterwards.

Output: per Beads issue, what closed, what did not and why. Every number with
its denominator and interval. State plainly which confounds are removed and
which remain; if a result sits inside its own uncertainty, say it did not move.
Read two transcripts by eye and say what you saw — three of the last round's
findings came from that and nothing else.

Stop: stop and report after `tj-vz7o.3`, `.6` and `.7` are closed and the
authority for `.4` has been asked for. Stop earlier and ask if the corpus would
have to enter the working tree, if a number would have to cross the two rulers,
or if any requirement here turns out to be materially ambiguous.
```

## What a reviewer should check first

1. `git status --short` clean and nothing pushed; `tests/test_corpus_stays_outside_the_repository.py` green.
2. Every published figure traceable to `raw_total` or to `calculate_weighted_score`, never a subtraction across the two.
3. Denominators present: scenarios not packets, 1247 not 1400.
4. No sentence anywhere about conversion, revenue or closing.
