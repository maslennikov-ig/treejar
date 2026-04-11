# Orchestrator Handoff

Updated: 2026-04-06
Current baseline branch: `main`
Current baseline commit: `27783a4e4f97fcb66073f07f2989bdff8848b622`

## Current state

- This is a single-repo Treejar runtime repository with a main-only delivery flow.
- `.codex/orchestrator.toml` is the machine-readable contract; `.codex/handoff.md` is current-state only.
- Tracked stage history now lives under `.codex/stages/`; `.codex/agent-reports/` remains the legacy local-only archive.
- `bd ready --json` works in this repository.
- Canonical live runtime target remains `https://noor.starec.ai`; direct `/opt/noor` triage is still the practical runtime-debug path.

## Active stage

- Current active stage: `tj-19ol.3` — blocker-driven canonical live-testing triage.
- Stage summary: [`.codex/stages/tj-19ol.3/summary.md`](./stages/tj-19ol.3/summary.md)
- Latest tracked artifact: [`.codex/stages/tj-19ol.3/artifacts/tj-19ol.3.13.md`](./stages/tj-19ol.3/artifacts/tj-19ol.3.13.md)
- Current truth: the first-turn concrete-order handoff fix is accepted and hot-applied; consultative bulk behavior is healthy; the acoustic/no-exact-match path is still only partial.

## Next recommended

- Next stage id: `tj-19ol.3`
- Recommended action: use `tj-19ol.3` only for fresh evidence-driven canonical retests; keep `tj-5dbj` separate for deterministic CPU-only rebuild work on `/opt/noor` and `tj-5ypi` separate for repo/CI deploy-contract drift.

## Starter prompt for next orchestrator

```text
Use $stage-orchestrator to continue with stage `tj-19ol.3` in this repository. Read AGENTS.md, .codex/orchestrator.toml, .codex/handoff.md, and the linked stage summary/artifact first. Then confirm current canonical runtime evidence, keep rebuild and deploy-contract follow-ups split, and prepare the next retest step without widening scope.
```

## Explicit defers

- The acoustic/no-exact-match path is still only partially resolved; keep it explicit in `tj-19ol.3` retest work instead of quietly treating it as finished.
- `tj-5dbj` rebuild work and `tj-5ypi` deploy-contract drift remain separate follow-ups, not debt hidden inside `tj-19ol.3`.
