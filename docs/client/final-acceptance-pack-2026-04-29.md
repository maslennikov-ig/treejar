# Treejar Final Acceptance Pack

Date: 2026-04-29
Stage: `tj-final27`
Task: `tj-final27.9`
Runtime target: `https://noor.starec.ai`

This pack is the client-review record refreshed for final delivery on 2026-08-14. The approved controlled final E2E subset from 2026-04-29 passed; the current release refresh, measured opening round, deployment and final controlled E2E are recorded below.

## Current Measurement Boundary — Read This First

- The isolated opening stand charges **eight rules out of fifteen**. The other
  **seven rules are unreachable on the first turn**; this opening result is not
  presented as full fifteen-rule coverage.
- The seven are rules 6, 10, 11, 12, 13, 14 and 15: they require a project or
  multi-family state, a later turn, or a tool-filled commercial next step.
- Deal outcomes are visible in the supplied channel data for only **192 of 1400
  dialogues**. The evidence supports claims about observable assistant behavior,
  not conversion, revenue, deal size, close rate, or causal sales impact.
- Every measured number in the final refresh is paired with its actual ceiling
  and the deployed `release_sha`; a raw total is not used to hide applicability.

## Referral Scope Exclusion

«Реферальная программа в объём текущей сдачи не входит. Механика
реализована и отключена; запуск выполняется отдельным решением заказчика
после приёмки.»

## Final Refresh — 2026-08-14

The refreshed code produces the pinned opening line `Chairs from AED 139,
desks and workstations from AED 58.` The price is an executable offer for one
customer because each winning row has a non-zero price and at least one unit in
stock. Whenever a quoted row has fewer than five units, the reply says plainly
that stock is limited and that a larger quantity may require another option and
price.

The protected preflight found 19 priced openings and one correctly withheld
anchor. The blind root reading covered all 20 openings. No second reader was
used. The rule result, with the attainable mean ceiling beside each score and
the paired delta against `tj-final27.18-round-20260814b`, was:

| Rule | New score / ceiling | Delta |
|---|---:|---:|
| 1 | 2.00 / 2.00 | 0.00 |
| 2 | 1.85 / 2.00 | 0.00 |
| 3 | 2.00 / 2.00 | 0.00 |
| 4 | 2.00 / 2.00 | +0.05 |
| 5 | 1.75 / 1.95 | -0.05 |
| 7 | 2.00 / 2.00 | 0.00 |
| 8 (`n=6`) | 1.67 / 2.00 | -0.33 |
| 9 (`n=6`) | 2.00 / 2.00 | 0.00 |

The raw paired delta was `-0.10` per opening (95% interval `-0.25` to `0.00`)
and the weighted delta was `-0.14` (95% interval `-0.35` to `0.00`). Both are
inside the measured reader gap of 2.0 points per opening and are not presented
as evidence of either improvement or regression. Twelve of 20 openings reached
their own ceiling. The two ceiling bands were 9.6 for 14 openings (mean 9.2)
and 30.0 for six openings (mean 29.1).

The result is an **accepted round**: all 20 responses were non-empty, all 20
root readings were valid, all 20 customer-facing replies stayed in the language
selected for that turn, and there were zero critical failures. Every delivered
reply also contained exactly one literal question mark. The price anchor
introduced no contradiction with quoted rows, and every reply that owed a
low-stock warning carried it before asking the customer to continue.

Named defect movement:

- New: after removal of the second language, dialog 293 contains no substantive
  need discovery beyond the name question; dialog 28 redirects recruitment and
  then continues role discovery; dialogs 442 and 819 each stack two discovery
  subjects into one grammatical question.
- Gone: the English-turn Arabic narrative and its critical failure on dialog
  293; the two-literal-question-mark greeting form; the missing delivery and
  assembly acknowledgement on dialog 819.
- Unchanged: wrong-family end-table wording on dialog 436; product-led
  discovery on dialogs 420 and 1000; internal catalog machinery wording on
  dialog 1067. The unresolved-referent cases on dialogs 366 and 815 remain
  scored under the existing reading convention and are not adopted as defects.

The protected artifact is
`.git/codex-orchestration/corpus-bridge/tj-08ve-round-20260814c`.
Generation used exactly 20 paid Luna calls for `$0.006586`, below the authorized
`$0.05` cap. There were no repair or scoring calls. The blind root reading was
free.

