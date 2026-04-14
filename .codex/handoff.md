# Orchestrator Handoff

Updated: 2026-04-14
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stages `tj-6h30`, `tj-5dbj`, `tj-7k2m`, and `tj-8q1r` are closed under `.codex/stages/`.
- Latest runtime-changing verification baseline is `652e0773d7206c17dcc8df7c4bcf4af4a63e7b46`.
- `tj-5dbj` landed deterministic lock-driven rebuilds, CPU-only PyTorch resolution, portable `vps-deploy.sh`, and process/stage verification fallback for hosts where `python3 < 3.11`.
- `tj-7k2m` revalidated the current deploy/runtime state: GitHub Actions run `24387902673` remains the latest successful `main` deploy for `67be40052087fc1f478e7f60ff44c85b4d6375b9`, live health returns `status=ok`, and `scripts/verify_api.py --base-url https://noor.starec.ai` passed `7/0`.
- `tj-8q1r` cleaned up repo-local orchestration truth: `CLAUDE.md` now defers to `AGENTS.md` and `.codex/*`, and the stale macOS WeasyPrint defer was replaced with current local evidence.
- On this macOS host, minimal WeasyPrint/PDF generation now works without `DYLD_FALLBACK_LIBRARY_PATH`; the remaining local PDF verification gap is that `scripts/verify_pdf.py` imports the LLM engine and therefore still needs app env such as `OPENROUTER_API_KEY`.

## Next recommended

Next stage id: `tbd`
Recommended action: no active follow-up stage is warranted after `tj-8q1r`; start a new isolated stage only with fresh live/runtime evidence or a newly prioritized operational/product track, and do not reopen already verified quotation or Telegram hypotheses without new evidence.

## Starter prompt for next orchestrator

Use $stage-orchestrator.
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, and `.codex/stages/tj-5dbj/summary.md` first.
Start from current `origin/main`.
Treat `652e0773d7206c17dcc8df7c4bcf4af4a63e7b46` as the latest runtime-changing verified baseline for deterministic rebuilds, CPU-only packaging, and portable orchestration verification.
Treat `tj-7k2m` as the latest evidence-only proof that deployed `main@67be40052087fc1f478e7f60ff44c85b4d6375b9` still matches the canonical live/API surface.
Treat `tj-8q1r` as the cleanup stage that supersedes the old host-local WeasyPrint defer with current evidence.
Keep runtime/deploy work isolated from product logic.

## Explicit defers

- Dirty root worktree state from `/Users/igor/code/treejar` must stay isolated and must not be merged into `main` without fresh review.
