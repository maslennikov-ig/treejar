# Stage tj-rt42 Summary

Updated: 2026-07-23
Status: accepted and closed
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

### Pre-cleanup inventory

- `git worktree list --porcelain`: 21 worktrees total (`main` plus 20 stale
  task worktrees).
- `git for-each-ref refs/heads`: 30 local branches total (`main` plus 29 task
  branches).
- All 27 ordinary task branches are ancestors of `main`. The remaining two
  branches are patch-equivalent: `codex/tj-av22-review-pass` has
  `cherry_plus=0/cherry_minus=2`, and
  `codex/tj-gh48-expected-answer-frames` has
  `cherry_plus=0/cherry_minus=1`. No local branch has a commit whose patch is
  absent from `main`.
- Eleven `tj-av22` worktrees are clean. Nine older worktrees contain only
  shared orchestration-baseline drift, not task implementation:
  `.codex/orchestrator.toml` changes the handoff line cap from 40 to 200;
  `tj-gh48-impl` also contains the superseded Docs L1/L2 wording in the two
  subagent contract files and the current AGENTS adapter in `CLAUDE.md`;
  `tj-gh51-order-quote-cutover` also contains that `CLAUDE.md` adapter.
  Patch fingerprints are:
  `tj-gh48-impl=33b426c219ab7e7f1ecf50aacf9df9d2ac508c5f9d007c47f28d1c8f7b7c6c94`,
  `tj-gh51-order-quote-cutover=e5998d5f0205351a6e791e061e48e1b1cf7a090ab56b1629062977892f5ac9d9`,
  and the seven remaining dirty worktrees share
  `b33d22b1a2ef8baf0c0d65efa3d1b276e83f5e8e7bd48e48981dca1a6a70606c`.
  Current tracked repository contracts supersede these copies, so the hashes
  and semantic diff classification are the preservation record.
- Protected untracked user paths were fingerprinted before cleanup:
  `noor-100-dialogue-tuning-offer.html=170246f1...`,
  `noor-media-recovery-pm-note.html=4433b93a...`,
  `noor-media-recovery-pm-note.md=5b46a609...`,
  `treejar-visual-search-offer.html=4d110f42...`, plus one file under
  `output/` and eight files under `tmp/`.
- `.venv` is active project infrastructure and is preserved. Rebuildable,
  inactive `.mypy_cache`, `.ruff_cache`, `.pytest_cache`, and project
  `__pycache__` directories are cleanup candidates. No repository-owned
  pytest, Ruff, Mypy, Uvicorn, or Vite process was active at classification
  time.
- Shared completion transport contains 14 reviewed historical `tj-av22`
  events and zero events for `tj-rt42`; it is retained as review history.
- The inbox reader itself exposed a stage-filtering defect. A regression test
  now proves that historical events from other stages are ignored before exact
  current-stage validation; the focused process suite passes 11/11.

### Planned exact cleanup

- Remove child worktrees before their nested parent, then remove the remaining
  clean worktrees and the nine classified baseline-drift worktrees.
- Delete all 29 local task branches only after worktree removal, using normal
  deletion for ancestors and force deletion only for the two proven
  patch-equivalent branches.
- Remove only the classified rebuildable caches. Preserve `.venv`, completion
  history, all remote branches, and every protected user path.

### Post-cleanup readback

- All 20 stale task worktrees were removed child-first. `git worktree
  list --porcelain` now reports only `/home/me/code/treejar` on `main`;
  `.worktrees/` is an empty 4 KB directory.
- All 29 local task branches were removed. Normal deletion covered 26 branches;
  Git required force deletion for one ancestor with a stale upstream and the
  two pre-proven patch-equivalent branches. `refs/heads` now contains only
  `main`. No remote branch was deleted.
- `.mypy_cache` (about 377 MB), `.ruff_cache`, `.pytest_cache`, and all project
  `__pycache__` directories were removed. `.venv` remains at about 1.6 GB.
- All four protected offer-file SHA-256 values and the protected file counts
  (`output=1`, `tmp=8`) match the pre-cleanup snapshot.
- `git fsck --full` reports no repository corruption. Unreachable objects
  listed only when explicitly using `--no-reflogs --unreachable` are the
  expected recoverable object tail after local branch deletion; no object
  pruning or reflog expiry was performed.
- Completion history remains intact: 14 reviewed historical events, zero
  current-stage events, and zero pending current-stage events.
- CI run `30034173648` passed for the inbox stage-filter correction. The
  previously deployed Zoho terminal-error correction also passed lint,
  type-check, full tests, and deployment in run `30033697030`; production
  readback confirms exact release `c519c3f1...`, five running services, green
  Redis/database health, cron markers `1:1:1`, and a successful maintenance
  heartbeat.
- Canonical stage closeout passed artifact and readiness validation, blocking
  review reconciliation, documentation/project-index/debt checks, process
  verification, `git diff --check`, and the 102-test acceptance slice.

## Closeout

- `docs-reviewed: updated` — this stage summary is the durable preservation
  and deletion record; product and operations docs are unaffected.
- `project-index: reviewed-no-change` — no entrypoint change is planned.
- `graph-reviewed: no-change-needed` — Graphify is not configured.
