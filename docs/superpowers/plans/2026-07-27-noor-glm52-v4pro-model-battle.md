# Noor GLM 5.2 / DeepSeek V4 Pro Model Battle Plan

**Goal:** Produce fresh, reproducible route rankings for four candidates per
Noor workload without changing production.

**Boundary:** One cohesive evaluation stage owns candidate configuration,
synthetic inference, blinded sales scoring, route decisions, and evidence.

## Scope ledger

- Sales: GLM-5, GLM-5.2, DeepSeek V4 Flash, DeepSeek V4 Pro.
- Fast/system: Nex-N2-Mini, GLM-5.2, DeepSeek V4 Flash, DeepSeek V4 Pro.
- Accepted cases, two repetitions, fresh baselines, hard gates, blind review.
- Production adoption and deployment are excluded.

## Task 1: Generalize candidate configuration

**Files:** `scripts/model_battle.py`,
`tests/test_scripts_model_battle.py`.

**Verification lane:** `tdd-required`.

- [x] Add failing tests for the extended route matrix, capability preflight,
  job construction, and manifest identity.
- [x] Add an explicit benchmark profile while preserving the original profile
  as the default for reproducibility.
- [x] Run the focused benchmark tests and static checks.

## Task 2: Execute and evaluate

**Files:** `.codex/stages/tj-5e3k/results/`,
`docs/reports/model-battle-glm52-v4pro-2026-07-27.md`.

- [x] Verify all exact model IDs and required capabilities in the live
  OpenRouter catalog.
- [x] Run 96 sequential sales calls and 192 sequential system calls.
- [x] Complete the anonymous sales review before reading the reveal key.
- [x] Score all candidates, apply hard gates, and publish strict and practical
  route decisions with limitations.

## Task 3: Close the stage

- [x] Run focused and repository quality gates.
- [x] Review documentation impact and Graphify status.
- [x] Update Beads, stage artifact, summary, and handoff.
- [x] Run canonical process verification and stage closeout.
- [x] Keep production routing unchanged.
