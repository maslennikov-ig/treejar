Target: Codex worker, inherited model/reasoning for bounded operational risk
Audience: visible spawned agent
Task IDs: tj-ymi3, tj-092y
Stage ID: tj-av22

Goal: Provide safe, testable controls for escalation reconciliation and Docker maintenance: dry-run first, exact idempotent apply mechanics, conservative defaults, reliable logging, and installation readback.

Success criteria:
- Escalations are classified from repository evidence; dry-run writes nothing; apply requires an archived exact-ID manifest, is transactional, and repeats as a no-op.
- Maintenance creates prerequisites, installs one marked cron entry idempotently, verifies readback, and does not default to aggressive cleanup.
- Tests cover failures and repeat runs; operator docs explain dry-run, readback, and rollback.
- No production state, crontab, Docker resources, or alerts are mutated.

Context: Work in `/home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-ops` on `codex/tj-av22-ops`, based on `codex/tj-av22-stabilization@0db9770`. Siblings own API/health and Zoho/inbound. Read the repo contract, tj-av22 plan, and operations docs.

Documentation: No dependency lookup is expected. Use repository scripts/deployment contracts. If platform behavior cannot be verified locally, record the uncertainty rather than guessing.

Asset Routing:
- Selected docs: repo contract, tj-av22 plan, operations runbooks.
- Selected skills: systematic-debugging, test-driven-development, verification-before-completion.
- Selected agents/personas: built-in worker; agent type to spawn: worker.
- Skill items: `/mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md`, `/mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md`, `/mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md`.
- Catalog candidates: none; skip fresh discovery unless blocked.

Constraints: Own `src/services/escalation_state.py`, escalation/reconciliation scripts, Docker-maintenance/install scripts, focused escalation/maintenance tests, relevant operations-runbook files, and artifacts `tj-ymi3.md` and `tj-092y.md`. Read elsewhere as useful; ask before expanding writes. Preserve unrelated work. Prefer tests-first. Production/VPS dry-run, apply, cron installation, cleanup, and real alerts stay outside this stream pending user approval.

Verification: Run focused escalation/API/script tests, Ruff for changed Python, and safe shell/static checks available locally. Report commands that cannot run.

Output: Commit the stream. Create both declared v3 artifacts with truthful evidence, docs impact, changed files, and defers. Report one completion event per artifact using `report_child_completion.py`, status `returned`, commit SHA, sender `operations-worker`, and clean `no`. Summarize outcome and blockers.

Stop: Pause for ambiguous transitions, write-zone conflict, unavailable verification, or any action that would mutate production/VPS state or send a real alert.
