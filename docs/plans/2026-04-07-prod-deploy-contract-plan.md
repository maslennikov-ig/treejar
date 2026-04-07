# Production Deploy Contract Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the broken git-based VPS deploy with a tested artifact-based deploy that matches the live `/opt/noor` runtime.

**Architecture:** GitHub Actions will build a release archive from the tracked repo contents, upload it to the VPS, then execute a repo-owned deploy script that syncs the archive into `/opt/noor`, preserves runtime-only state, rebuilds Docker Compose, and verifies health. Rollback will use automatic pre-deploy backups instead of remote git history.

**Tech Stack:** GitHub Actions, bash, rsync, tar, Docker Compose, pytest

---

### Task 1: Build deploy-script regression coverage

**Files:**
- Create: `tests/test_scripts_vps_deploy.py`
- Modify: `scripts/vps-deploy.sh`

**Step 1: Write the failing tests**

- Cover successful archive deployment into a temp `noor` directory.
- Assert that `.env` and preserved runtime directories survive the sync.
- Assert that stale tracked files are removed.
- Assert that Docker Compose is invoked with project name `noor`.
- Add a failure test for a missing `.env`.

**Step 2: Run tests to verify failure**

Run: `uv run pytest tests/test_scripts_vps_deploy.py -v --tb=short`

Expected: FAIL because the current script only supports git-based deploys from `/opt/treejar-prod`.

**Step 3: Implement minimal deploy-script rewrite**

- Replace branch-based git pull logic with archive-based sync logic.
- Add argument parsing for archive path, target dir, compose file, and health URL.
- Add runtime backup creation and backup retention.
- Fail fast when `.env` is missing.

**Step 4: Run the deploy-script tests**

Run: `uv run pytest tests/test_scripts_vps_deploy.py -v --tb=short`

Expected: PASS

### Task 2: Align CI with the new deploy contract

**Files:**
- Modify: `.github/workflows/ci.yml`

**Step 1: Update deploy job inputs**

- Add `workflow_dispatch` for recovery deploys from `main`.
- Add deploy-job concurrency to prevent overlapping releases.
- Add a checkout step for the deploy job.

**Step 2: Package and upload a release artifact**

- Build a release directory from `git archive`.
- Add `.release-sha` and `.release-run-id`.
- Upload the archive and `scripts/vps-deploy.sh` over SSH/SCP using the existing VPS secrets.

**Step 3: Execute remote deploy**

- Run the uploaded deploy script against `/opt/noor`.
- Let the script own the health-check result.

### Task 3: Converge runtime and operator documentation

**Files:**
- Modify: `scripts/setup-vps.sh`
- Modify: `docs/admin-guide.md`
- Modify: `GEMINI.md`

**Step 1: Update setup script**

- Rename the live path reference from `/opt/treejar-prod` to `/opt/noor`.
- Remove clone-based guidance and point operators at the deploy workflow / release artifact.

**Step 2: Update operator docs**

- Document `/opt/noor` as the canonical runtime path.
- Replace git-based rollback with backup-based rollback from `.hotfix-backups`.
- Align deploy flow notes with artifact-based CI.

### Task 4: Remove stale compose-project hints from operator helpers

**Files:**
- Modify: `scripts/verify_all.sh`
- Modify: `scripts/verify_api.py`
- Modify: `scripts/verify_crm.py`
- Modify: `scripts/verify_db.py`
- Modify: `scripts/verify_followups.py`
- Modify: `scripts/verify_inventory.py`
- Modify: `scripts/verify_pdf.py`
- Modify: `scripts/verify_quality.py`
- Modify: `scripts/verify_rag_pipeline.py`
- Modify: `scripts/verify_telegram.py`
- Modify: `scripts/verify_voice.py`

**Step 1: Update usage hints**

- Replace `docker compose -p treejar-prod ...` with `/opt/noor`-based commands that match the live runtime.

### Task 5: Verify and release

**Files:**
- Modify as needed based on validation findings

**Step 1: Run local verification**

Run:

- `uv run pytest tests/test_scripts_vps_deploy.py -v --tb=short`
- `uv run ruff check src/ tests/`
- `uv run ruff format --check src/ tests/`
- `uv run mypy src/`
- `uv run pytest tests/ -v --tb=short`

**Step 2: Push to `main`**

- Push the deploy-contract fix once local verification passes.

**Step 3: Verify live deployment**

- Watch the GitHub Actions deploy job to completion.
- Verify the VPS health-check and runtime service state.
