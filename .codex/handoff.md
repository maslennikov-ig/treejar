# Orchestrator Handoff

Updated: 2026-05-19
Current branch: `main`

## Current Truth

- Canonical host: `https://noor.starec.ai`; canonical runtime path: `/opt/noor`.
- Production release is `9e967d5acd862e98c74b472c1d6fa102e686bf3f`; GitHub Actions run `26098722338` succeeded; `/opt/noor/.release-sha` matches.
- Stage `tj-gh18` is delivered, deployed, live E2E verified, and GitHub #39/#35 are closed.
- Stage `tj-gh19` is delivered, deployed, live E2E verified, Beads closed, and GitHub #40 is closed.
- `tj-gh19.1` / #40 context fix preserves pending quote context for terse details like `Lil, 1 dubay`, stores name/address, keeps `pending_quote_selection`, and asks only for missing company-or-individual when address is specific.
- `tj-gh19.2` / #40 quantity fix prevents model numbers such as `SKYLAND NOVO 2400` from becoming quantities for `CH 616`; prior SKU variants including Cyrillic homoglyph `СН 616` remain covered.
- Final `tj-gh19` verification passed: targeted LLM/verified-answer suites `215 passed`; ruff, format-check, mypy, git diff check, full pytest `1066 passed, 19 skipped`, process verification, and stage closeout.
- Production smoke passed: `scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`.
- Final live E2E conversation `640d0cfb-0460-4033-b6f0-7de84eadcc2a` verified name-gate resume, exact product reference quantity clarification, `NOVO 2400` non-quantity behavior, `CH 616` variant selection, `Lil, 1 dubay` quote-context preservation, company-or-individual gate, and no escalation.
- Stage summary: `.codex/stages/tj-gh19/summary.md`; artifacts: `.codex/stages/tj-gh19/artifacts/tj-gh19.1-2.md`, `.codex/stages/tj-gh19/artifacts/tj-gh19.3-live-e2e.md`.
- Stage `tj-gh20` is delivered to production in `shadow` mode. Customer-visible behavior remains legacy; the LangGraph Dialogue State Kernel writes bounded traces only.
- Production `SystemConfig`: `dialogue_kernel_mode=shadow`, `dialogue_kernel_trace_enabled=true`, `dialogue_kernel_enforced_flows=""`.
- `tj-gh20` adds a LangGraph Dialogue State Kernel with default `legacy`, side-effect-free `shadow`, and allowlisted `enforce`; exact SKU+quantity turns are recognized but delegated to legacy in v1 until kernel-owned quote side effects are implemented.
- Production synthetic E2E with mock messaging passed for name-gate resume, quote-detail context preservation, `NOVO 2400` non-quantity parsing, `CH 616` quantity parsing, product reference clarification, and side-effect-free shadow traces.
- Decision report: keep `shadow`, do not enable `enforce` yet. Post-quotation shadow trace showed the kernel would hold quote context while legacy answered with a manager-confirm message; this remains under GitHub #11 until Lilia answers policy questions.
- `tj-gh20` artifacts: `.codex/stages/tj-gh20/summary.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.1-docs-fixtures.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.2-6-runtime-kernel.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.6-readonly-review.md`, `.codex/stages/tj-gh20/artifacts/tj-gh20.7-delivery.md`.
- Orchestration baseline is `balanced-v2.7`; use repo-local commands in `.codex/orchestrator.toml`.

## Next recommended

Next stage id: new `tj-gh21` or #11-specific stage after Lilia answers follow-up policy questions.

Recommended action: monitor production shadow traces and prepare an enforce rollout proposal only after #11 policy answers are available. Keep #11 pending until Lilia answers the already-posted questions.

## Starter prompt for next orchestrator

Use $orchestrator-stage for the next medium/complex issue batch. Current delivered production release is `9e967d5acd862e98c74b472c1d6fa102e686bf3f`; `tj-gh20` is deployed in `shadow` mode only, with decision report in `.codex/stages/tj-gh20/artifacts/tj-gh20.7-delivery.md`. Do not enable `enforce` or touch GitHub #11 until Lilia answers the pending questions.

## Explicit defers

- `tj-b4n` / GitHub #24 remains provider-blocked pending an official Wazzup typing endpoint.
- GitHub #11 remains pending Lilia's answers.
- Dialogue kernel `enforce` rollout remains deferred; production is intentionally `shadow` only.
