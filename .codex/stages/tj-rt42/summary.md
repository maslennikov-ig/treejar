# Stage tj-rt42 Summary

Updated: 2026-07-23
Status: in progress
Branch: `main`
Beads: `tj-rt42`

## Cohesive Boundary

This stage re-audits and safely removes stale local worktrees, integrated local
branches, reviewed completion tails, and disposable caches. The main worktree,
protected branch, unrelated user files, active shared Codex processes, and any
ambiguous or unique change are outside destructive scope.

## Exact Authorized Scope

- User approval: 2026-07-23 blanket authorization for the previously proposed
  destructive repository cleanup.
- Remove a worktree only after its dirty/untracked state and unique commits are
  classified. Archive evidence before removing any non-empty diff that is not
  already tracked elsewhere.
- Delete a local branch only after its worktree is removed and it is merged or
  patch-equivalent to `main`; preserve remote-only/unmerged branches.
- Remove only rebuildable project caches whose owners are inactive. Preserve
  `.venv`, active dependencies, unrelated app processes, and all existing
  untracked user offer/output/tmp files unless an exact disposable subpath is
  proven.
- Do not delete remote branches.

## Routing

- Skills: `orchestrator-stage`, `cleanup-audit`,
  `verification-before-completion`, and `orchestration-closeout`.
- Documentation: repository Git/orchestration contracts only; no external docs
  are needed.
- Delegation: root-owned sequential cleanup because every worktree and branch
  shares one git common dir and deletion order matters.
- Graphify: not configured; cleanup does not justify a graph refresh.

## Evidence

Pending re-audit and cleanup.

## Closeout

- `docs-reviewed: pending`
- `project-index: reviewed-no-change` — no entrypoint change is planned.
- `graph-reviewed: no-change-needed` — Graphify is not configured.
