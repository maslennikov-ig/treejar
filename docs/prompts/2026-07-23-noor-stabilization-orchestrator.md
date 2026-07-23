# Noor Stabilization Launcher

Target: Codex gpt-5.6 root orchestrator in `/home/me/code/treejar`.

Entrypoint: use `orchestrator-stage` to continue Beads epic `tj-av22`.

Goal: leave Noor secure, reliable, observable, verified, and ready for supported
operation.

Success criteria:
- technical findings are resolved or tied to a specific external blocker;
- relevant regression tests and canonical gates pass;
- Beads, stage records, and durable docs reflect the final state;
- approved production work has release, verification, and rollback evidence.

Context: read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, the
epic, and its linked specification and implementation plan.

Working approach: choose the execution shape that best fits current evidence.
Visible subagents are authorized when delegation is useful; the plan's
decomposition is optional guidance. Keep delegated prompts concise and in
English. Preserve unrelated files and follow repository approval boundaries.

Output: the completed outcome, verification evidence, remaining blockers, and
the next approval decision if one is needed.

Stop: ask before deploy or production mutation, real Telegram/WhatsApp traffic,
reconciliation apply, credential or scope changes, destructive cleanup, or an
ambiguous API compatibility decision.
