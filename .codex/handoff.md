# Orchestrator Handoff

Updated: 2026-07-29
Current branch: `codex/tj-ee5f-remediation`
Current stage id: `tj-ee5f`
Current stage status: local release gate complete and independently accepted;
remote delivery, deploy, and production retest remain pending

## Current truth

- Canonical runtime: `https://noor.starec.ai`.
- Owning task: `tj-ee5f.1`; blocking defects `tj-ee5f.5-.10` remain open until
  release-bound production proof.
- Frozen scope: AC-01..AC-30, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- Local remediation branch contains `origin/main@ed8e24d`; unrelated and
  untracked user files in the primary worktree were preserved.
- Accepted local release head is `36b8985`.
- The failed pre-remediation evidence is bound to release `ed8e24d`; the exact
  post-remediation runtime SHA has not been deployed or read back yet.

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

- All eleven tracked stage artifacts pass artifact validation.
- Compact orchestrator prompt passes
  `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind fallback`
  at 2568 characters.
- Independent dialog review: `APPROVE`.
- Independent production-trust review: initial `6 P1 / 1 P2`; all findings and
  the subsequent judge crash-recovery P1 were corrected. Final delta-review:
  `APPROVE`.
- The single final release gate passed with `2464 passed`, `19 skipped`, Ruff,
  format, Mypy, and canonical process verification green.
- Stage readiness passes. Product prompt and frozen AC-01..AC-30 snapshot are
  unchanged.

## Next recommended

Next stage id: `tj-ee5f.1`

Recommended action: fresh fetch, prove `origin/main` is an ancestor of the
accepted head, non-force deliver to `main`, wait for canonical CI/deploy, and
read back the exact release before one bounded production acceptance set.

At provider-canary time, pause once and ask the owner to send EN, AR, and voice
from the protected test WhatsApp. Do not close the epic if that proof is
unavailable.

## Starter prompt for next orchestrator

Use $orchestrator-stage with the compact prompt in
`.codex/stages/tj-ee5f/remediation-orchestrator-prompt.md`.

## Approval gates

- Reversible local edits, tests, orchestration docs, and Beads truth updates are
  authorized.
- Current owner authority covers fresh fetch, safe non-force push, canonical
  deploy/readback, paid test-only model/voice calls, protected test Wazzup,
  test-only Zoho/CRM/quotation/PDF/callback/readbacks, and safe cleanup.
- Force push, history rewrite, real customers, secrets/access changes,
  destructive production work, and unlisted external effects remain excluded.

## Explicit defers

- Production acceptance, report/PDF delivery, Beads closure, and canonical
  stage closeout remain pending.
- Provider-originated EN/AR/voice canaries remain an owner-assisted gate.
- Repository-history privacy cleanup remains a separate destructive action.
- Existing unrelated backlog remains separate: `tj-qy7y`, `tj-n8p6`,
  `tj-b93r`, `tj-final27.6`, `tj-gh21`, `tj-2pkk`, `tj-g3f`, `tj-9q0`,
  and `tj-hye`.