### Current deployment and controlled E2E

GitHub Actions run `31805222594` deployed
`main@f5be6a26b292b81da1288ca3c394ceac21eb57a3`. Public API smoke passed 8/8,
and `/api/v1/health` returned that exact release SHA.

An audit of that release then found one customer-visible defect in the same
outbound boundary and it was repaired before handoff. The boundary had judged
an Arabic reply by its share of Arabic letters; our catalog is named in Latin
script, so a true Arabic answer that named several products, quoted a price or
carried a link was replaced by a fixed sentence and the customer lost the
answer. The boundary now decides per side: an Arabic reply keeps the customer's
language when it carries Arabic of its own, an English reply still may not
carry Arabic script, and a first turn that loses its only question to the guard
regains one work-led question. Replaying the accepted round's shipped output
through the repaired boundary, at no cost, returned 18 of the 20 replies
byte-identical; dialogs 293 and 1291 each gained one work-led question, every
reply still carried exactly one question mark, and no reply changed language.
GitHub Actions run `31811997412` deployed that repair as
`main@d30b2d918f75353b3ad75438b29b409a2776cdca`, and `/api/v1/health` returned
that exact release SHA.

The production catalog is live data and currently yields a rounded opening
floor of AED 99 / 58; the protected acceptance snapshot remains AED 139 / 58.
Owner decision 2026-08-14 permits whole-AED rounding in a `from` price. The
runtime uses the same rounded amounts in the customer line and its grounding
evidence, so the approved rounding cannot trigger a false price rejection.

Controlled readback recorded only identifiers and digests, never message bodies:

- Anchor conversation `5decbb27-cf64-4ff2-bc09-9ca6d80a4af3`, digest
  `1536b1aa3fcab6c03b6fbd402aa165ff6ff9ad8233279131328fd21bbc820805`:
  exact live-catalog anchor, limited-stock disclosure and volume-price caveat
  were present; escalation status was `none`.
- Literal R04 conversation `8605eba9-1aeb-4cd5-a0ac-9c58eaac2cb9`, digest
  `eda9598c59292866fb9b411a0ce1cab90f29a3b5b65b7fe9b6f8392cca752577`:
  `verified-opening-catalog` supplied SKU and price, avoided a form, and asked
  exactly one question; escalation status was `none`.
- Final aggregate: zero pending synthetic conversations and zero pending
  escalation rows. Two pre-fix synthetic escalation rows were resolved.

Post-deploy checks used synthetic values and recorded no customer message body.
The shipped greeting guard returned one literal question mark and no
second-language letters. The logging readback found zero complete access URLs,
zero query-bearing URLs and one intentionally redacted URL marker.

`tj-final27.19` is closed by a record-editing filter attached to every active
application handler. It removes HTTP(S) paths, query strings and userinfo before
any formatter writes a record, so the protection also covers a future HTTP
client using a different logger. The audit additionally removed Wazzup upload
URL logging and catalog image URL/exception logging because signed media URLs
can carry access. Owner decision 2026-08-14: the Telegram token is not rotated;
the observed copy never left standard output on the owner-controlled server,
where the same value already exists in `.env`, and no external log collector,
CI call, Git record, document or artifact contains it. `tj-final27.20` is also
closed by the final outbound guard that folds the name question into the single
substantive question.

Historical refresh note, 2026-04-30: the snapshot was promoted into the repo
after later narrow follow-ups were delivered. Production runtime at that time
was `main@354015280c8f8d39b538bbaba769e70d29d1c6b2`; those deployments addressed
the generic objection/retention/off-catalog fallback quality risk
(`tj-final27.11`), commercial-offer/proposal escalation routing (`tj-jy5i`),
and payment-reminder provider reuse (`tj-final27.13`). The 2026-04-29 final E2E
evidence remains tied to the runtime recorded below.

## Source Evidence

