# Stage tj-ee5f Summary

Updated: 2026-08-03
Status: accepted with a known external Wazzup limitation
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
- The redacted Russian client report was rendered as a five-page blocked draft
  PDF and visually inspected at full-page resolution. Cyrillic text, tables,
  page numbering, wrapping, and section transitions are clean. The PDF remains
  protected outside Git. The final report is accepted after the owner approved
  the provider limitation; the current closeout renders and inspects the final
  PDF without changing production evidence.
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

All 48 outbound audits remain `sent`, not terminal. A narrow smoke on `3954857`
reproduced the same state despite a provider message identity. The configured
Wazzup channel is active and subscribed to message/status callbacks.
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
remains blocked because the other historical outbound effects still lack
terminal provider or recipient readback.

Beads `tj-ee5f.1` is closed under the owner-approved functional
known-limitation disposition. Completion audit keeps epic `tj-ee5f` and its
follow-up `tj-ee5f.5` `BLOCKED`: the original epic may close only after Wazzup
announces its fix and the bounded terminal-status retest passes.

## Accepted limitation and closeout decision

On 2026-08-03 the owner relayed Wazzup support's conclusion: the missing
`delivered/read` callbacks are a provider bug, there is no current workaround,
and Wazzup will notify the customer after its fix is developed. The owner
accepted the functional production result with this known limitation.

The stage therefore closes its functional E2E boundary without claiming
terminal status that was not observed. `sent` remains nonterminal, the working
`audit.starec.ai` callback/fan-out remains unchanged, and `tj-ee5f.5` remains
a blocked child follow-up under the epic. After provider notification it requires
one protected test message and exact `sent -> delivered -> read` webhook/audit
readback; broad commercial scenario reruns are unnecessary.

This accepted functional stage is not the final epic closure. The known bug is
an explicit defer, not full proof, so the epic remains open until `tj-ee5f.5`
records terminal evidence.

The historical 23.9/30 table remains the immutable pre-correction score. A new
aggregate score is not invented: final acceptance combines the release-bound
S01-S10 defect retests, provider EN/AR/voice canaries, exact Zoho/PDF/CRM
readbacks and cleanup, the 2690-test release gate, and independent `APPROVE`.
The owner explicitly accepts the absent post-correction aggregate as part of
the same provider-limited closeout.

The final Russian report is rendered at
`output/pdf/noor-live-sales-tool-e2e-remediation-2026-07-29.pdf`: six A4 pages,
clean Cyrillic, tables, wrapping, page numbers, and section transitions. Visual
inspection found no clipping or overlap. SHA256:
`d2e10f99e9da467617790dd00ac7cdeb91ab499833fb54b2b0eb670df92b751d`.

docs-reviewed: updated - client report, stage summary, handoff, and Beads truth
now record the owner-approved provider limitation and exact retest trigger.

project-index: reviewed-no-change - no stable repository entrypoint changed.

graph-reviewed: no-change-needed - Graphify is not configured and this is a
docs-only closeout decision.

Canonical stage closeout passed at release level using the risk-selected
`targeted_commands` group. The unchanged exact product evidence reuses the
accepted 2690-test release gate and independent review; the docs-only decision
was freshly checked by artifact validation, `git diff --check`, stage readiness,
and process verification.

## Explicit defers

- `tj-ee5f.5`: Wazzup support must first ship the callback fix; then one bounded
  protected-message retest must prove terminal webhook/audit transitions.
- Historical test-message outbound effects remain `sent`; they are not
  reclassified as delivered or read.
- Repository-history privacy cleanup remains a separate destructive-action
  decision; current-tree redaction remains the local privacy boundary.
