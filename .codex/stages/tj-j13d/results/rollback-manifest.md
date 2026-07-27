# Production rollback manifest — tj-j13d

Captured: `2026-07-27T13:24:56Z`

This manifest contains no credentials. The protected files remain only on the
canonical Noor server.

## Previous production state

- Deployed release:
  `292d82cdbe7a041787093779173d3e051c052ccb`
- `OPENROUTER_MODEL_MAIN=z-ai/glm-5`
- `OPENROUTER_MODEL_FAST=xiaomi/mimo-v2-flash`

## Protected snapshots

- Environment backup:
  `/opt/noor/.hotfix-backups/model-switch-20260727T132456Z-from-292d82cdbe7a041787093779173d3e051c052ccb.env`
  - SHA-256:
    `9975af9a7e30c995cc01db71f97c089a3ce716fc57693c3131489212f832239c`
  - mode/owner: `600`, `noor-dev:noor-dev`
  - verified size: `2521` bytes
- Release backup:
  `/opt/noor/.hotfix-backups/model-switch-20260727T132456Z-from-292d82cdbe7a041787093779173d3e051c052ccb.tar.gz`
  - SHA-256:
    `66339ce64254a7188e836615d21dd822cab18ff5faa2c7d5901be741a1ed09c6`
  - mode/owner: `600`, `noor-dev:noor-dev`
  - verified size: `3789124` bytes
  - archive listing was successfully read and contains `docker-compose.yml`
    plus the prior release files.

## Restore procedure

Run on the canonical server as `noor-dev`:

1. Recheck both SHA-256 values above.
2. Restore the protected environment with mode `600`:
   `install -m 600 <environment-backup> /opt/noor/.env`.
3. Run the canonical deploy entrypoint against `<release-backup>` with target
   `/opt/noor` and health URL
   `http://127.0.0.1:8002/api/v1/health`.
4. Read back `.release-sha` and both model variables.
5. Verify app, worker, Redis, PostgreSQL, public health, and the bounded
   synthetic model-route smoke.

Rollback is mandatory if deployment health, provider preflight, structured
JSON, or grounding verification fails.
