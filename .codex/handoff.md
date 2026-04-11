# Orchestrator Handoff

Updated: 2026-04-11
Current baseline branch: `main`

## Current truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Treejar Catalog API is the customer-facing catalog source of truth; Zoho remains the exact stock/price and order-execution truth.
- Stage `tj-6h30` is closed and fully recorded under `.codex/stages/tj-6h30/`.
- Latest runtime-changing verification baseline is `b2d9b6beb82f050ac44f8c026cd8f9936b06d5fd`.
- GitHub Actions deploy run `24286771354` succeeded on 2026-04-11.
- Live verification is complete for quotation, Telegram manager-review, repaired smoke tooling, deployed synthetic smoke `chatId` normalization, and safe `faq_global` downgrade.
- Owner-facing observation guide: `docs/client/victor-owner-guide-2026-04-11.md`.
- On this WSL host, full `pytest` verification needs `TMPDIR=/tmp TEMP=/tmp TMP=/tmp` because inherited Windows temp paths break pytest capture teardown.

## Next recommended

Next stage id: `tj-5dbj`
Recommended action: investigate canonical `/opt/noor` rebuild determinism and CPU-only packaging without reopening already-verified quotation or Telegram hypotheses.

## Starter prompt for next orchestrator

Use $stage-orchestrator.
Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, and `.codex/stages/tj-6h30/summary.md` first.
Start from current `origin/main`.
Treat `b2d9b6beb82f050ac44f8c026cd8f9936b06d5fd` as the last runtime-changing verified baseline for quotation and Telegram manager-review behavior.
Keep runtime/deploy work isolated from product-logic changes.

## Explicit defers

- `tj-5dbj`: runtime rebuild determinism and CPU-only packaging remain open by design.
- Dirty root worktree state from `/home/me/code/treejar` must stay on a separate backup branch and must not be merged into `main` without fresh review.
