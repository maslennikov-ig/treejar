# Orchestrator Handoff

Updated: 2026-08-14
Current branch: `main`
Current stage id: `tj-final27-client-handoff`
Status: final client-handoff delivery is in verification. The requested anchor,
realistic-opening fix, referral exclusion, acceptance pack, controlled E2E and
measured round are recorded. One new measured P1, `tj-08ve`, remains open.

Documentation: no external/versioned boundary - this delivery follows repository
code and the already pinned pgvector/model evidence.

## Current truth

- A catalog row joins an anchor family only when its name and taxonomy agree,
  and joins the first matching family (`tj-3jo0`). A first message explicitly
  about something other than furniture still withholds the anchor (`tj-7vhq`).
  Arabic still uses `،` (`tj-b8il`).
- The opening price floor now uses every row with a non-zero price and at least
  one unit in stock. On the pinned catalog it is `Chairs from AED 139, desks and
  workstations from AED 58.` If a cited row has fewer than five units, the reply
  says stock is limited and a larger quantity may require another option and
  price (`tj-final27.18`).
- R04 and R02 no longer fall through to a model questionnaire. Headcount plus
  named furniture families, or a generic office brief, enters a verified
  opening-catalog state, prints purchasable SKU/price rows, qualifies delivery
  timing, and asks at most one question (`tj-6tx6`).
- The opening-round prompt is built from production functions. Its retrieval
  evidence has 332 catalog rows, BGE-M3 revision
  `5617a9f61b028005a4858fdac845db406aefb181`, pgvector `0.8.5`, and retrieval
  contract `29123d5fb9d3a8bc4dabce9585e333f5e51305e75044b47270d9b51c0c6a3da1`.
- `/api/v1/health` returns the deployed release SHA or bounded `unknown`.

## Referral scope exclusion approved 2026-08-14

«Реферальная программа в объём текущей сдачи не входит. Механика
реализована и отключена; запуск выполняется отдельным решением заказчика
после приёмки.»

This exact wording is also in the client acceptance pack. `tj-final27.6` is
closed; referral activation is not a delivery condition.

## Final measurement

- Protected output:
  `.git/codex-orchestration/corpus-bridge/tj-final27.18-round-20260814b`.
- Preflight: 20 scenarios, 19 priced, 1 withheld, AED 139 / 58, zero paid calls.
- Root read 20/20 blind and free. No second reader. Score/mean ceiling and delta
  from `tj-399z`: r1 2.00/2.00 (0.00), r2 1.85/2.00 (-0.10), r3 2.00/2.00
  (0.00), r4 1.95/2.00 (0.00), r5 1.80/1.95 (0.00), r7 2.00/2.00 (+0.05),
  r8 2.00/2.00 (+0.17, n=6), r9 2.00/2.00 (0.00, n=6).
- Raw paired delta: 0.00/opening, 95% -0.25 to +0.20. Weighted delta: +0.10,
  95% -0.15 to +0.36. Both are inside the measured 2.0-point reader gap.
  Fourteen of 20 reached their own ceiling, versus 13/20 in `tj-399z`.
- The anchor contradicted no quoted row. Every reply that owed a low-stock
  warning carried it before the next question.
- New defects: wrong language plus a generic need question on dialog 293;
  internal catalog-lookup wording on 1067. Gone: repeated value copy on 807;
  product-led question on 442; stacked clarification questions on 1067.
  Unchanged: wrong-family wording on 436; product lists on 420/1000; the
  rule-5 ceiling on 28; dropped delivery timing on 819.
- The round is not accepted because dialog 293 switched the substantive reply
  away from the customer language. The one critical failure is `tj-08ve`.
- Paid calls: 20 Luna generation calls, $0.006569; one triggered repair call,
  $0.000134; total $0.006703 under the $0.05 cap. Scoring cost zero.

## Protected replay

- Frozen baseline:
  `1fc87c04a645fa97e35978283584fb840f5ae7b7c2e4291740d4f5c0f1567b00`.
- Current raw aggregate:
  `1b425bd1f66a9189a07436f5d75b3bbcb71d68ca716e94b6f0d4c86627c97866`.
- Exactly 7 expected differences remain, only on dialogs 28, 875 and 1291.
  No re-baseline.
- No protected request or reply body is tracked; durable records use only ids,
  integers and digests.

## Final package and E2E

- The client pack states prominently that the opening stand charges 8 of 15
  rules. Rules 6, 10, 11, 12, 13, 14 and 15 are unreachable on the first turn.
- Deal outcomes are visible for only 192 of 1400 dialogues. The pack makes no
  conversion, revenue, close-rate or causal sales claim.
- Before delivery, public API smoke passed 8/8 on production `8c832b4`. Two
  approved text-only synthetic conversations returned grounded chat and exact
  SKU answers with 0 pending. Reply digests:
  `a5e01a3dbcef9e96fe8f5d8a318b67a8619b7d9b488906e40d612cfbb465f6a6` and
  `718d82e85471c098a4df756aaa3b0fa4db876a5240795cc6d859e518b1d04a16`.
- Post-delivery R04/anchor E2E and delivered-SHA health readback are pending.

## Verification

- Focused anchor/guard/harness checks: 119 passed.
- R04/R02 state and three repeated answers per form: passed.
- Ruff check and format: passed. Mypy: passed.
- Full pytest: 3821 passed, 20 skipped, 0 failed. The +18 passes from the
  3803/20/0 baseline are 15 direct regressions and three automatically
  parameterized registry checks for the new deterministic route. The first pass
  exposed seven maintenance failures; all seven were fixed before this clean
  run.
- Process verification: passed. Root stage closeout: 71 passed, 1 skipped.
- Final raw replay after closeout retained `1b425bd1…` versus `1fc87c04…` and
  the same seven expected differences.
- Production delivery and post-deploy readback are pending.

## Documentation and graph review

- `docs-reviewed: updated` - handoff, client pack, root reading convention and
  stage evidence carry the changed behavior and measured result.
- `project-index: reviewed-no-change` - no stable entrypoint or module ownership
  boundary changed.
- `graph-reviewed: no-change-needed` - Graphify is not initialized.

## Next recommended

Next stage id: not opened
Recommended action: fix `tj-08ve`, then run a fresh paired opening round only
with new owner authority. Never use `--second-reader`.

## Starter prompt for next orchestrator

Use $orchestrator-stage on `tj-08ve`. Keep the customer-language fix
deterministic, preserve the protected raw replay, and request fresh authority
before any new measured generation calls.

## Explicit defers

- `tj-08ve`: dialog 293 switched the substantive first reply away from the
  stored customer language. A deterministic language guard and a new paired
  20-opening round are required; this stage's 20 generation calls are exhausted.
- The opening stand cannot exercise rules 6, 10, 11, 12, 13, 14 or 15. They
  remain covered by separate multi-turn/functional evidence and are never
  presented as part of the opening score.
- Reader-gap drift re-read remains owed under `tj-4q79`; the 2.0-point gap is
  not recomputed here and no paid second reader is authorized.
- Two candidate rule-2 convention cases from `tj-68au` remain unadopted until
  both paired rounds are reread. Rule 5's mean ceiling remains 1.95.
