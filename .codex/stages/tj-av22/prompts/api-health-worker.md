Target: Codex worker, inherited model and reasoning (appropriate for a bounded security/public-health contract change)
Audience: separate visible spawned agent
Task IDs: tj-9c94, tj-38l5
Stage ID: tj-av22

Goal: Make Noor's health surface safe and truthful. Raw Redis queue data should not be publicly exposed, and health should reflect the deployed version plus required Redis and database availability.

Success criteria:
- Unauthenticated callers cannot obtain raw Redis values from the debug route.
- Health returns structured 200 only when required dependencies are healthy and 503 with sanitized detail otherwise.
- Version resolution uses the deployed package/configuration with a deterministic test fallback.
- Focused tests cover the security boundary and Redis/DB/version combinations.

Context: Work in `/home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-api` on `codex/tj-av22-api`, based on `codex/tj-av22-stabilization@0db9770`. Parallel siblings own Zoho/inbound and operational safety. Read `AGENTS.md`, `.codex/orchestrator.toml`, and the tj-av22 spec/plan.

Documentation: No dependency lookup is expected; use repository contracts and consumers. If an external contract becomes necessary, report why.

Asset Routing:
- Selected docs: repository contracts and tj-av22 planning docs.
- Selected skills: systematic-debugging, test-driven-development, verification-before-completion.
- Selected agents/personas: built-in worker; agent type to spawn: worker.
- Skill items: `/mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md`, `/mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md`, `/mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md`.
- Catalog candidates: none; installed workflows fit. Skip fresh discovery unless a specialist blocker appears.

Constraints: Own `src/api/v1/health.py`, `src/schemas/health.py`, narrowly required wiring in `src/api/deps.py` or `src/main.py`, `tests/test_health.py`, `tests/test_api_health.py`, `tests/test_api_internal_auth.py`, and the two declared artifacts. Read elsewhere as useful; ask before expanding writes. Preserve unrelated work. Choose the smallest repository-compatible implementation, preferably tests-first. Do not deploy or mutate production.

Verification: Run focused contract tests, Ruff on changed Python, and relevant type checks. Report any command that cannot run.

Output: Commit the stream. Create v3 artifacts `.codex/stages/tj-av22/artifacts/tj-9c94.md` and `tj-38l5.md` from the template with truthful evidence, docs impact, changed files, and defers. Report one completion event per artifact using `report_child_completion.py` with status `returned`, commit SHA, sender `api-health-worker`, and clean `no`. Summarize outcome and blockers.

Stop: Pause for genuine public-API ambiguity, write-zone conflict, unavailable verification, production access, or debt that cannot be tracked explicitly.
