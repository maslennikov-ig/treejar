# Orchestrator Handoff

Updated: 2026-07-30
Current branch: `codex/tj-ee5f-remediation`
Current stage id: `tj-ee5f`
Current stage status: remediation deployed and healthy; a second
Russian voice/name resume correction is accepted for delivery

## Current truth

- Canonical runtime: `https://noor.starec.ai`.
- Owning task: `tj-ee5f.1`; blocking defects `tj-ee5f.5-.10` remain open until
  release-bound production proof.
- Frozen scope: AC-01..AC-30, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- The deployed production release and current `main` are
  `ebc629f0d3a676b5aa51ed3ccabb062a564665ff`.
- Canonical CI/deploy run `30537621859` succeeded. Exact release, five running
  services, and 8/8 API smoke were read back.
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
- The owner-originated voice canary exposed one remaining routing defect:
  a price/stock inquiry containing an exact SKU was treated as an order
  selection and asked for quantity. The local correction routes non-order
  inquiries through the catalog path before product-selection handling.
- After that correction reached production, a Russian voice/name resume
  exposed the same fallback later in the flow. The second local correction
  applies the shared order guard to the legacy fallback, supports Russian
  price/stock morphology and noun-first quote refusal, and routes the saved
  request through exact catalog plus Zoho readback.

## Local proof

- All eleven tracked stage artifacts pass artifact validation.
- Compact orchestrator prompt passes
  `orch-prompts prompt-check --runtime codex --profile gpt-5.6 --kind fallback`
  at 2568 characters.
- Independent dialog review: `APPROVE`.
- Independent production-trust review: initial `6 P1 / 1 P2`; all findings and
  the subsequent judge crash-recovery P1 were corrected. Final delta-review:
  `APPROVE`.
- The voice delta ran one full release suite: `2686 passed`, `19 skipped`; the
  three failures were only the expected handoff-digest drift. After refreshing
  that controlled digest, all three affected tests passed. Ruff, format, Mypy,
  and canonical process verification are green.
- Stage readiness passes. Product prompt and frozen AC-01..AC-30 snapshot are
  unchanged.
- The exact-SKU voice correction has focused RED/GREEN proof and independent
  delta-review verdict `APPROVE`; no product-prompt change was made.
- The second Russian resume correction has focused RED/GREEN proof. Release
  verification passed with `2690 passed`, `19 skipped`, Ruff, format, Mypy, and
  process verification green. Post-review affected tests and static checks pass;
  final independent verdict is `APPROVE` with no P0-P2. Product-prompt growth
  remains zero.

## Production proof and blocker

- Functional production retests S01-S10 pass the remediated behaviors.
- Exact S09 Zoho contact/order/PDF fields and S10 CRM opportunity fields have
  protected readbacks; the test order/deal were terminally cleaned up.
- Combined server facts contain 29 turns, 14 provider-reported model turns,
  88,329 tokens, USD 0.10085, 28 tool calls, and 48 outbound audits.
- Every outbound audit is still `sent`. A narrow smoke on exact release
  `3954857` also stayed `sent` despite a provider message identity.
- The configured Wazzup channel is `active`; `messagesAndStatuses=true` and
  `channelsUpdates=true`.
- `https://audit.starec.ai/webhook` is the intentional single callback and
  fan-out service. Its test ping and safe dual-envelope status probe both
  reached Noor, so the callback URI must not be redirected.
- Across the latest two-day audit window, 639 of 641 outbound rows remain
  `sent`, two are `error`, and none reached `delivered/read`. The remaining
  issue is provider-side terminal status generation/delivery, not Noor routing.
- Owner-originated EN and AR canaries reached Noor and returned catalog-backed
  answers in the requested language without quote collection or escalation.
- The real Wazzup audio canary reached Noor and was transcribed exactly by
  `openai/gpt-4o-mini-transcribe`: 158 input and 21 output tokens,
  USD 0.0003025, 1.184 s. Its assistant response reproduced the exact-SKU
  quantity-gate defect described above.
- The first correction was deployed as `ebc629f`. A Russian voice retest was
  transcribed exactly with 137 input and 28 output tokens at USD 0.000311. Noor
  correctly asked for the name, then misclassified the saved request after the
  owner replied and asked for quantity again.
- All canary outbound audits remain `sent`; both immutable failed captures are
  protected outside Git.

## Next recommended

Next stage id: `tj-ee5f.1`

Recommended action: deliver the accepted second correction after a fresh fetch,
verify the canonical deploy, then rerun only the owner-originated Russian voice
plus name resume. Capture the STT trace, catalog/Zoho-backed answer, and outbound
status. If the answer arrives but remains `sent`, retain the exact evidence as a
Wazzup provider blocker; do not change the working audit fan-out. Do not close
the epic if any required proof is unavailable.

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
- The affected provider-originated Russian voice/name canary needs one
  owner-assisted retest after the correction is deployed.
- Test-message outbound audits still need terminal readback; `sent` is not a
  delivery proof.
- Repository-history privacy cleanup remains a separate destructive action.
- Existing unrelated backlog remains separate: `tj-qy7y`, `tj-n8p6`,
  `tj-b93r`, `tj-final27.6`, `tj-gh21`, `tj-2pkk`, `tj-g3f`, `tj-9q0`,
  and `tj-hye`.