- Contract scope: `docs/tz.md`, `docs/03-ai-agent-requirements.md`, `docs/response-to-client-2026-02-17.md`.
- Final delivery plan: `docs/plans/2026-04-27-final-delivery-completion.md`.
- Delivered stage evidence: `.codex/stages/tj-ruue/summary.md`, `.codex/stages/tj-e2e26/summary.md`, `.codex/stages/tj-prl26/summary.md`, `.codex/stages/tj-final27/summary.md`.
- Final27 evidence artifacts: `.codex/stages/tj-final27/artifacts/tj-final27.1.md`, `.codex/stages/tj-final27/artifacts/tj-final27.2.md`, `.codex/stages/tj-final27/artifacts/tj-final27.3.md`, `.codex/stages/tj-final27/artifacts/tj-z911.md`.
- Controlled runbook for the remaining final E2E: `docs/testing/final-controlled-e2e-runbook-2026-04-29.md`.

## What Was Promised

The accepted scope describes an AI sales assistant for office furniture sales through WhatsApp, with English and Arabic dialogue, product consultation, catalog-grounded answers, Zoho CRM/Inventory integration, quotation/SaleOrder flow, manager handoff, Telegram notifications, admin/operator surfaces, quality/reporting, referral and feedback capabilities, and production deployment.

Commercial and operational promises include:

- WhatsApp/Wazzup inbound and outbound messaging with product consultation.
- Treejar Catalog API as the customer-facing product source of truth.
- Zoho CRM contact/deal handling, source attribution, and returning-customer context.
- Zoho Inventory operational checks for quotation/SaleOrder and related business process state.
- PDF quotation flow after exact `SKU + quantity` confirmation, with direct customer delivery.
- Order status answers for approval/rejection/payment/delivery state.
- Manager handoff and Telegram operational notifications.
- Admin dashboard, prompt/config controls, metrics, QA/reporting, and operator visibility.
- Payment follow-up, post-delivery feedback, referrals, recommendations, and nonfunctional readiness.
- Final E2E and acceptance evidence before formal closure.

## What Is Done

Current deployed baseline is `main@d30b2d918f75353b3ad75438b29b409a2776cdca`, delivered by GitHub Actions run `31811997412`, with runtime `.release-sha` matching and `/api/v1/health` OK. The measured round above was generated on `main@f5be6a26b292b81da1288ca3c394ceac21eb57a3`, and the difference between the two is the audit repair described there. The approved historical `tj-final27.9` E2E evidence below was collected earlier on `main@090e318d06662eb4a4c4f2247eb01bd1ed317b94`.

Delivered product and runtime evidence:

- `tj-ruue`: OpenRouter/LLM safety, cost controls, AI Quality Controls disabled-safe defaults, admin controls, model routing, and rollout docs were delivered. CI/deploy and post-deploy smoke passed.
- `tj-e2e26`: production E2E hardening delivered auth protection for conversation APIs, exact phone filtering, order-status copy after approve/reject, Telegram private manager replies, outbound Wazzup audit/idempotency, media/caption audit visibility, and zero pending synthetic conversations after scoped production rechecks.
- `tj-prl26`: pre-launch readiness E2E passed after the SKU masking blocker was fixed and deployed. Controlled rerun `20260426181300` covered customer chat/product/stock, quotation approve/reject, Telegram private manager reply, active escalation fallback, phone filters, outbound audit readback, and `0` pending conversations.
- `tj-final27.1`: catalog/Zoho truth is explicit. Treejar Catalog API `price` is customer-facing truth; `salePrice` is raw-only until an approved sale policy exists; Zoho remains operational for stock/item/order execution; catalog-only or missing-price quotation fails closed with manager escalation.
- `tj-final27.2`: inbound source/UTM attribution is stored locally with original/latest preservation; Zoho outbound mapping is explicit-only; returning-customer context is bounded.
- `tj-final27.3`: payment reminders are disabled by default; manual/scheduled modes are guarded and capped; out-of-window WhatsApp reminder sends require approved templates; locally created Wazzup providers are closed.
- `tj-z911`: strict price fail-closed behavior and payment-reminder scan hard caps were added. Full local pytest with `-s` passed `818 passed, 19 skipped`; ruff, format, mypy, and artifact validation passed.
- `tj-final27.9`: final acceptance pack and controlled E2E runbook were prepared; the approved functional E2E subset passed; a bounded quality pass confirmed safe behavior for tested hard-facts scenarios and identified sales-copy quality follow-ups.
- `tj-final27.11`: compact deterministic sales fallback was deployed for price objection, retention/drop-off, and known off-catalog requests. Controlled text-only E2E on `[PROTECTED_TEST_PHONE]` passed for all three scenarios with `z-ai/glm-5|sales-fallback`, `escalation_status=none`, and `0` pending conversations.
- `tj-jy5i`: commercial offer/business proposal clarification routing was deployed so incomplete proposal requests ask for missing items/quantities without verified-policy escalation, while high-risk payment terms still route to manager confirmation.
- `tj-final27.13`: payment-reminder run-level provider reuse was deployed without changing the existing scan-loop or hard-cap warning. Payment reminders remain disabled by default.
- `tj-final27.18`: the opening price floor uses every purchasable row with a
  non-zero price and at least one unit. The pinned English line is `Chairs from
  AED 139, desks and workstations from AED 58.` A cited row below five units is
  explicitly qualified as limited stock, with larger quantities requiring a
  potentially different option and price.
