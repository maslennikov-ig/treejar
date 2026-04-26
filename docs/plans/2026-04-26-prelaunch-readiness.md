# Pre-Launch Readiness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Produce launch/no-go evidence for Treejar before real customer traffic without widening scope or mutating production unless explicitly approved.

**Architecture:** Treat pre-launch readiness as evidence collection, not feature work. Keep API/admin/cost checks read-only by default, run live WhatsApp synthetic E2E only as an explicitly approved bounded pass, and convert any defect into a separate Beads task instead of silently fixing inside the readiness stage.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, Redis, Wazzup webhooks, Telegram callbacks, OpenRouter/PydanticAI, Beads, repo-local orchestration scripts.

---

## Stage

- Stage ID: `tj-prl26`
- Worktree: `/home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness`
- Branch: `codex/tj-prl26-prelaunch-readiness`
- Base: `origin/main@f1136fc2a6d6c8c49535b4460c89f3486b2521c1`
- Latest deployed runtime SHA: `2dc356ef16496cb33f035198e5deeda733a04c1a`

## Guardrails

- Do not run `scripts/verify_wazzup.py`.
- Do not enable or trigger scheduled AI Quality Controls.
- Do not run broad production suites.
- Do not send unsolicited media tests.
- Do not deploy, change production config, rotate secrets, or mutate DB/Redis except through explicitly approved synthetic E2E messages.
- Do not store raw secrets in tracked docs, Beads, artifacts, or prompts.

## Acceptance Matrix

| Area | Required Evidence | Launch Gate |
| --- | --- | --- |
| Runtime health | `verify_api.py` 7/0, `/api/v1/health` ok, release SHA known, Alembic at head | Blocking if health fails, release is unknown, or migration is behind |
| API boundary | Anonymous `/dashboard/` returns `401`; anonymous `/api/v1/conversations/` returns `403`; exact phone filter remains exact by default | Blocking if public conversation data is exposed |
| Core customer chat | Synthetic greeting/discovery reply in the customer's language, no crash, conversation is traceable | Blocking if no reply, wrong channel, or hallucinated hard facts |
| Product discovery/stock | Product suggestions include customer-facing catalog data; exact SKU/stock answer uses Zoho/catalog truth | Blocking if price/stock is invented |
| Quotation approval | Exact SKU + quantity creates manager approval flow, approve sends PDF/text, order-status says approved/processing | Blocking if PDF is missing, stale pending copy appears, or order metadata is unusable |
| Quotation reject | Reject writes rejected/inactive state and order-status says rejected/no active order | Blocking if rejected sale order is treated as active |
| Manager handoff | Private Telegram manager reply is sent to customer, persisted as conversation message, and escalation resolves | Blocking if sent reply is not auditable |
| Active escalation/fallback | Customer receives safe fallback while hard escalation is active and bot does not fight manager takeover | Blocking if bot spams or ignores escalation state |
| Outbound audit/idempotency | Wazzup text/media/caption rows exist with provider IDs/status; synthetic status webhook updates rows | Blocking if outbound side effects are invisible |
| Cost controls | AI Quality Controls disabled/manual by default, no scheduled QA LLM calls, GLM-5 not used for non-core defaults, `llm_attempts` exists | Blocking if background QA can spend credits by default |
| Operator readiness | Admin dashboard reachable behind auth; operator can inspect conversations, outbound audit, AI Quality Controls posture | Blocking if owner cannot see/triage critical state |

## Task 1: Local Plan And Stage Artifacts

**Files:**
- Create: `.codex/stages/tj-prl26/summary.md`
- Create: `.codex/stages/tj-prl26/artifacts/tj-prl26.1.md`
- Create: `docs/plans/2026-04-26-prelaunch-readiness.md`
- Create: `docs/prompts/2026-04-26-tj-prl26-controlled-e2e-agent.md`
- Modify: `.codex/handoff.md`

**Steps:**

1. Create Beads epic `tj-prl26` and child tasks `tj-prl26.1-.4`.
2. Write this plan and stage summary.
3. Write the controlled E2E agent prompt.
4. Run:

