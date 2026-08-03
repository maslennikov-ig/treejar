# Orchestrator Handoff

Updated: 2026-08-03
Current branch: `codex/tj-ee5f-remediation`
Accepted stage id: `tj-ee5f`
Current stage status: functional production E2E and client report accepted with
a known external Wazzup status limitation; `tj-ee5f.1` and epic are closed

## Current truth

- Canonical runtime: `https://noor.starec.ai`.
- Owning task `tj-ee5f.1` and epic `tj-ee5f` are closed. `tj-ee5f.5` remains an
  independent blocked follow-up for terminal Wazzup status proof.
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
- The redacted Russian report records the functional PASS and the provider bug
  without relabeling `sent` as delivery. The final six-page PDF was rendered
  and visually inspected: Cyrillic, tables, wrapping, page numbering, and
  section transitions are clean; SHA256 is
  `d2e10f99e9da467617790dd00ac7cdeb91ab499833fb54b2b0eb670df92b751d`.
- Canonical release-level stage closeout passed with artifact validation,
  stage readiness, `git diff --check`, and process verification. Matching
  product evidence reuses the accepted 2690-test gate and independent review.
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
- Beads `tj-ee5f.6-.10` are closed. `.5` remains blocked only for one bounded
  terminal-status retest after Wazzup announces its provider fix.

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

## Accepted external limitation

- On 2026-08-03 the owner relayed Wazzup support's answer: missing
  `delivered/read` callbacks are a provider bug, no workaround currently
  exists, and support will notify the customer after the fix is developed.
- The owner accepted the functional production E2E with this known limitation.
  The evidence remains truthful: existing audits stay `sent`, and the working
  `audit.starec.ai` fan-out is unchanged.
- Broad scenario reruns are not useful while the bug exists because they only
  create additional nonterminal rows.

## Next recommended

Next stage id: `tj-ee5f.5`

Recommended action: wait for Wazzup support's fix notification. Then send one
message through the protected test identity and verify exact
`sent -> delivered -> read` callbacks through the existing audit fan-out and
Noor audit. Do not rerun the full sales suite or change the callback URI.

## Starter prompt for next orchestrator

Use $orchestrator-stage only after Wazzup announces the fix. Resume the bounded
follow-up `tj-ee5f.5`; the accepted sales-remediation scope must not be reopened.

## Approval gates

- Reversible local edits, tests, orchestration docs, and Beads truth updates are
  authorized.
- No production, paid, Wazzup, Zoho, CRM, callback, or deploy action is needed
  for this documentation closeout.
- A future `tj-ee5f.5` live retest requires fresh exact authority after the
  provider announces its fix.
- Force push, history rewrite, real customers, secrets/access changes,
  destructive production work, and unlisted external effects remain excluded.

## Explicit defers

- `tj-ee5f.5` remains blocked on the external Wazzup fix and one future bounded
  terminal-status retest. This is not a functional Noor acceptance blocker.
- Historical test-message outbound audits remain `sent`; they are not delivery
  proof and will not be rewritten.
- Repository-history privacy cleanup remains a separate destructive action.
- Existing unrelated backlog remains separate: `tj-qy7y`, `tj-n8p6`,
  `tj-b93r`, `tj-final27.6`, `tj-gh21`, `tj-2pkk`, `tj-g3f`, `tj-9q0`,
  and `tj-hye`.