- `tj-6tx6`: the realistic R04/R02 office openings now enter a verified catalog
  state before free generation. They carry purchasable SKU/price rows and at
  most one question instead of a numbered questionnaire.

## Confirmed E2E, CI, And Smoke Evidence

Confirmed production and local evidence already recorded:

- `tj-ruue`: GitHub Actions run `24876930080` passed lint/test/type-check/deploy; post-deploy `verify_api.py` passed `7/0`; anonymous dashboard/admin quality endpoints denied; health OK.
- `tj-e2e26`: GitHub Actions runs `24957702024` and `24958178545` passed through deploy. Final post-deploy smoke after `main@2dc356e` passed `verify_api.py` `7/0`, health OK, dashboard anonymous `401`, conversations anonymous `403`, Alembic at `2026_04_26_outbound_audit`.
- `tj-prl26`: GitHub Actions run `24963241165` passed through deploy. Controlled production rerun passed five final synthetic conversations with `0` pending, and stage closeout passed full local pytest `774 passed, 19 skipped`.
- `tj-final27`: the 2026-04-29 final E2E snapshot records deployed `main@090e318d06662eb4a4c4f2247eb01bd1ed317b94`, CI/deploy run `25115695746`, production smoke `verify_api.py` `7/0`, and `/api/v1/health` `200`.
- `tj-final27.9`: approved controlled E2E subset passed on 2026-04-29 against runtime `090e318d06662eb4a4c4f2247eb01bd1ed317b94`. It covered customer discovery, SKU `00-07024023` exact price/stock, quotation approve/reject (`Fr3167`/`Fr3168`), Telegram private manager reply, active escalation fallback, outbound audit readback, phone filtering, and final pending count (`6` conversations, `0` pending).
- `tj-final27.9` quality pass: approved bounded text-only synthetic quality scenarios covered consultative sales, price objection, retention, payment terms/discount request, Saudi Arabia delivery, Arabic sales request, off-catalog request, and large-order handoff. Final readback showed `6` `tj-final27-quality` conversations and `0` pending.
- Later follow-ups: `tj-final27.11` sales fallback deployed on `ab897878e2f0ee339bd7626b63d5c6f3a9497042`, `tj-jy5i` commercial-offer routing deployed on `1cce2aa4bdbc82b9a11ce2f7ce117103e6a3e6f0`, and `tj-final27.13` payment-reminder provider reuse deployed on `354015280c8f8d39b538bbaba769e70d29d1c6b2`. Each had targeted verification and production health/readback evidence recorded in Beads or handoff.
- 2026-08-14 final refresh: `f5be6a2…` passed 3832 tests with 20 skips,
  process verification, protected replay, public API smoke 8/8 and exact
  health-SHA readback. The accepted protected round had 20/20 language matches,
  zero critical failures and exactly one question marker in every reply.
  Synthetic production readback confirmed the outbound and logging guards.
- 2026-08-14 audit repair: `d30b2d9…` passed 3842 tests with the same 20 skips,
  process verification, stage closeout and the unchanged protected replay, then
  deployed with an exact health-SHA readback. The ten added tests are the
  repaired boundary's own: five Arabic replies that must reach the customer
  unchanged, one wrong-language reply that must still be replaced, one English
  reply that must lose only its Arabic sentence, first-turn question
  restoration in both languages, and a later turn that must never be handed a
  discovery question.

