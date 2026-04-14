# Orchestrator Handoff

Updated: 2026-04-14
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-6h30` and `tj-5dbj` are closed under `.codex/stages/`.
- Latest runtime-changing verification baseline is `652e0773d7206c17dcc8df7c4bcf4af4a63e7b46`.
- `tj-5dbj` landed deterministic lock-driven rebuilds, CPU-only PyTorch resolution, portable `vps-deploy.sh`, and process/stage verification fallback for hosts where `python3 < 3.11`.
- On this macOS host, full `pytest` verification depends on local WeasyPrint system libraries and `DYLD_FALLBACK_LIBRARY_PATH`; that remains host-local rather than repo-tracked state.

## Next recommended

Next stage id: `tbd`
Recommended action: start a new isolated stage only with fresh live/runtime evidence or a newly prioritized operational track; do not reopen already verified quotation or Telegram hypotheses without new evidence.

## Starter prompt for next orchestrator

Use $stage-orchestrator.
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, and `.codex/stages/tj-5dbj/summary.md` first.
Start from current `origin/main`.
Treat `652e0773d7206c17dcc8df7c4bcf4af4a63e7b46` as the latest runtime-changing verified baseline for deterministic rebuilds, CPU-only packaging, and portable orchestration verification.
Keep runtime/deploy work isolated from product logic.

## Explicit defers

- Host-local WeasyPrint provisioning (`brew` packages and `DYLD_FALLBACK_LIBRARY_PATH`) is still machine-specific and intentionally not tracked in git.
- Dirty root worktree state from `/Users/igor/code/treejar` must stay isolated and must not be merged into `main` without fresh review.
