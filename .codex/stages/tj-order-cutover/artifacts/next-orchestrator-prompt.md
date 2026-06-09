---
schema_version: orchestration-artifact/v1
artifact_type: delegated-stream
task_id: tj-order-cutover
stage_id: tj-order-cutover
agent_type: n/a
subagent_model: n/a
reasoning_effort: high
model_reasoning_rationale: Architecture-sensitive order/quote runtime cutover with production regressions and live E2E risk.
repo: treejar
branch: codex/tj-order-flow-cutover-plan
base_branch: main
base_commit: 3d37eb1cd6002aea6919ff07f01c7c03beeb8e10
worktree: /home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover
write_zone:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-09-order-flow-cutover.md
  - .codex/stages/tj-order-cutover
success_criteria:
  - Next orchestrator can implement from the plan without re-discovering root cause.
selected_docs:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-09-order-flow-cutover.md
selected_skills:
  - /home/me/.agents/skills/orchestrator-stage/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/subagent-driven-development/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md
selected_agents:
  - correctness_reviewer
  - improvement_reviewer
  - llm_architect
  - architect_reviewer
  - qa_expert
  - risk_manager
  - docs_reviewer
catalog_candidates:
  - none - installed QUALITY_PACK agents are sufficient.
parallel_group: planning
depends_on_streams:
  - none
parallel_decision: local
status: returned
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: not_applicable
cleanup_notes: Planning artifact only.
risk_level: high
docs_impact: structural
docs_reviewed: updated
docs_review_notes: Specs and plan updated for full cutover.
verification:
  - pending in planning closeout
changed_files:
  - docs/specs/dialogue-state-kernel.md
  - docs/specs/customer-facts-layer.md
  - docs/superpowers/plans/2026-06-09-order-flow-cutover.md
  - .codex/stages/tj-order-cutover/summary.md
  - .codex/stages/tj-order-cutover/artifacts/next-orchestrator-prompt.md
explicit_defers:
  - Implementation/deploy/live E2E deferred to next orchestrator with explicit user approval for external actions.
---

# Summary

This artifact records the ready-to-use prompt for the next orchestrator. It is a
planning handoff, not an implementation result.

# Scope / Routing

The prompt routes the next run to `tj-order-cutover`, the existing local
LangGraph/Pydantic/PydanticAI stack, and installed QUALITY_PACK agents. No
catalog-only assets or new runtime framework are selected.

# Prompt For Next Orchestrator

Use `$orchestrator-stage` to implement stage `tj-order-cutover`.

Goal: finish the full order/quote flow cutover so recurring context-loss bugs
#40-#51 cannot reappear through legacy metadata, recent-history-only matching,
or assistant-prose quote recovery. Use existing libraries and capabilities:
LangGraph, Pydantic, PydanticAI structured extraction/test doubles, SQLAlchemy,
pytest, Ruff, and mypy. Do not add Rasa, Parlant, or another runtime framework
unless implementation proves the existing stack cannot satisfy the contract.

Start from:

- Repo/worktree: `/home/me/code/treejar/.worktrees/tj-gh51-order-quote-cutover`
- Planning branch: `codex/tj-order-flow-cutover-plan`
- Base/main SHA: `3d37eb1cd6002aea6919ff07f01c7c03beeb8e10`
- Stage: `tj-order-cutover`
- Beads epic: `tj-order-cutover`
- Plan: `docs/superpowers/plans/2026-06-09-order-flow-cutover.md`
- Specs:
  - `docs/specs/dialogue-state-kernel.md`
  - `docs/specs/customer-facts-layer.md`
- Stage summary: `.codex/stages/tj-order-cutover/summary.md`

Re-orient before writing:

1. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
   `.codex/stages/tj-order-cutover/summary.md`, this prompt artifact, the plan,
   the two specs, Beads state, `git status`, relevant diffs, active worktrees,
   and open/updated GitHub issues #40-#51.
2. Preserve unrelated dirty files or worktrees. The main checkout
   `/home/me/code/treejar` may contain unrelated local changes; do not overwrite
   them. Work in a dedicated branch/worktree.
