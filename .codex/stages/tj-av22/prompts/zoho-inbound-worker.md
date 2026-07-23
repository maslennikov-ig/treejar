Target: Codex worker, inherited model and reasoning (appropriate for cross-module OAuth, retry, lock, and idempotency risk)
Audience: separate visible spawned agent
Task ID: tj-p9ui
Stage ID: tj-av22

Goal: Make Zoho token refresh and accepted inbound-batch processing failure-safe so malformed OAuth success responses cannot silently discard messages or create duplicate replies on retry.

Success criteria:
- A 2xx response without a usable `access_token`, OAuth error JSON, and invalid JSON fail deterministically without leaking secrets.
- Token TTL and refresh-lock behavior stay safe on success and every failure path.
- Transient accepted-batch failures have bounded retry and visible terminal failure; replay is idempotent.
- CRM, Inventory, chat-batch, and worker regressions demonstrate the behavior.

Context: Work in `/home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-zoho` on `codex/tj-av22-zoho`, based on `codex/tj-av22-stabilization@0db9770`. Parallel siblings own API/health and operational safety. Read `AGENTS.md`, `.codex/orchestrator.toml`, and the tj-av22 spec/plan.

Documentation: Use official Zoho CRM V8 refresh/token-validity contracts: `https://www.zoho.com/crm/developer/docs/api/v8/refresh.html` and `https://www.zoho.com/crm/developer/docs/api/v8/token-validity.html`. Use repository evidence for retry semantics.

Asset Routing:
- Selected docs: official Zoho links and repository contracts.
- Selected skills: systematic-debugging, test-driven-development, verification-before-completion.
- Selected agents/personas: built-in worker; agent type to spawn: worker.
- Skill items: `/mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md`, `/mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md`, `/mnt/c/Users/masle/.codex/superpowers/skills/verification-before-completion/SKILL.md`.
- Catalog candidates: none; selected assets are sufficient. Skip fresh discovery unless blocked.

Constraints: Own `src/integrations/zoho_oauth.py`, Zoho CRM/Inventory clients, `src/services/chat.py`, `src/worker.py`, focused Zoho/chat-batch/worker tests, and `.codex/stages/tj-av22/artifacts/tj-p9ui.md`. Read elsewhere as useful; ask before expanding writes. Preserve unrelated work. Prefer tests-first. Do not call live Zoho, Telegram, WhatsApp, or production services.

Verification: Run focused Zoho, chat-batch, and worker tests plus Ruff and mypy over changed surfaces. Report commands that cannot run.

Output: Commit the stream. Create the declared v3 artifact with truthful evidence, docs impact, changed files, and defers. Report completion via `report_child_completion.py --task tj-p9ui --stage tj-av22` with status `returned`, commit SHA, sender `zoho-inbound-worker`, and clean `no`. Summarize outcome and blockers.

Stop: Pause if retry/idempotency ownership remains unclear, writes would leave the assigned zone, verification is unavailable, or credentials/production access are required.
