# Orchestrator Handoff

Updated: 2026-07-29
Current branch: `codex/tj-ee5f-remediation`
Current stage id: `tj-ee5f`
Current stage status: remediation deployed; S05 typed-state fix verified on
production, but final acceptance remains blocked

## Current truth

- Canonical runtime: `https://noor.starec.ai`.
- Owning task: `tj-ee5f.1`; blocking defects `tj-ee5f.5-.10` remain open until
  release-bound production proof.
- Frozen scope: AC-01..AC-30, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- The deployed production code release is
  `06b6087844ff4e650aa0dbfe6c50b2b3c8bfa744`; later `main` changes are
  orchestration/report documentation only.
- Canonical CI/deploy run `30489291826` succeeded. Exact release, health,
  Redis, database, five running services, and 8/8 API smoke were read back.
- Unrelated and untracked user files in the primary worktree were preserved.
- Failed and incomplete production attempts remain immutable outside Git.

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
- Quote routing no longer infers sent/detail state from assistant prose.
  Explicit no-quote instructions interrupt typed quote-detail collection and
  return the conversation to product selection.

## Local proof

- All eleven tracked stage artifacts pass artifact validation.
- Compact orchestrator prompt passes
  `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind fallback`
  at 2568 characters.
- Independent dialog review: `APPROVE`.
- Independent production-trust review: initial `6 P1 / 1 P2`; all findings and
  the subsequent judge crash-recovery P1 were corrected. Final delta-review:
  `APPROVE`.
- The latest final release gate passed with `2559 passed`, `19 skipped`, Ruff,
  format, Mypy, and canonical process verification green.
- Stage readiness passes. Product prompt and frozen AC-01..AC-30 snapshot are
  unchanged.

## Production proof and blocker

- S05 no longer enters quote collection after a quote offer or an explicit
  refusal. Production readback shows `active_flow=product_selection`,
  `quote_sent=false`, `post_quotation_status=null`, and
  `quotation_hold=yes`.
- Name gate, catalog consultation, catalog tool traces, duration, and
  provider-reported cost were collected from production facts.
- The final S05 answer did not complete. Bounded retries were exhausted after
  OpenRouter returned `finish_reason=error`; the current Pydantic AI client
  rejects that provider response as `UnexpectedModelBehavior`.
- A complete final-release set of ten text scenarios was therefore not run.
  Provider-originated EN/AR/voice canaries and terminal outbound-effect
  readbacks are still missing.

## Next recommended

Next stage id: `tj-ee5f.1`

Recommended action: handle the OpenRouter `finish_reason=error` compatibility
path without prompt growth, then rerun only S05. If it completes, run the
remaining final-release acceptance set and reconcile every side effect.
Provider-originated EN/AR/voice still requires the owner's protected test
WhatsApp. Do not close the epic if any proof is unavailable.

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

- Complete production acceptance, accepted report/PDF, Beads closure, and
  canonical stage closeout remain pending.
- OpenRouter `finish_reason=error` compatibility is a release-bound runtime
  blocker; no more paid retries should run before it is resolved.
- Provider-originated EN/AR/voice canaries remain an owner-assisted gate.
- Test-message outbound audits still need terminal readback or an explicitly
  accepted retention disposition.
- Repository-history privacy cleanup remains a separate destructive action.
- Existing unrelated backlog remains separate: `tj-qy7y`, `tj-n8p6`,
  `tj-b93r`, `tj-final27.6`, `tj-gh21`, `tj-2pkk`, `tj-g3f`, `tj-9q0`,
  and `tj-hye`.
