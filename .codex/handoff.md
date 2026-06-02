# Orchestrator Handoff
Updated: 2026-06-02
Current branch: `codex/tj-gh48-expected-answer-frames`

## Current Truth
- Canonical host: `https://noor.starec.ai`; runtime path: `/opt/noor`.
- `main` includes delivered `tj-gh47` runtime commit `70500e32e6206462b426b65dd8d7afc8e5ccda72`; any later docs-only evidence commit is not part of the deployed runtime.
- Production runtime is `70500e32e6206462b426b65dd8d7afc8e5ccda72`: `.release-sha=70500e32e6206462b426b65dd8d7afc8e5ccda72`, `.release-run-id=26771029593`.
- `tj-mmj8`, `tj-4cm4`, `tj-8ma2`, and `tj-4xnf` are merged, deployed, live-E2E verified/triaged, cleaned, and closed in Beads.
- `tj-4xnf` fixed the remaining Zoho Inventory customer-resolution failure after prior duplicate-name fallback commit `e97bbb4`: synthetic phone suffixes no longer leak into Inventory lookup/create.
- Local `tj-4xnf` fix strips repo-owned `#...` suffixes only at the Zoho Inventory contact boundary, while preserving suffixed phones inside app conversation storage.
- Local verification passed: RED/GREEN synthetic suffix regression, `tests/test_llm_quotation.py` plus Inventory tests (`20 passed`), relevant engine quote tests (`46 passed`), ruff, format check, mypy, and full stage closeout (`1181 passed, 19 skipped`).
- `tj-nzob` is merged, pushed, deployed, production-smoked, locally cleaned, and closed in Beads: comma-separated ordered brief parsing now preserves `company=LLD`; GitHub Actions run `26502776229` passed `changes`, `lint`, `test`, `type-check`, and `deploy`; production smoke passed `8 passed, 0 failed`; live WhatsApp E2E was not run.
- `tj-4xnf` production E2E conversation `4c2156c6-1763-435e-aa3d-7965631a96f3` created quotation `Fr3316` / sale order `378603000022228007`; synthetic conversations were closed after evidence.
- Stage evidence: `.codex/stages/tj-4xnf/summary.md`, `.codex/stages/tj-4xnf/artifacts/tj-4xnf-local-implementation.md`, and `.codex/stages/tj-4xnf/artifacts/tj-4xnf-production-e2e.md`.
- Current `tj-nzob` evidence: `.codex/stages/tj-nzob/summary.md` and `.codex/stages/tj-nzob/artifacts/tj-nzob-local-implementation.md`.
- Stage `tj-gh47` fixed GitHub #47 preference-answer over-escalation; implementation is merged, pushed, deployed, production-smoked, production-E2E verified, and closed in GitHub/Beads.
- `tj-gh47` production E2E conversation `6e437d6d-e1b9-46e0-ad58-cfe7fe9e85ee` on `+79262810921#tj-gh47-pref-20260601173808` proved that `I prefer more open for team` after Noor's LUMA/NOVO question returns NOVO/open product options with `escalation_status=none`, `pending_escalations=0`, no manager-handoff wording; the synthetic conversation was closed.
- Active planning stage `tj-gh48` prepares the fundamental fix: expected-answer frames in the existing Dialogue State Kernel, so Noor remembers answer expectations across bounded interruptions instead of relying only on the latest assistant question.
- `tj-gh48` docs/spec package is on branch `codex/tj-gh48-expected-answer-frames`: updated `docs/specs/dialogue-state-kernel.md`, `docs/specs/dialogue-state-kernel-evals.md`, and added `docs/superpowers/plans/2026-06-02-expected-answer-frames.md`.
- Beads `tj-gh48` epic and dependent tasks `tj-gh48.1` through `tj-gh48.7` exist; implementation remains pending and must start from these tasks.

## Next recommended
Next stage id: `tj-gh48`.
Recommended action: review the expected-answer frames spec/package, then execute implementation through Beads `tj-gh48.2` through `tj-gh48.7` using a dedicated worktree/branch from fresh `origin/main`.

## Starter prompt for next orchestrator
Use $orchestrator-stage. Continue `tj-gh48` expected-answer frames. Read `AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `.codex/stages/tj-gh48/summary.md`, `docs/specs/dialogue-state-kernel.md`, `docs/specs/dialogue-state-kernel-evals.md`, and `docs/superpowers/plans/2026-06-02-expected-answer-frames.md`. Start implementation from fresh `origin/main` in a dedicated branch/worktree. Use Beads `tj-gh48.2` through `tj-gh48.7`; do not create duplicate tasks. Keep production in `dialogue_kernel_mode=shadow` unless explicit approval enables a narrow enforce rollout. Do not deploy, mutate production, run live WhatsApp E2E, or close #11 without explicit current-task approval.

## Explicit defers
- `tj-nzob`: live WhatsApp E2E was not run; local/parser tests and production API smoke passed after deploy.
- `tj-final27.6`: referral launch remains blocked pending written client referral policy or explicit exclusion.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
- `tj-gh48`: implementation is deferred to the next orchestrator; this pass only prepared docs, Beads, and prompt.
