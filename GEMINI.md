# Antigravity (Gemini) Memory File: TreeJar Project

**Purpose**: This file serves as a memory anchor for project-specific infrastructure, deployment flows, and custom workflows.

## Environment & Deployment Infrastructure
The project uses a single TreeJar VPS (`136.243.71.213`) to securely host both Development and Production environments in parallel, physically isolated via separate Docker Compose configurations and Nginx Host routing.

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
Deployments are fully automated via GitHub Actions (`.github/workflows/deploy.yml`):
1.  **Trigger**: Pushing code to `develop` or `main`.
2.  **Action**: GitHub Actions connects to the VPS via SSH (`root` or configured user) using repository secrets (`VPS_HOST`, `VPS_USERNAME`, `VPS_SSH_KEY`).
3.  **Execution**: It executes `scripts/vps-deploy.sh [branch_name]` on the server.
4.  **Result**: The script updates the git tree, resets to the remote branch, and runs `docker compose up -d --build` targeting the correct `.yml` configuration.

## Custom Workflows & Scripts

*   **`/push` (Development/Release Cycle)**
    *   Uses `.agent/workflows/push.md` -> `.agent/scripts/release.sh`.
    *   Role: Analyzes conventional commits, generates/updates `CHANGELOG.md` and `RELEASE_NOTES.md`, bumps the semantic version in `pyproject.toml`, creates a release commit, and pushes a Git tag.
    *   *Note*: Has `RELEASE_SKIP_REMOTE_CHECK=true` context locally to prevent `git fetch` deadlocks inside the agent shell.

*   **`/deploy` (Production Pipeline)**
    *   Uses `.agent/workflows/deploy.md` -> `.agent/scripts/deploy.sh`.
    *   Role: Safely merges the current feature branch into `main` using an **isolated Git worktree**. It runs tests (`pytest`, `ruff`, `mypy`) within the temporary worktree. If tests pass, it pushes to origin `main`, which in turn triggers the aforementioned GitHub Action to deploy to VPS Prod.

## Core App Architecture Quick Summary
*   **Backend**: Python, FastAPI, SQLAlchemy (AsyncPG), Alembic (Migrations).
*   **Database**: PostgreSQL 16 (with pgvector for LLM embeddings) & Redis 7 (for caching/queues).
*   **Dependency Manager**: `uv` (project defined in `pyproject.toml`).
*   **Task Management**: "Beads" (`bd` CLI tool) for macro-tasks (bug, feature, task). All tasks must be done in isolated worktrees (`using-git-worktrees` skill) under a strict TDD paradigm.
