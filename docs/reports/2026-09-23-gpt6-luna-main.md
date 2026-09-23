# GPT-6 Luna release and post-deployment acceptance

Status: delivered to main, deployed and verified on 2026-09-23.
Tasks: tj-qr32 (model), tj-3nvu (integration/deploy), tj-pmbv (name/error
questions), tj-y1uj (price-unit grounding).
Live code release: `071b0e32f35bec5474ba4b7e4d1b651f85d45295`.
[CI 35855524010](https://github.com/maslennikov-ig/treejar/actions/runs/35855524010)
passed lint, type checks, all tests and standard app-only deployment.

## Result

Primary database setting and environment fallback select `openai/gpt-6-luna`.
Core chat/followup explicitly send reasoning.effort=medium. Auxiliary routes,
35-second completion bound, one same-request retry and 90-second core deadline
are unchanged. Test-only WhatsApp ending0665 remains the operating boundary.

The original `I’m Nadia` now produces the name Nadia before generation. ASCII,
curly and modifier apostrophes are covered. Generation-error replies receive
no additive discovery/name/company questions. The live Nadia smoke returned a
useful answer without asking for the supplied name again.

The Arabic smoke exposed an unsupported package-price inference for CH 850 T
black (2 pcs/1 box): the model called AED139 a box price. A separate read-only
Zoho GET confirmed selling unit `pcs`. The customer catalog price was preserved;
Zoho's different rate did not replace it. Agent instructions now require direct
evidence for selling units and prohibit conversion using packaging quantities.
This clarification lives in the sales agent. The frozen general grounding policy
was restored byte-for-byte; no historical policy evidence was re-pinned.

## Verification

- Final CI: **4,115 passed, 27 skipped**; Ruff/format and Mypy passed.
- Focused name/error regressions: five cases initially; adjacent opening tests
  now mock successful generation and assert a non-error response.
- A pre-existing test-only timestamp race was removed by deriving observation
  time from the synthetic attempt's final timestamp, not elapsed wall time.
  Production readback validation remains unchanged.
- Initial CI caught a stale expected model and mutable handoff digest. Updated
  the expected selected model and used the repository's current-state re-pin
  helper. The first policy patch hit a frozen source pin and was relocated.
- Fresh independent reads in app and worker confirm Luna/medium, test mode and
  sender/allowlist equality. All four changed runtime file hashes match code.
- Exact live health SHA confirmed, database/Redis healthy, app/worker running
  with zero restarts. Standard deployment revalidated test-worker restrictions.

## Bounded paid model checks

These use real OpenRouter completions and the deployed prompt, tool schemas and
core model settings. Tool calls are intercepted; catalog rows come from a
read-only DB snapshot, inventory-unavailable results are deliberate fixtures,
and business writes/outbound sends are disabled. This is **not** a full
process_message/WhatsApp/Zoho quotation E2E proof.

| Scenario | Root assessment | Seconds |
|---|---|---:|
| Original Nadia office request | Name retained, substantive reply, no repeat name ask | 11.37 |
| Exact chair SKU | Search/stock calls, catalog AED99, no invented stock | 6.79 |
| Explicit no quotation/order/manager | No such side-effect tool requested | 5.64 |
| Arabic office request after correction | Arabic/name preserved, no package-price invention | 32.26 |
| Is AED139 for a pair? | Refuses unsupported pair price, retains catalog amount | 12.19 |

The initial catalog attempt hit the smoke harness's artificial three-round
limit (not a runtime timeout). Its incomplete trace is retained. Only that case
was replayed with a five-round bound. The initial Arabic failure is also retained;
after the scoped correction, Arabic and explicit packaging-price cases were run.
Unaffected earlier model observations were reused rather than rerunning all cases.
No HTTP/model timeouts occurred in these smoke attempts. The final Arabic answer
was conservative about price and did not give amounts; this is not evidence that
all possible sales answers are perfect.

Provider-confirmed smoke cost: **USD 0.00813352**
across 21 completion calls; unknown-cost attempts: 0.
The earlier switch compatibility call cost USD0.0000155 separately. No paid
second reader was used. The root read and assessed every output.

Evidence: `2026-09-23-luna-smoke-before-price-unit-fix.json` and
`2026-09-23-luna-smoke-after-price-unit-fix.json` in this directory.

## Recovery

Latest standard-deploy backup:
`/opt/noor/.hotfix-backups/deploy-20260923T113912Z-from-e325c63fd7cf687d15d738cea2a20fd4a98a8f6b.tar.gz`.
That previous release includes Luna/medium and the name/error fix.

Earlier model-switch rollback:
`/opt/noor/.hotfix-backups/tj-qr32-20260923`; previous DB/environment main model
was z-ai/glm-5.3-flash, with noor-rollback:tj-qr32-app/worker images. Its private
environment backup remains on the server. Restore only this setting using an
expected-current-value check, preserve subsequent environment changes and all
conversation/customer data, recreate only app/worker, then verify test boundaries.

No task-specific implementation defers remain. Fresh tester-authored WhatsApp
traffic is the remaining end-to-end delivery/real quotation observation boundary.
