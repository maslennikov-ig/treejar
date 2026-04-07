# Docker Maintenance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add safe Docker cleanup automation for the canonical VPS and reclaim excess Docker disk usage without touching live data volumes.

**Architecture:** A repo-managed bash script performs conservative or aggressive Docker cleanup, verifies health, and can be scheduled via a user-level crontab installer. The live server cleanup uses the same contract instead of ad-hoc shell history.

**Tech Stack:** bash, Docker CLI, cron, pytest

---

### Task 1: Add regression tests for maintenance scripts

**Files:**
- Create: `tests/test_scripts_docker_maintenance.py`

**Step 1: Write failing tests**

- Cover dry-run output and ensure no prune commands execute.
- Cover `--apply` conservative mode and assert:
  - builder prune uses bounded cache options
  - image prune uses retention filter
  - health-check runs
- Cover cron installer idempotency and managed-block replacement.

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_scripts_docker_maintenance.py -v --tb=short -s`

Expected: FAIL because the scripts do not exist yet.

### Task 2: Implement the maintenance scripts

**Files:**
- Create: `scripts/docker-maintenance.sh`
- Create: `scripts/install-docker-maintenance-cron.sh`

**Step 1: Implement cleanup script**

- Default to dry-run.
- Support `--apply`, `--aggressive`, `--target-dir`, and log-file output.
- Run only:
  - `docker builder prune`
  - `docker image prune`
- Never prune volumes.
- Run health-check after cleanup.

**Step 2: Implement cron installer**

- Write a managed block into the current user's crontab.
- Create the maintenance log directory.
- Keep install idempotent.

**Step 3: Re-run targeted tests**

Run: `uv run pytest tests/test_scripts_docker_maintenance.py -v --tb=short -s`

Expected: PASS

### Task 3: Update operator docs

**Files:**
- Modify: `docs/admin-guide.md`

**Step 1: Add maintenance runbook**

- Document conservative daily cleanup
- Document aggressive one-off cleanup
- Document cron installation

### Task 4: Verify and apply

**Files:**
- Modify as needed from validation feedback

**Step 1: Local verification**

Run:

- `bash -n scripts/docker-maintenance.sh scripts/install-docker-maintenance-cron.sh`
- `uv run pytest tests/test_scripts_docker_maintenance.py -v --tb=short -s`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `uv run pytest tests/ -v --tb=short -s`

**Step 2: Release**

- Push to `main`

**Step 3: Canonical apply**

- Run one aggressive cleanup on the VPS
- Install daily cron automation
- Re-check:
  - `docker system df`
  - `df -h`
  - health endpoint
