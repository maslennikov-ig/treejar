# Orchestrator Handoff

Updated: 2026-07-29
Current branch: `codex/tj-ee5f-remediation`
Current stage id: `tj-ee5f`
Current stage status: local remediation integrated and independently accepted;
remote delivery, deploy, and production retest remain pending

## Current truth

- Canonical runtime: `https://noor.starec.ai`.
- Owning task: `tj-ee5f.1`; blocking defects `tj-ee5f.5-.10` remain open until
  release-bound production proof.
- Frozen scope: AC-01..AC-30, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- Local remediation branch is based on `main@844a394`; unrelated and untracked
  user files in the primary worktree were preserved.
- Final local remediation commit is `fc1e7f8`.
- The last known production identity in repository evidence is release
  `0dd9615`; it has not been refreshed in this local-only session.

## Local remediation

- Trusted E2E now uses authority-bound HTTP/SSH transports and derives
  transcripts, tool traces, timings, costs, readbacks, and side effects from
  production facts. Runtime endpoint/SSH/commands and post-dispatch
  reconciliation are fail-closed.
- Name-gate intent, EN/AR catalog/no-match routing, quote consent/state,
  exact-SKU behavior, customer-field parsing, Zoho payloads, operation-scoped
  quote idempotency, and exactly-once audited PDF dispatch are corrected.
- Voice uses OpenRouter's dedicated STT endpoint, validates actual audio format,
  rolls out `VOICE_TRANSCRIPTION_MODEL` safely with the legacy alias, and keeps
  a bounded persisted usage/cost/timing trace.
- Exact captured scenario wording remains in tests only. Product system-prompt
  growth is zero.

## Local proof

- Three focused stream artifacts are registered and pass artifact validation.
- Compact orchestrator prompt passes
  `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind fallback`.
- Independent combined review: initial `0 P0 / 4 P1`; all four corrected.
- Independent delta re-review: `ACCEPT`, no P0/P1. Its final P2 on voice trace
  bounds was fixed with focused RED/GREEN proof.
- Full Ruff, format, and Mypy gates pass.
- The one full test run produced `2295 passed`, `19 skipped`, and `18 failed`.
  Those failures were traced to the isolated worktree's absent offline frontend
  dependencies and six affected contracts. Every failed node plus adjacent
  trust/runtime coverage now passes after focused fixes; the broad suite was
  not repeated, as required by the paid/release rerun policy.
- Canonical process verification passes on the final orchestration state.

## Next recommended

Next stage id: `tj-ee5f.1`

Recommended action: obtain current authority for the exact remote/live batch:
fresh fetch, safe non-force delivery, canonical deploy/readback, paid test-only
models, protected Wazzup/WhatsApp, test-only Zoho quotation/PDF and cleanup.

At provider-canary time, pause once and ask the owner to send EN, AR, and voice
from the protected test WhatsApp. Do not close the epic if that proof is
unavailable.

## Starter prompt for next orchestrator

Use $orchestrator-stage with the compact prompt in
`.codex/stages/tj-ee5f/remediation-orchestrator-prompt.md`.

## Approval gates

- Reversible local edits, tests, orchestration docs, and Beads truth updates are
  authorized.
- No remote/live action was performed in this remediation session.
- Ask immediately before the exact fetch/push/deploy/paid/provider/production
  batch. Force push, history rewrite, real customers, secrets/access changes,
  and destructive production work remain excluded.

## Explicit defers

- Production acceptance, report/PDF delivery, Beads closure, and canonical
  stage closeout remain pending.
- Provider-originated EN/AR/voice canaries remain an owner-assisted gate.
- Repository-history privacy cleanup remains a separate destructive action.
- Existing unrelated backlog remains separate: `tj-qy7y`, `tj-n8p6`,
  `tj-b93r`, `tj-final27.6`, `tj-gh21`, `tj-2pkk`, `tj-g3f`, `tj-9q0`,
  and `tj-hye`.
