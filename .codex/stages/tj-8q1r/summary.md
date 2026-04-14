# Stage Summary

Stage ID: `tj-8q1r`
Status: `closed`
Updated: 2026-04-14
Baseline: `main@fe9f2c64b0b8a25928aef78295bac721a8d75ad1`

## Outcome

- `tj-8q1r` is closed as a narrow orchestration-truth cleanup stage.
- `CLAUDE.md` now points back to `AGENTS.md` and `.codex/*` instead of carrying a stale parallel contract.
- The stale macOS WeasyPrint defer was replaced with current evidence: minimal PDF rendering works locally without `DYLD_FALLBACK_LIBRARY_PATH`, while the remaining local verification gap is app env for the LLM import path.
- Root-local `.gitignore` / `.beads` cleanup was explicitly not promoted into `main`, because the exported `.beads/issues.jsonl` snapshot is stale relative to the embedded-dolt Beads source of truth.

## Linked Artifacts

- [`.codex/stages/tj-8q1r/artifacts/tj-8q1r.md`](./artifacts/tj-8q1r.md)

## Next Step

- Leave `.beads` tracking policy as a separate review item if you later want portable Beads exports in git.
- Keep the dirty root worktree isolated until those local-only changes are either recreated cleanly or discarded.
