# Stage tj-ee5f Summary

Updated: 2026-07-30
Status: blocked; functional remediation accepted, Wazzup terminal status missing
Branch: `codex/tj-ee5f-remediation`
Beads owner: `tj-ee5f.1`

## Boundary

This remains one release-level acceptance stage. It preserves the frozen
AC-01..AC-30 snapshot and digest
`12f0cc9c8c038f366096162dbac51e90746f38efb93b9f9feb29f1ea507cf732`.
No criterion was added, removed, or renumbered.

## Integrated remediation streams

- `tj-ee5f.5`: real HTTP/SSH production transport, protected runtime/readback
  authority, derived duration/cost/tool/side-effect facts, and causal
  reconciliation after dispatch.
- `tj-ee5f.6-.9`: typed name-gate intent, EN/AR catalog routing, explicit quote
  consent and interruptions, exact-SKU behavior, safe customer-field parsing,
  typed Zoho payloads, inbound-scoped quote idempotency, and exactly-once PDF
  delivery through outbound audit.
- `tj-ee5f.10`: dedicated OpenRouter STT endpoint, MIME plus magic-byte format
  validation, new/legacy config rollout, distinct-message fallback identity,
  and bounded persisted provider usage/cost/timing trace.

The accepted specification, plan, and compact orchestrator prompt are tracked
under `docs/superpowers/` and `.codex/stages/tj-ee5f/`.

## Verification

- Every stream recorded focused RED/GREEN proof in its validated artifact.
- Prompt validation passes for Codex gpt-5.6 fallback.
- Captured S01-S11 phrases were not added to production logic.
- `src/llm/prompts.py` has no delta; net product system-prompt growth is zero.
- Independent dialog review verdict is `APPROVE`.
- Independent production-trust review first found six P1 and one P2 issue.
  Provider-bound request/receipt, telemetry, reconciliation, identity, Mypy,
  and crash-recovery corrections closed every finding; final delta-review
  verdict is `APPROVE`.
- The voice delta ran one full release suite: `2686 passed`, `19 skipped`; the
  three failures were only the expected handoff-digest drift. After refreshing
  that controlled digest, all three affected tests passed. Ruff, format, Mypy,
  and canonical process verification are green.
- All eleven tracked stage artifacts validate, stage readiness passes, and the
  remediation artifacts remain accepted.
- Independent review of the final quote-state delta is `APPROVE`, with no
  P0/P1. `src/llm/prompts.py` remains unchanged.

## External state

`a2f245c` was delivered to `main` after a fresh fetch and non-force push.
Canonical CI/deploy run `30540774784` succeeded. Production readback confirmed
the exact release, all five services running, healthy Redis/database, and 8/8
API smoke.

Functional production retests S01-S10 now pass the remediated name-gate,
catalog, quote-state, exact-SKU, no-match, memory, Zoho quotation/PDF, and CRM
opportunity behaviors. The combined server snapshot contains 29 turns,
14 provider-reported model turns, 88,329 tokens, USD 0.10085, and 28 tool
calls. S09 and S10 readbacks and safe cleanup are protected outside Git.
The owner later supplied the S09 PDF received in the protected WhatsApp around
12:00 Europe/Moscow. Its normalized text and rendered page match the protected
S09 quotation exactly, so quotation delivery is independently accepted even
though its provider audit still says `sent`.

The trusted final observation remains incomplete because all 48 outbound
audits are `sent`, not terminal. A narrow smoke on `3954857` reproduced the
same state despite a provider message identity. The configured Wazzup channel
is active and subscribed to message/status callbacks.
`https://audit.starec.ai/webhook` is the intentional single callback/fan-out:
its test ping and a safe probe containing both supported status envelopes
reached Noor. No callback change is needed. In the latest two-day audit window,
639 of 641 outbound rows remain `sent`, two are `error`, and none reached
`delivered/read`.

The owner-originated EN and AR canaries reached Noor and returned relevant
catalog-backed answers in the requested language. The real Wazzup voice canary
was transcribed exactly by `openai/gpt-4o-mini-transcribe` with 158 input and
21 output tokens, USD 0.0003025, and 1.184 s request duration. It exposed one
remaining semantic defect: an exact-SKU price/stock inquiry with an explicit
quote refusal was interpreted as order selection and prompted for quantity.

That first correction was deployed as `ebc629f`. A Russian owner-originated
voice retest was then transcribed exactly with 137 input and 28 output tokens
at USD 0.000311. The first response correctly asked for the customer's name,
but the saved request was misclassified after the owner replied with the name:
Noor again asked for quantity instead of reading exact catalog price and stock.
The immutable failed capture is protected outside Git.

The second correction makes the shared order guard recognize Russian
price/stock morphology, recognizes quote refusal when the quote noun precedes
the negation, applies the shared guard to the legacy missing-quantity fallback,
and routes the saved Russian request through catalog plus Zoho readback.
Focused RED reproduced `product-quantity-clarify`; focused GREEN returns the
exact catalog variant, price, and stock without quantity or quote collection.
The one full release gate passed with `2690 passed`, `19 skipped`, Ruff,
format, Mypy, and process verification green. Independent review then found
Russian morphology, clause-boundary, and false-positive gaps; the bounded
correction wave passed its affected tests and static gates. Final independent
verdict is `APPROVE` with no remaining P0-P2. The product prompt remains
unchanged.

The clean owner-originated Russian voice/name retest on `a2f245c` is accepted:
the dedicated STT transcribed the request exactly with 163 input and 28 output
tokens, USD 0.00034375, and 1.043 s request duration. After the owner supplied
the name, Noor resumed the saved intent, selected only `CH 616 NEW black`, and
returned live Zoho price AED 295 and stock 41. It did not ask for quantity,
offer alternatives or quotation, or escalate. Wazzup accepted both responses,
but both audits remain `sent`.

Beads `tj-ee5f.6-.10` are closed on release-bound proof. The received S09 PDF
belongs to the earlier `f283a22` quotation run, not to the final `a2f245c`
voice/name canary; that final request explicitly declined a quotation. `.5`
remains open because the other historical outbound effects still lack
terminal provider or recipient readback.

## Remaining acceptance

1. Obtain terminal provider or exact recipient readback for the remaining
   historical test-only outbound messages; do not reinterpret `sent` as
   delivery.
2. Keep the intentional `audit.starec.ai` callback/fan-out unchanged.
3. Render and inspect the final Russian report PDF and run canonical closeout
   only after terminal reconciliation succeeds.

## Explicit defers

- Historical test-message outbound effects not covered by the accepted S09 PDF
  and final-response recipient evidence still need terminal readback; `sent`
  is not accepted as delivery.
- Repository-history privacy cleanup remains a separate destructive-action
  decision; current-tree redaction remains the local privacy boundary.