```bash
uv run python scripts/orchestration/validate_artifact.py .codex/stages/tj-prl26/artifacts/tj-prl26.1.md
uv run python scripts/orchestration/check_stage_ready.py tj-prl26
bash scripts/orchestration/run_process_verification.sh
git diff --check
```

Expected: artifact validation and process verification pass; stage readiness may remain blocked until child tasks are complete.

## Task 2: Controlled Synthetic E2E Pass

**Owner:** E2E agent or manual operator.

**Files:**
- Create: `.codex/stages/tj-prl26/artifacts/tj-prl26.2.md`

**Prerequisite:** Explicit approval to send bounded synthetic messages through production WhatsApp/Telegram.

**Steps:**

1. Confirm deployed runtime:

```bash
ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id 2>/dev/null || true'
uv run python scripts/verify_api.py --base-url https://noor.starec.ai
curl -fsS https://noor.starec.ai/api/v1/health
```

2. Run customer-facing synthetic scenarios with unique `tj-prl26-*` phone suffixes and `scripts/bot_test.py`.
3. Exercise Telegram approve/reject/private reply callbacks only for created synthetic conversations.
4. Read back conversation details, outbound audit rows, status updates, and pending counts.
5. Record exact conversation IDs, quotation numbers, response snippets, and skipped actions.

Expected: all launch-gate flows pass or produce concrete blocker Beads.

## Task 3: Admin/Operator And Cost-Control Readiness

**Files:**
- Create: `.codex/stages/tj-prl26/artifacts/tj-prl26.3.md`

**Steps:**

1. Verify auth guards via HTTP:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' https://noor.starec.ai/dashboard/
curl -sS -o /dev/null -w '%{http_code}\n' https://noor.starec.ai/api/v1/conversations/
curl -sS -o /dev/null -w '%{http_code}\n' https://noor.starec.ai/api/v1/admin/ai-quality-controls
```

Expected: dashboard/admin endpoints fail closed for anonymous users (`401` or protected redirect as appropriate); conversations return `403`.

2. Run read-only DB checks from `/opt/noor`:

```bash
ssh noor-server 'cd /opt/noor && docker compose exec -T app uv run python - <<'"'"'PY'"'"'
from sqlalchemy import text
from src.core.database import SessionLocal

queries = {
    "ai_quality_controls": "select value from system_configs where key = 'ai_quality_controls'",
    "llm_attempts": "select count(*) from llm_attempts",
    "outbound_audits": "select count(*) from outbound_message_audits",
    "pending_tj_prl26": "select count(*) from conversations where phone like '%tj-prl26%' and escalation_status = 'pending'",
}
with SessionLocal() as db:
    for name, sql in queries.items():
        print(name, db.execute(text(sql)).scalar())
PY'
```

Expected: no DB writes; QA config is missing/disabled or explicitly safe; audit/attempt tables exist; no pending synthetic conversations after E2E.

3. Record whether admin UI can show operator-critical data. Use screenshots only if explicitly requested.

Expected: owner has a usable operational view before launch.

## Task 4: Closeout And Launch/No-Go Decision

**Files:**
- Modify: `.codex/stages/tj-prl26/summary.md`
- Modify: `.codex/handoff.md`
- Create or update: `.codex/stages/tj-prl26/artifacts/tj-prl26.4.md`

**Steps:**

1. Review artifacts for `tj-prl26.1-.3`.
2. Classify evidence into:
   - launch blocker;
   - acceptable defer;
   - already covered by existing delivered stage.
3. Create Beads for any blocker found.
4. Run stage closeout only when blockers are closed or explicitly deferred:

```bash
PYTEST_ADDOPTS=-s uv run python scripts/orchestration/run_stage_closeout.py --stage tj-prl26
```

Expected: launch/no-go recommendation is backed by fresh evidence.

## Initial Recommendation

Start with Task 3 read-only checks and Task 2 controlled E2E in parallel only if live synthetic messages are approved. If any blocker appears, stop widening E2E and create the narrowest fix stage for that defect.
