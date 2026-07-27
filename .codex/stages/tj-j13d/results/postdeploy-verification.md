# Production verification — tj-j13d

Verified: `2026-07-27T13:31:02Z`

## Delivery

- GitHub Actions:
  `https://github.com/maslennikov-ig/treejar/actions/runs/30270308830`
- Run `30270308830`: `changes`, `lint`, `type-check`, `test`, and `deploy`
  succeeded.
- Runtime release:
  `8ec2f71f3acb3ba37d514b2b220720c724c9f410`
- Runtime model readback:
  - `OPENROUTER_MODEL_MAIN=z-ai/glm-5.2`
  - `OPENROUTER_MODEL_FAST=deepseek/deepseek-v4-flash`
- Protected runtime `.env`: mode `600`, owner `noor-dev:noor-dev`.

## Runtime health

- `app`, `worker`, `nginx`, `redis`, and `db`: running.
- Public `/api/v1/health`: `status=ok`; Redis and database `ok`.
- Direct Redis probe: `PONG`.
- Direct PostgreSQL probe: accepting connections.
- Repo-owned public API probe: `8 passed, 0 failed`.
- Fresh app/worker logs: no matching traceback, critical, unhandled,
  exception, or error entries.

## Synthetic model-route smoke

Executed through the live app container environment by feeding the tracked
`scripts/verify_model_routes.py` over standard input; the image intentionally
does not package the repository `scripts/` directory.

- Provider capability preflight: passed.
- GLM-5.2 showroom visit: passed (`6172.498 ms`).
- GLM-5.2 conditional project samples: passed (`5449.144 ms`).
- GLM-5.2 medical-inference refusal: passed (`5144.503 ms`).
- GLM-5.2 missing-stock verification: passed (`4200.829 ms`).
- DeepSeek V4 Flash strict JSON with reasoning disabled: passed
  (`1444.998 ms`).
- Summary: `5/5` passed.

The verification used fixed synthetic prompts and made no customer, Wazzup,
Zoho, quotation, order, database, or CRM mutation.

## Rollback

Rollback was not required. The protected previous environment and release
snapshots remain available and verified as recorded in
`rollback-manifest.md`.
