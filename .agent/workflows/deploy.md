---
description: Deploy directly to Prod/Stage (runs tests in isolated Worktree first)
---

Merge **current branch** into main and push to trigger a direct production deployment.

**What happens:**
1. Isolates tests in a temporary Worktree `../treejar-deploy-tmp`
2. Merges your branch → `main` in that Worktree
3. Runs checks (`ruff`, `mypy`, `pytest`) in complete safety
4. If successful, pushes to `main`
5. Prod server automatically rebuilds and restarts the `treejar-prod` containers

**Flags:**
- `--force` / `-f`: Skip quality checks (tests/linters)
- `--yes` / `-y`: Skip confirmation prompt
- `--sync` / `-s`: Auto-sync develop with master after deploy

**Usage:**
// turbo-all
bash .agent/scripts/deploy.sh $ARGUMENTS
