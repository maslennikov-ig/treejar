Target: Codex gpt-5.6 in `/home/me/code/treejar`.
Audience: project owner; final client report reader is Viktor.

Goal:
Use `$orchestrator-stage` to fix every unresolved finding from
`docs/client/noor-live-sales-tool-e2e-2026-07-28.md`, deliver one reviewed
release, rerun production acceptance, and close `tj-ee5f` only on complete
evidence.

Success:
- Reuse `tj-ee5f.1`; make `.5-.10` its blockers and preserve failed evidence.
- Preserve the frozen `AC-01..AC-30` snapshot and digest; do not add or rename
  criteria.
- Finish the real trusted production execution path, typed name-gate intent,
  EN/AR catalog/no-match routing, explicit quote state, safe Zoho/PDF flow, and
  dedicated STT with message-identity deduplication.
- Run one final release gate, canonical deploy/readback, at least ten complete
  text scenarios, and provider EN/AR/voice canaries.
- Require every text scenario `>=20/30`, mean `>=24/30`, no functional failure,
  unresolved P0/P1, or nonterminal side effect.

Context:
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, Beads
`tj-ee5f.1` and `.5-.10`, the current stage manifests, the remediation design,
and the remediation plan. Treat recorded runtime identities as evidence to
verify. Work in isolated branches/worktrees and preserve unrelated user files.

Constraints:
Exact captured sentences belong only in fixtures. Production uses typed state,
catalog data, and compact configuration. Do not grow the product system prompt.
Use focused TDD during implementation and one combined release suite. Do not
rewrite failed evidence or spend paid calls on broad semantic reruns. Raw
evidence stays protected outside Git.

Authority:
Local implementation is authorized. Ask immediately before the exact
remote/live batch: non-force push, deploy, paid calls, test-only Wazzup,
Zoho/CRM/quotation/PDF, callback, provider canaries, and cleanup. Never touch
real customers, secrets/access, force-push/history, destructive production
state, or unlisted external effects.

Output:
Update Beads, scope ledger, stage summary, handoff, redacted Russian Markdown
report, accepted PDF, and canonical stage-closeout evidence. Explain simply
what was broken, what changed, and how production proved it.

Stop:
Stop on scope/identity drift, an unlisted or unknown side effect, unresolved
P0/P1, destructive/real-customer action, or missing authority. When the
provider-originated canary is ready, ask the owner once to send protected
EN/AR/voice messages; if unavailable, mark it `BLOCKED` and keep the epic open.
