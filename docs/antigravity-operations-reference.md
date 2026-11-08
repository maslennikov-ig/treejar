# Treejar operations reference migrated from GEMINI.md

This retains unique historical infrastructure and integration-fixture facts
from the pre-rollout `GEMINI.md` on 2026-10-04. It is an on-demand reference,
not current runtime proof or authorization. Current `AGENTS.md`, handoff and
operations runbooks control execution. Check current scripts/configuration and
live evidence before using any dated topology, endpoint or API observation.

Deployments, live mutations and permission changes require current explicit
owner authority. The historical SQL command below is a command shape, not a
permission to reset or write a database. Keep fixture identities and channel
facts project-local. The original complete file has a private external backup
under `~/.agent-harness/antigravity/projects/`.

## Historical environment and infrastructure
The project currently runs on a new Hetzner VPS (`95.216.204.189`, Helsinki, 8 vCPU, 16 GB RAM) to securely host both Development and Production environments in parallel, physically isolated via separate Docker Compose configurations and Nginx Host routing.

*   **Production (Stage/Prod)**
    *   **Domain**: `noor.starec.ai` (Listens on port `8002` internally via Nginx)
    *   **Branch**: `main`
    *   **Docker Config**: `docker-compose.yml` (Services: `app`, `db`, `worker`, `redis`, `nginx`)
    *   **Environment File**: `.env`
    *   **Data Volumes**: Standard Docker named volumes (`pgdata`, `redis-data`)

*   **Development (Dev)**
    *   **Domain**: `dev.noor.starec.ai` (Listens on port `8003` internally via Nginx)
    *   **Branch**: `develop`
    *   **Docker Config**: `docker-compose.dev.yml` (Services renamed with `-dev` suffixes)
    *   **Environment File**: `.env.dev`
    *   **Data Volumes**: Isolated named volumes (`pgdata-dev`, `redis-data-dev`) to prevent collision.

### Deployment Flow (Automated CI/CD)
Deployments are fully automated via GitHub Actions (`.github/workflows/ci.yml`):
1.  **Trigger**: Pushing code to `main` or manually running `workflow_dispatch` from `main`.
2.  **Action**: GitHub Actions packages a release archive from the tracked repository contents and uploads it to the VPS over SSH using repository secrets (`VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_KEY`).
3.  **Execution**: CI uploads the repo version of `scripts/vps-deploy.sh` and runs it against the live runtime directory `/opt/noor`.
4.  **Result**: The script syncs the release into `/opt/noor`, preserves runtime-only state such as `.env`, creates a rollback backup under `.hotfix-backups`, runs `docker compose up -d --build`, and verifies the local health endpoint.

### VPS SSH Access (Agent Notes)
*   **Host**: `95.216.204.189`
*   **Port**: `2222`
*   **User**: `noor-dev`
*   **Key file**: `~/.ssh/treejar_vps` (Saved locally on agent's machine)
*   **Role**: Agent has limited NOPASSWD sudo access to restart services and run `docker compose up -d` in `/opt/noor/`.
*   **SSH Config Alias**: `noor-server`
*   **DB Reset Command** (for testing):
    ```bash
    ssh noor-server "docker exec noor-db-1 psql -U treejar -d treejar -c \"<SQL_HERE>\""
    ```


## Application architecture
*   **Backend**: Python, FastAPI, SQLAlchemy (AsyncPG), Alembic (Migrations).
*   **Database**: PostgreSQL 16 (with pgvector for LLM embeddings) & Redis 7 (for caching/queues).
*   **Dependency Manager**: `uv` (project defined in `pyproject.toml`).
*   **Task Management**: Existing Beads (`bd`); current `AGENTS.md` controls isolation and verification.


## Integration testing fixtures

### Test Contact in Zoho CRM
A permanent test contact exists in Zoho CRM for use in integration tests:
*   **Zoho CRM ID**: `559571000034673035`
*   **Phone**: `+971000000001`
*   **Name**: Integration TestBot
*   **Email**: `integration-test@treejar.test`
*   **Segment**: `["Wholesale"]` (multi-select list — the exact type returned by real API)
*   **Lead Source**: Chatbot

**Usage**: All integration tests under `tests/integration/` reference this contact via `TEST_CONTACT_PHONE = "+971000000001"` in `tests/integration/conftest.py`.

**Important**: Do NOT delete this contact from Zoho CRM. It is used by `@pytest.mark.integration` tests.

### Wazzup Channel for Tests
*   **Channel ID**: `b49b1b9d-757f-4104-b56d-8f43d62cc515`
*   **Name**: Treejar
*   **Phone**: `+971551220665`
*   **Transport**: WhatsApp

> **Note**: Wazzup v3 API requires `contentUri` (a publicly accessible URL) for sending files, NOT inline base64. The current `WazzupProvider.send_media` base64 `content` field is silently ignored by Wazzup.
