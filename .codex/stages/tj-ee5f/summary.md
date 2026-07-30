# Stage tj-ee5f Summary

Updated: 2026-07-30
Status: in progress; provider canaries captured, voice correction pending deploy
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

`3954857` was delivered to `main` after a fresh fetch and non-force push.
Canonical CI/deploy run `30533112670` succeeded. Production readback confirmed
the exact release, all five services running, and 8/8 API smoke.

Functional production retests S01-S10 now pass the remediated name-gate,
catalog, quote-state, exact-SKU, no-match, memory, Zoho quotation/PDF, and CRM
opportunity behaviors. The combined server snapshot contains 29 turns,
14 provider-reported model turns, 88,329 tokens, USD 0.10085, and 28 tool
calls. S09 and S10 readbacks and safe cleanup are protected outside Git.

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

The local correction gives non-order price/stock inquiries priority over the
product-selection quantity gate. Focused RED/GREEN proof and an independent
delta-review both pass. The product prompt remains unchanged.

## Remaining acceptance

1. Deliver and deploy the reviewed exact-SKU inquiry correction.
2. Ask the owner to repeat only the voice canary, then capture its STT,
   catalog-backed answer, and terminal status.
3. If status remains `sent`, record the exact Wazzup blocker without changing
   the working audit fan-out.
4. Publish the accepted Russian report and inspected PDF, then run canonical
   stage closeout only if every blocker is terminal.

## Explicit defers

- The affected provider-originated voice canary requires one owner-assisted
  retest after deploy. If unavailable, that criterion remains `BLOCKED` and the
  epic stays open.
- Test-message outbound effects still need terminal readback; `sent` is not
  accepted as delivery.
- Repository-history privacy cleanup remains a separate destructive-action
  decision; current-tree redaction remains the local privacy boundary.
