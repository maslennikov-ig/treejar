# Orchestrator Handoff

Updated: 2026-07-30
Current branch: `codex/tj-ee5f-remediation`
Current stage id: `tj-ee5f`
Current stage status: functional remediation accepted on production; blocked
only on terminal Wazzup delivery/read evidence

## Current truth

- Canonical runtime: `https://noor.starec.ai`.
- Owning task: `tj-ee5f.1`; only blocking defect `tj-ee5f.5` remains open for
  terminal side-effect reconciliation.
- Frozen scope: AC-01..AC-30, digest
  `12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
- The last deployed, production-tested product release is
  `a2f245cde301457ef19abda221732368986d7f9d`; later documentation-only commits
  do not change the runtime.
- Canonical CI/deploy run `30540774784` succeeded. Exact release, five running
  services, healthy Redis/database, and 8/8 API smoke were read back.
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
- The redacted Russian report has a protected five-page blocked-draft PDF.
  Full-page visual inspection confirmed clean Cyrillic rendering, tables,
  wrapping, page numbering, and section transitions. It remains a draft until
  terminal Wazzup reconciliation is available.
- The exact-SKU voice correction has focused RED/GREEN proof and independent
  delta-review verdict `APPROVE`; no product-prompt change was made.
- The second Russian resume correction has focused RED/GREEN proof. Release
  verification passed with `2690 passed`, `19 skipped`, Ruff, format, Mypy, and
  process verification green. Post-review affected tests and static checks pass;
  final independent verdict is `APPROVE` with no P0-P2. Product-prompt growth
  remains zero.
- The exact-release owner retest passed: dedicated STT transcribed the Russian
  voice request exactly (163 input, 28 output tokens, USD 0.00034375, 1.043 s),
  name gate resumed the saved intent, and Noor returned only `CH 616 NEW black`
  with live Zoho price AED 295 and stock 41. No quantity, alternatives, quote,
  or escalation path was entered.
- Beads `tj-ee5f.6-.10` are closed. `.5` remains open only for trusted terminal
  reconciliation of the other historical outbound effects.

## Production proof and blocker

- Functional production retests S01-S10 pass the remediated behaviors.
- Exact S09 Zoho contact/order/PDF fields and S10 CRM opportunity fields have
  protected readbacks; the test order/deal were terminally cleaned up.
- The owner supplied the S09 PDF received in the protected WhatsApp around
  12:00 Europe/Moscow. Normalized text and pixel rendering match the protected
  S09 PDF exactly. This proves quotation delivery for `f283a22`; it is not
  attributed to the later no-quotation canary on `a2f245c`.
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
- The corrected owner retest on `a2f245c` passed functionally with exact STT,
  saved-intent resume and catalog/Zoho answer. Wazzup returned `201 Created` and
  provider identities for both replies, but both new audits remain `sent`.
- All canary outbound audits remain `sent`; failed and successful raw captures
  are protected outside Git.

## Next recommended

Next stage id: `tj-ee5f.1`

Recommended action: keep the accepted release unchanged and obtain terminal
provider or exact recipient readback for the remaining historical outbound
messages. Do not change the working audit fan-out or reinterpret `sent` as
delivery. After terminal reconciliation, render/inspect the Russian report PDF
and run canonical stage closeout.

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

- Terminal production acceptance, accepted report PDF, Beads `.5/.1` and epic
  closure, and canonical stage closeout remain pending.
- Historical test-message outbound audits not covered by the accepted
  recipient evidence still need terminal readback; `sent` is not a delivery
  proof.
- Repository-history privacy cleanup remains a separate destructive action.
- Existing unrelated backlog remains separate: `tj-qy7y`, `tj-n8p6`,
  `tj-b93r`, `tj-final27.6`, `tj-gh21`, `tj-2pkk`, `tj-g3f`, `tj-9q0`,
  and `tj-hye`.
