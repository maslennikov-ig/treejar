# Codex handoff prompt — finish `tj-ee5f` remediation

**Date:** 2026-08-03
**Target runtime:** Codex CLI in this repository
**Kind:** handoff (cross-runtime, manual)
**Validation:** `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind handoff` → pass,
with one residual warning: 2693 characters against a 1500 target. The excess is
the write zone, the two authority gates, and the paid/deploy prohibitions;
trimming further would remove safety content, so it is kept deliberately.

## How to launch

The orchestrator role is already fixed by `.codex/orchestrator.toml`:
`role = "orchestrator-stage"`, baseline profile `balanced-v2.19`, current stage
`tj-ee5f`, `inline_subagents_allowed = false`,
`subagent_visibility = "separate_spawned_threads"`,
`max_concurrent_subagents = 4`. Start Codex in `/home/me/code/treejar` and paste
the prompt below; the role, stage, and delegation policy load from the repo.

Four concurrent subagents map cleanly onto the four Beads streams
(`.7`, `.8`, `.12`, `.13`), which is also how the review was partitioned.

## Prompt

```text
Target: Codex gpt-5.6 orchestrator
Audience: fresh Codex session, repo `/home/me/code/treejar`

Goal: Finish stage `tj-ee5f` so the deterministic acceptance failures are
remediated on the path production actually runs, the isolated model battle can
select a non-incumbent winner, and stage documents claim only what the code does.

Success criteria:
- Every `must-fix` in the review section of the spec is closed or explicitly
  deferred in Beads.
- An explicit quote refusal never renders "on hold" wording; one SKU gives one
  stock number per turn; verified facts never replace the model's answer wholesale.
- The core round can end `winner`, not only `blocked` or `practical_tie`.
- Typed dialogue state governs the default runtime path, or the stage records in
  writing which fixes stay inert and behind which flag.
- `.codex/stages/tj-ee5f/summary.md` and the task artifacts assert remediation
  only where a focused test proves it.

Context:
- Branch `codex/tj-ee5f-quality-model-battle` at `3701c1e`; gates green there.
- Spec plus the full independent review with file:line evidence:
  `docs/superpowers/specs/2026-08-03-noor-e2e-remediation-and-model-comparison-spec.md`.
  Read it first; findings are `R-01`..`R-20` under "Review outcome".
- `bd ready` gives the unblocked set and the dependency order under
  `tj-ee5f.7/.8/.12/.14`. Harness repair is `.14`; `.13` owns the paid run and
  stays blocked.
- Repo contract: `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`.

Constraints:
- Write zone: `src/`, `tests/`, `scripts/`, `.codex/stages/tj-ee5f/`,
  `.codex/handoff.md`, `docs/superpowers/`. Leave `docs/client/` and untracked
  files alone.
- Fix with typed state and configuration, not prompt prose. No scenario sentences
  in product code, no net prompt growth.
- Preserve frozen `AC-01..AC-30` and its digest; protected evidence stays outside git.
- Defers must be bounded, in Beads, and listed under `Explicit defers` in the handoff.

Ask the user when two outcomes stay plausible and the answer changes acceptance,
scope, or rework — notably whether the dialogue kernel becomes the default path
now. Ask separately, naming the exact action, before any paid OpenRouter call,
model-config change, push, deploy, or production readback.

Output: behavior first — per closed failure, the customer-visible difference and
the command that shows it; scenarios checked and not checked; remaining Beads work
and any inert-behind-a-flag fix; gate output and diffs last.

Stop: Stop after local remediation and consistent stage documents, then report.
Do not run the paid battle, change model config, push, deploy, or touch production.
```

## Notes for the launcher

Two decisions are deliberately left to the owner rather than defaulted:

- **`R-01`, the dialogue kernel flag.** Turning `dialogue_kernel_mode` away from
  `legacy` changes conversation behavior in production. Until it is decided, the
  `.8` fixes are inert. The prompt requires Codex to ask, and to record the
  answer either way.
- **Nothing about money.** The budget rules are already settled in the spec, so
  Codex has no budget question to ask; it simply must not spend. The paid battle
  and the deploy remain separate authority gates.
