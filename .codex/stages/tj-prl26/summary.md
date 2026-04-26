# Stage tj-prl26: Pre-Launch Readiness Acceptance Pack

Status: in progress
Base worktree: `/home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness`
Branch: `codex/tj-prl26-prelaunch-readiness`
Base: `origin/main@f1136fc2a6d6c8c49535b4460c89f3486b2521c1`
Latest deployed runtime SHA: `2dc356ef16496cb33f035198e5deeda733a04c1a`

## Scope

This stage prepares launch/no-go evidence before real customer traffic. It is not a feature stage.

The stage covers:

- repeatable pre-launch acceptance checklist;
- bounded synthetic WhatsApp/Telegram E2E prompt;
- read-only admin/operator and cost-control readiness checks;
- final launch/no-go closeout with blockers and explicit defers.

## Beads

- `tj-prl26`: epic for pre-launch readiness.
- `tj-prl26.1`: define checklist/runbook and stage docs.
- `tj-prl26.2`: run controlled synthetic customer E2E acceptance pass.
- `tj-prl26.3`: verify admin/operator and cost-control launch defaults.
- `tj-prl26.4`: close readiness with launch/no-go decision.

## Guardrails

- Do not run broad production suites, `scripts/verify_wazzup.py`, scheduled AI Quality Controls, or unsolicited media tests without explicit approval.
- Do not deploy, mutate production config, rotate secrets, or write DB/Redis outside explicitly approved synthetic E2E flows.
- Do not store raw secrets in tracked files, artifacts, Beads, or prompts.
- Product/API fixes discovered by this stage must become separate Beads unless they are docs-only orchestration corrections.

## Acceptance Matrix

- Runtime health: `verify_api.py`, `/api/v1/health`, release SHA, Alembic head.
- API boundary: anonymous dashboard/admin/conversation access denied.
- Core customer chat: greeting, discovery, language, no crash.
- Product/stock: catalog/Zoho truth, no invented price or stock.
- Quotation approval/reject: PDF/text/status metadata and order-status copy.
- Manager handoff: Telegram private reply is sent, persisted, and auditable.
- Escalation fallback: active escalation is safe and quiet.
- Outbound audit/idempotency: Wazzup side effects and status updates are visible.
- Cost controls: AI Quality Controls safe by default; no scheduled QA LLM spend.
- Operator readiness: owner can inspect conversations, audit rows, and controls.

## Current State

- Worktree created from current `origin/main`.
- Beads `tj-prl26` and children `tj-prl26.1-.4` created.
- `tj-prl26.1` is closed: plan, stage summary, controlled E2E prompt, and artifact were created and validated.
- `tj-prl26.2` remains open for controlled live synthetic E2E after explicit approval.
- `tj-prl26.3` remains open for read-only admin/operator and cost-control launch checks.
- `tj-prl26.4` remains open for final launch/no-go closeout.

## Explicit Defers

- No live synthetic messages have been sent in this stage yet.
- No production observation window is planned because the project has no real customer traffic yet.
