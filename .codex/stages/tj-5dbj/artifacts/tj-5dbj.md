---
task_id: tj-5dbj
stage_id: tj-5dbj
repo: treejar
branch: codex/tj-5dbj-integration
base_branch: main
base_commit: d1eb3f5118cb1cfa4bb5816fdce7c7bd6efe059e
worktree: /Users/igor/.config/superpowers/worktrees/treejar/tj-5dbj-integration
status: accepted_and_integrated
verification:
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv sync --locked --all-extras --dev --python 3.13: passed
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run ruff check src/ tests/: passed
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run ruff format --check src/ tests/: passed
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run mypy src/: passed
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run pytest tests/ -v --tb=short: passed (619 passed, 19 skipped)
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp scripts/orchestration/run_process_verification.sh --stage tj-5dbj: passed
  - TMPDIR=/tmp TEMP=/tmp TMP=/tmp python3 scripts/orchestration/run_stage_closeout.py --stage tj-5dbj: passed with a local `uv` wrapper exporting macOS WeasyPrint dylib path
changed_files:
  - .github/workflows/ci.yml
  - Dockerfile
  - README.md
  - docs/dev-guide.md
  - pyproject.toml
  - scripts/vps-deploy.sh
  - tests/test_infra_contract.py
  - uv.lock
  - scripts/orchestration/cleanup_stage_workspace.py
  - scripts/orchestration/run_process_verification.sh
  - scripts/orchestration/run_stage_closeout.py
  - scripts/orchestration/runtime_support.py
  - tests/test_scripts_process_verification.py
  - .codex/handoff.md
  - .codex/stages/tj-5dbj/summary.md
  - .codex/stages/tj-5dbj/artifacts/tj-5dbj.md
---

# Summary

This stage closed the operational rebuild and packaging gap without reopening already verified product behavior. The integrated change-set forces lock-driven installs in Docker and CI, pins `torch` to the explicit CPU wheel index, adds a regression contract test for the infrastructure assumptions, and keeps orchestration closeout usable on hosts where `python3` is still below 3.11.

The stage also carries the `vps-deploy.sh` portability fix so local/macOS operators no longer trip over `mapfile` and so missing `.env` fails before command preflight. All work stayed in the runtime/deploy lane; quotation, Telegram review, and other previously verified product hypotheses were not reopened.

# Verification

- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv sync --locked --all-extras --dev --python 3.13` -> passed
- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run ruff check src/ tests/` -> passed
- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run ruff format --check src/ tests/` -> passed
- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run mypy src/` -> passed
- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp uv run pytest tests/ -v --tb=short` -> `619 passed, 19 skipped`
- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp scripts/orchestration/run_process_verification.sh --stage tj-5dbj` -> passed
- `TMPDIR=/tmp TEMP=/tmp TMP=/tmp python3 scripts/orchestration/run_stage_closeout.py --stage tj-5dbj` -> passed with a local `uv` wrapper exporting the macOS WeasyPrint dylib path

# Risks / Follow-ups

- Host-local WeasyPrint libraries are still a machine-setup concern outside git; this repo change-set only ensures the Python/runtime contract is deterministic once those system libraries exist.
- Dirty root worktree state under `/Users/igor/code/treejar` remains intentionally excluded from this stage and must stay outside any `main` delivery without fresh review.
