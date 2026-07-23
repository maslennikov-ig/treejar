# Noor latency evidence and safe reduction

You own Beads task `tj-15m.6` in the isolated worktree
`/home/me/code/treejar/.worktrees/tj-av22-stabilization/.worktrees/tj-av22-latency`
on branch `codex/tj-av22-latency`, based on
`codex/tj-av22-stabilization@f76fac2`.

Aim for the outcome in the Beads task and the approved stabilization
specification: establish a repeatable, privacy-safe view of the current local
latency path, identify the dominant remaining phase, and make the narrowest
evidence-backed improvement that does not weaken product, quotation,
escalation, language, or response-quality behavior.

Use your judgment about the most useful measurement shape and implementation.
Treat historical notes in `tj-15m` as evidence and validate current code.
Prefer a small reversible change. A controlled local benchmark can attribute
phases, but do not present mocked timings as live provider latency.

Do not call OpenRouter, Zoho, Wazzup, Telegram, production, staging, or any paid
service. Do not deploy or mutate runtime data. If the remaining bottleneck is
external or can only be proven live, preserve that as an explicit, evidence-led
handoff to `tj-av22.3`.

The write zone is `src/llm/**`, narrowly needed supporting modules,
`src/services/chat.py`, a focused benchmark under `scripts/`, focused tests and
latency docs, and `.codex/stages/tj-av22/artifacts/tj-15m.6.md`.

Avoid unrelated cleanup and broad prompt/model changes. Keep telemetry bounded
and free of message text, phone numbers, credentials, raw tool results, and
other PII.

Use systematic debugging, test-driven development for behavior changes, and
verification-before-completion. Run focused tests plus Ruff, format, and Mypy
for the affected surface. Commit the implementation, merge the current
stabilization branch if needed, create the v3 stage artifact, and report via
`scripts/orchestration/report_child_completion.py`. Leave the worktree for root
review.

## Asset Routing

- Selected skills: `systematic-debugging`, `test-driven-development`,
  `verification-before-completion`, `format-commit-message`.
- Selected agent/persona: built-in latency/reliability worker.
- Catalog candidates: none; installed repository skills and current code are
  sufficient.

## Documentation

Use repository docs, tests, installed dependency source, and Beads evidence
first. For a decisive version-sensitive contract, use authoritative Context7
documentation when available and record what changed the decision.

## Return contract

Return a concise findings-first summary with:

- measured before/after evidence and what it does and does not prove;
- files and behavior changed;
- correctness and quality verification;
- remaining production/provider gate;
- implementation commit, artifact path, and completion event ID.
