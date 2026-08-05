---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-feet/stage-manifest.json
stream_owner: tj-feet-local-implementation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: the Noor sales assistant runtime and the sealed model comparison
public_facade: no new public facade; per-turn runtime directives and the battle harness
bounded_acceptance: one root-owned acceptance after implementation, stopped at the tj-feet.8 paid gate
non_goals:
  - paid provider calls, model configuration change, push, deploy, production mutation, Zoho/PDF/Wazzup effects, live messaging
  - paraphrase detection inside a field that exists, which belongs to tj-feet.9
  - the counter-set generation run, which the owner scheduled after the model is chosen
evidence:
  - none
task_id: tj-feet-root-stream
epic_id: tj-feet
stage_id: tj-feet
session_id: tj-feet
milestone: sales grounding, tool obedience and evaluation repair
milestone_status: in_progress
agent_type: n/a
subagent_model: n/a
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: executed locally by the root owner; the session instruction prohibits the Agent tool and the repo contract sets inline_subagents_allowed = false, so no visible subagents were available
repo: treejar
branch: codex/tj-feet
base_branch: codex/tj-ee5f-quality-model-battle
base_commit: ea35d44
worktree: /home/me/code/treejar/.worktrees/tj-feet
write_zone:
  - src/dialogue/
  - src/llm/engine.py
  - scripts/model_battle*
  - tests/
  - docs/reports/, .codex/stages/tj-feet/, .codex/goals/tj-feet/
success_criteria:
  - the quotation tool is absent from the offered set while consent is declined, and a renewed explicit request restores it
  - a claim whose field path is absent from the retrieved row cannot reach the customer
  - an unknown attribute yields a useful partial answer, never a refusal
  - the wrongly failed labelled assumption passes and the wrongly passed vague claim fails
  - repo gates pass once at stage acceptance
selected_docs:
  - docs/superpowers/specs/2026-08-05-sales-grounding-and-tool-obedience-spec.md
selected_skills:
  - orchestration-bridge:orchestrator-stage
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: n/a
depends_on_streams:
  - none
parallel_decision: local
status: accepted
delivery_method: manual integration
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: branch codex/tj-feet and its worktree stay in place; the stage is not closed
risk_level: medium
verification_tier: integration
risk_tags:
  - state-transition
  - public-api
affected_surfaces:
  - backend
invariants:
  - state-transition
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: four stage reports, the stage summary and .codex/handoff.md record the behaviour change and the open gates
verification:
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -q --tb=short: passed
  - scripts/orchestration/run_process_verification.sh: passed
changed_files:
  - src/dialogue/claim_contract.py
  - src/dialogue/order_guards.py
  - src/llm/engine.py
  - scripts/model_battle.py
  - scripts/model_battle_cases.py
  - scripts/model_battle_rubric.py
  - scripts/model_battle_anchors.py
  - scripts/model_battle_counterset.py
  - tests/test_llm_engine.py
  - tests/test_dialogue_claim_contract.py
  - tests/test_scripts_model_battle_rubric.py
  - tests/test_scripts_model_battle_fixtures.py
  - tests/test_scripts_model_battle_counterset.py
explicit_defers:
  - tj-feet.10 - the claim contract runs on the requested-gap repair trigger only; extending it to every catalog turn needs an owner decision on the per-turn cost
  - tj-feet.5, tj-feet.6, tj-feet.9 - no measured numbers until the counter-set generation run, scheduled by the owner after the model is chosen
  - tj-feet.8 - paid provider calls remain an ungranted authority gate
---

# Summary

The assistant can no longer offer the quotation tool after an explicit decline,
and can no longer assert a product attribute whose field path is absent from the
row it actually retrieved. An unknown attribute now produces a useful partial
answer rather than silence or a refusal. The instrument that judges all of this
tells a labelled assumption from a fabrication and reports groundedness, tool
obedience and conversational quality separately.

Five of nine child tasks are closed. The stage stops at the `tj-feet.8` paid
provider gate, as instructed.

# Scope / Routing

Executed locally by the root owner. The session instruction prohibits the Agent
tool and `.codex/orchestrator.toml` sets `inline_subagents_allowed = false`, so
the named reason for direct local execution is unavailable visible subagents.

The base required a decision. The specification's exact source locations and the
sealed round it analyses resolve only against
`codex/tj-ee5f-quality-model-battle` at `ea35d44` plus that worktree's
uncommitted state; local `main` is 90 commits behind `origin/main` and
`origin/main` is 19 behind that branch. Commit `94c29e6` imports the harness and
the stage documents verbatim and records what was deliberately left with the
other stream.

# Verification

One root-owned acceptance set on the combined tree, run once:

- `uv run ruff check src/ tests/` — passed
- `uv run ruff format --check src/ tests/` — 331 files already formatted
- `uv run mypy src/` — no issues in 166 source files
- `uv run pytest tests/ -q --tb=short` — 2923 passed, 19 skipped
- `scripts/orchestration/run_process_verification.sh` — OK

Per task, a focused red-green target ran first. The two `tj-feet.2` decline
cases failed before the guard and pass after it; 6 of 12 fixture regressions
fail on the pre-repair fixtures and all 12 pass after.

# Delivery / Cleanup

Accepted locally on `codex/tj-feet`. Not pushed, not merged, not deployed. The
branch and worktree stay in place because the stage is not closed.

# Risks / Follow-ups / Explicit Defers

The claim contract is enforced on the repair-pass trigger only, so a volunteered
attribute on a turn with no requested gap is still unverified; `tj-feet.10`
tracks that with both implementation options and their costs. The counter-set
has no numbers yet by owner decision. `tj-feet.8` needs explicit authority for
about `$0.04` of candidate provider spend against the retained `$4.00`
reservation.

`codex/tj-feet` and `codex/tj-ee5f-quality-model-battle` both edit
`.codex/handoff.md`; the other stream's edits are uncommitted in its own
worktree and will need reconciling at merge.