3. Restate current goal, state, constraints, blockers, active worktrees, and the
   next concrete step before implementation.

Constraints:

- Use existing libraries first. Prefer LangGraph/Pydantic/PydanticAI over new
  frameworks and avoid new custom parsing unless catalog-backed or unavoidable.
- No hidden inline-only delegation. If delegating, use separate visible Codex
  subagents.
- No deploy, live WhatsApp, Wazzup/Zoho production mutation, issue closure, or
  remote cleanup without explicit current-task approval.
- Keep legacy order/quote keys as read-only migration/diagnostic fallback, not
  write authority. New order/quote writes go to the typed runtime frame first.
- `src/llm/engine.py` may remain the side-effect integration point, but it must
  stop owning order/quote policy by branch order.

Required routing:

- Use installed QUALITY_PACK agents before catalog. Useful agents:
  `code_mapper`, `python_pro`, `ai_engineer`, `backend_developer`,
  `correctness_reviewer`, `improvement_reviewer`, `llm_architect`,
  `architect_reviewer`, `qa_expert`, `risk_manager`, and `docs_reviewer`.
- Use Docs L1/L2 or local docs only if current LangGraph/PydanticAI API behavior
  matters during implementation. Otherwise record that no dependency docs lookup
  was needed because the plan uses already-installed APIs in existing code.
- Graphify is not configured in this repo as of this planning stage.

Implementation order:

1. Start with `tj-order-cutover.1`: RED replay matrix and invariants. Do not
   implement until at least one relevant new regression fails.
2. Implement the typed contract/migration in `tj-order-cutover.2`.
3. Implement runtime-owned quantity frames in `tj-order-cutover.3`.
4. Implement runtime-owned quote selection and SKU repair in
   `tj-order-cutover.4`.
5. Replace order/quote branches in `src/llm/engine.py` with a typed runtime
   adapter in `tj-order-cutover.5`.
6. Align facts, memory, and dialogue kernel in `tj-order-cutover.6`.
7. Run review-fix streams and observability updates in `tj-order-cutover.7`.
8. Run full verification, stage closeout, and only then request/perform approved
   delivery/live E2E under `tj-order-cutover.8`.

Mandatory test matrix:

- #42 second occurrence: `SK 45 White` -> quantity prompt -> `2`; no generic
  opener.
- #50: `I need 2 SKYLAND NOVO 2400 Meeting Table and 4 CH 616 chairs`; preserves
  both lines.
- Unresolved repair: `CH 616 NEW black` resolves the existing `4 x CH 616`
  unresolved line.
- #49/#51: quote details after a full order summary never restart item/quantity
  collection.
- `Only SKYLAND NOVO 2400 2 position` fills the active quantity/product frame.
- Direct SKU+quantity quote path.
- Compact quote details: `Lilia / Del company / 2 street / Only table`.
- Discount/payment/human handoff blocker remains safe.
- Duplicate-message check: one customer turn must not send repeated identical
  bot prompts.

Verification gates:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short
scripts/orchestration/run_stage_closeout.py --stage tj-order-cutover
```

Closeout:

- Update Beads task statuses and notes.
- Update `.codex/stages/tj-order-cutover/summary.md` with actual evidence.
- Update `.codex/handoff.md` with current deployed or pre-delivery truth.
- Include `docs-reviewed`.
- Include `graph-reviewed: no-change-needed` unless Graphify is enabled later.
- Do not claim completion from memory; cite fresh verification evidence.

# Verification

This artifact should validate with
`scripts/orchestration/validate_artifact.py .codex/stages/tj-order-cutover/artifacts/next-orchestrator-prompt.md`.
The implementation prompt itself requires full runtime verification in the next
stage.

# Delivery / Cleanup

Planning artifact only. No implementation branch merge, deploy, production
mutation, or live WhatsApp test is included in this artifact.

# Risks / Follow-ups

- The next orchestrator must start with RED regression coverage before changing
  runtime code.
- The main checkout may contain unrelated local modifications; use the clean
  planning worktree or another dedicated worktree and preserve unrelated files.
- Live E2E, deploy, and GitHub issue closure require explicit current-task
  approval.