What was not confirmed by the historical 2026-04-29 run:

- Voice/audio, payment reminder sends/templates, referral live branch, feedback live branch, scheduled QA, broad production suites, deploy, or staging/production config changes were not run for the original `tj-final27.9` E2E task. The 2026-04-30 docs promotion was a docs/.codex-only merge and did not run live E2E, production mutation, or deploy.
- The 2026-08-14 refresh supplies the current measured round, release gates,
  deployment health SHA, and controlled E2E record; those results supersede this
  historical limitation only where explicitly recorded.

## Sales Quality Findings

The approved quality pass is not a broad AI Quality Controls run. It is a small live synthetic sample meant to judge whether the model sells safely and handles common commercial situations.

Positive findings:

- Consultative sales: the model did not invent an ergonomic chair within a 500 AED budget. It gave higher-priced alternatives, stock constraints, and a useful follow-up question.
- Arabic: the model replied in Arabic, stayed catalog-grounded, and explained the budget mismatch clearly.
- Hard facts: the model did not promise net 30 terms, a 20% discount, or Saudi Arabia delivery next week without manager confirmation.
- Large order: the model captured quantity/location/timing and routed stock, price, and logistics confirmation to a manager.

Quality risks:

- Price objection handling was too generic in the 2026-04-29 quality pass. It was later addressed by `tj-final27.11`, which routes known price objections through compact deterministic sales fallback without promising unapproved discounts.
- Retention handling was too generic in the 2026-04-29 quality pass. It was later addressed by `tj-final27.11`, which adds a non-escalating retention/drop-off fallback.
- Off-catalog redirection was too generic in the 2026-04-29 quality pass. It was later addressed by `tj-final27.11`, which redirects known off-catalog requests toward Treejar's office/workplace categories.
- WhatsApp formatting is readable, but separators and bold markdown can feel mechanical for a human sales chat.

## Client Decisions And Explicit Defers

These items are explicit boundaries of the current delivery:

- Future live E2E still requires an exact phone/channel, an approved synthetic
  suffix prefix, named scenarios and explicit permission for any media, voice,
  payment or referral branch.
- Voice/audio production hardening is delivered under closed `tj-final27.4`;
  no additional live voice test should run without explicit approval.
- Post-delivery feedback acceptance is delivered under closed `tj-final27.5`.
- Referrals are excluded by the approved wording above. The mechanics remain
  implemented and disabled; activation is a separate customer decision after
  acceptance.
- QA/reporting acceptance is delivered under closed `tj-final27.7`; scheduled
  AI Quality Controls stay disabled unless explicitly enabled.
- Nonfunctional readiness evidence is delivered under closed `tj-final27.8`;
  future production load or security runs still require explicit scope.
- Zoho UTM/source outbound mapping: exact Zoho CRM API field names and overwrite policy are still a client decision.
- Payment reminders: template IDs/names, timing, copy/tone, stop conditions, and enablement policy are still client decisions. Default runtime sends zero reminders.
- Support window: source documents mention at least 15 working days of startup support, but final start date, contact path, hours, and escalation rules should be confirmed in the client handoff.
- Measured opening language: resolved by a deterministic final outbound guard;
  the accepted round is 20/20 on the turn language with zero critical failures.
- Logging safety: resolved for Telegram, Wazzup signed upload URLs and catalog
  image URLs. The existing Telegram token intentionally remains unchanged under
  the recorded owner decision above.
- Opening question count: resolved at the same final outbound boundary; the
  accepted round and synthetic production check each contain one literal
  question marker per reply.

## Acceptance Recommendation

Use this pack for client review of the final delivery state. The project has fresh evidence for the core sales path, production runtime health, quotation approve/reject, manager handoff, auth guards, cost-control defaults, catalog/Zoho truth policy, CRM attribution storage, disabled-safe payment reminders, and the approved controlled E2E subset.

The pack is accepted for client handoff: controlled E2E left zero pending
synthetic state, release gates are green, the blind round is recorded with
per-rule ceilings, and production health reports the delivered code commit.
The language, logging-safety and double-question blockers are closed. Referral
activation is not a condition because it is explicitly excluded above. The
measurement boundary and remaining client-owned operating decisions above stay
attached to this acceptance statement.
