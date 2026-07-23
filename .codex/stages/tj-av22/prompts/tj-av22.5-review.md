# Independent Noor stabilization review

Review Beads task `tj-av22.5` in
`/home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-review`
on branch `codex/tj-av22-review`, based on
`codex/tj-av22-stabilization@ee7a250`.

Assess whether the integrated stabilization changes genuinely satisfy the
approved specification, with special attention to security/privacy,
OAuth retry and replay idempotency, concurrent token refresh, exact-ID
escalation apply, health semantics, Docker heartbeat/cron safety, public API
retirement, and runtime signal collection/delivery.

Use your judgment to follow the highest-risk paths. Focus on actionable bugs
and contract gaps rather than style. Check tests as evidence but reason about
failure modes they may miss. You may run read-only tests and static checks.
Do not call live services, deploy, mutate production data, or change product
code.

Your only write is
`.codex/stages/tj-av22/artifacts/tj-av22.5.md`. Use the v3 delegated artifact
format and make the body findings-first. Each finding should have severity,
exact file/line evidence, impact, and a practical correction. State clearly
when there are no P0/P1 findings and distinguish approval-gated production
proof from local code defects.

After the review, commit the artifact and report completion through
`scripts/orchestration/report_child_completion.py`. Leave the worktree for root
review.

## Asset Routing

- Selected skills: `code-review`, `verification-before-completion`,
  `format-commit-message`.
- Selected agent/persona: built-in worker acting as an independent senior
  reliability/security reviewer.
- Catalog candidates: none; installed review guidance and repository evidence
  are sufficient.

## Documentation

No external dependency research is expected. Use `AGENTS.md`,
`.codex/orchestrator.toml`, the approved stabilization spec/plan, Beads state,
the changed code, tests, and operations docs. If a version-sensitive
third-party contract becomes decisive, use authoritative Context7
documentation when available and cite it in the artifact.

## Return contract

Return:

- findings in severity order, or an explicit no-findings statement;
- residual risks and production-only proof still required;
- checks run;
- artifact commit, path, and completion event ID.
