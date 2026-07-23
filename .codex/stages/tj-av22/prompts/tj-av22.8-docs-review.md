Target: Codex `docs_reviewer` in
`/home/me/code/treejar/.worktrees/tj-av22-docs-review`.

Goal: determine whether Noor's durable documentation accurately describes the
integrated stabilization behavior and its release, rollback, recovery, and
approval boundaries.

Success criteria:
- API removals, health behavior, inbound retry/quarantine privacy, monitoring,
  maintenance, escalation reconciliation, and latency evidence are checked
  against current code;
- stale or missing documentation is reported with exact file references and a
  concise suggested correction;
- transient history is not proposed for durable docs;
- one valid artifact gives `updated`, `no-change-needed`, or `needs-work`.

Context: read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`,
the stabilization spec/plan, `docs/operations-runbook.md`, `docs/admin-guide.md`,
`docs/dev-guide.md`, `README.md`, Beads `tj-av22` and `tj-av22.8`, then inspect
the integrated diff from `89f9a560071302d16f53704870e7a508e9d05f28`.

Constraints: this is a read-only documentation review. Choose the review path
from the changed contracts. Do not edit project files, docs, Beads, or runtime
state. The only allowed write is the artifact below. Do not contact production
or external services.

Asset Routing:
- selected skills: verification-before-completion
- selected agents/personas: docs_reviewer
- catalog candidates: none; repository docs and code are authoritative

Documentation: no dependency research is expected. If a version-sensitive
external fact becomes necessary, cite first-party documentation in the
artifact; otherwise stay repository-local.

Output: write only
`.codex/stages/tj-av22/artifacts/tj-av22.8.md`, with artifact frontmatter,
coverage, findings, exact suggested edits, documentation verdict,
`docs-reviewed`, and `graph-reviewed`. Commit the artifact and report completion
with `scripts/orchestration/report_child_completion.py`.

Stop: report uncertainty when product policy, production state, or an external
owner is needed; do not guess or alter documentation.
