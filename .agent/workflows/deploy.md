---
description: Deploy to prod via Blue/Green (runs local tests in Worktree)
---

Merge **current branch** into master and push to trigger Blue/Green production deployment.

**What happens:**
1. Isolates tests in a temporary Worktree `../treejar-deploy-tmp`
2. Merges your branch → master in that Worktree
3. Runs checks (`ruff`, `mypy`, `pytest`) in complete safety
4. If successful, pushes to `master`
5. Prod server automatically deploys to inactive color (Blue/Green)

**Flags:**
- `--force` / `-f`: Skip quality checks (tests/linters)
- `--yes` / `-y`: Skip confirmation prompt
- `--sync` / `-s`: Auto-sync develop with master after deploy

**Usage:**
// turbo-all
bash .agent/scripts/deploy.sh $ARGUMENTS
