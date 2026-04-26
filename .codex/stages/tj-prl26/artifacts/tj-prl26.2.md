---
task_id: tj-prl26.2
stage_id: tj-prl26
repo: treejar
branch: codex/tj-prl26-prelaunch-readiness
base_branch: origin/main
base_commit: f1136fc2a6d6c8c49535b4460c89f3486b2521c1
worktree: /home/me/code/treejar/.worktrees/codex-tj-prl26-prelaunch-readiness
status: blocked
verification:
  - ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id': passed
  - uv run python scripts/verify_api.py --base-url https://noor.starec.ai: passed
  - curl -fsS https://noor.starec.ai/api/v1/health: passed
  - anonymous GET /dashboard/ and /api/v1/conversations/: passed
  - scripts/bot_test.py stock/SKU synthetic message: failed
  - production read-only conversation/API/audit readback: passed
  - Context7 FastAPI docs lookup: passed
changed_files:
  - .codex/stages/tj-prl26/artifacts/tj-prl26.2.md
---

# Summary

Bounded pre-launch E2E stopped early on a launch blocker in the product/stock path. Production public catalog and DB contain SKU `00-07024023`, but the bot told the synthetic customer that the SKU does not exist.

Created blocker Beads task: `tj-prl26.5` (`BUG: production exact SKU stock lookup misses catalog SKU 00-07024023`).

# Verification

The run completed only the runtime/API smoke, the first successful customer stock/SKU scenario, and narrow readback. It intentionally did not continue into quotation or manager flows after the product/stock blocker appeared.

# Runtime / API Smoke

- Runtime target: `https://noor.starec.ai`.
- Runtime path: `/opt/noor`.
- Release SHA: `2dc356ef16496cb33f035198e5deeda733a04c1a`.
- GitHub run id: `24958178545`.
- Worktree HEAD at run start: `44177b398e28e34448d660f9cedb1e0eee162fa3`.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> `7 passed, 0 failed`.
- `GET /api/v1/health` -> `{"status":"ok","version":"0.1.0","dependencies":{"redis":{"status":"ok"}}}`.
- Anonymous `GET /dashboard/` -> `401`.
- Anonymous `GET /api/v1/conversations/` -> `403`.
- Context7 docs check: `/fastapi/fastapi` confirms documented `HTTPException` usage for `401` auth failures and notes FastAPI security utilities may use `403` for older/explicit forbidden behavior; this matches the expected smoke boundary here.

# Customer E2E Evidence

Phone suffix used:

- `79262810921#tj-prl26-chat-20260426a`

Conversation:

- `23ce4397-93e8-4b81-97f0-33846d7f795c`

Synthetic message:

```text
Do you have SKU 00-07024023 in stock, and what is the current price? Synthetic tj-prl26-chat-20260426a.
```

Production catalog/DB evidence:

- Public `/api/v1/products/?page_size=5` returned active SKU `00-07024023`.
- Read-only DB SELECT returned `00-07024023`, `Rectangular operative table, IMAGO-S, SP-3.1SD, 1400x600x755, White/aluminum`, price `264.00`, stock `12`.

Bot response snippet:

```text
I'm sorry, but I couldn't find a product with SKU **00-07024023** in our inventory system. This SKU doesn't appear to exist in our catalog.
```

This is the smallest reproduction found before widening: one customer message with an active public catalog SKU. The run stopped here per guardrail.

# Readback / Audit Evidence

Conversation API phone filtering:

- Exact suffix query `phone=79262810921#tj-prl26-chat-20260426a` -> total `1`, id `23ce4397-93e8-4b81-97f0-33846d7f795c`.
- Exact base query `phone=79262810921` -> total `1`, a separate existing base-phone conversation `95668449-d1a5-4b51-9503-9cb51146b961`; suffix conversation was not included.
- Default exact query `phone=tj-prl26` -> total `0`.
- Explicit fuzzy query `phone=tj-prl26&phone_match=fuzzy` -> total `1`, id `23ce4397-93e8-4b81-97f0-33846d7f795c`.

Outbound audit row for the bot reply:

- Audit id `832fcaa5-c71d-42fa-825d-957c06a8a610`.
- `source=bot_reply`, `message_type=text`, `status=sent`.
- Provider message id `edb4c52e-52b4-4c4b-b66b-9f6710e08e48`.
- CRM message id `bot:23ce4397-93e8-4b81-97f0-33846d7f795c:bbd60d7c-d602-4b49-979d-17b6db013d4f`.
- `status_updated_at=2026-04-26 16:47:45.771290+00:00`.

Pending count:

- `tj-prl26` conversations total: `1`.
- `tj-prl26` conversations with `escalation_status='pending'`: `0`.

Synthetic status webhook update:

- Skipped. Existing outbound audit row already had provider id, `sent` status, and `status_updated_at`; the run stopped at the product/stock blocker before status persistence needed extra validation.

# Commands Run

- `sed -n ... AGENTS.md`, `.codex/orchestrator.toml`, `.codex/handoff.md`, `docs/plans/2026-04-26-prelaunch-readiness.md`, `.codex/stages/tj-prl26/summary.md` -> required context read.
- `bd show tj-prl26.2 --json` -> task open before run.
- Context7 `resolve_library_id("FastAPI")` and `query_docs("/fastapi/fastapi", ...)` -> docs lookup completed.
- `ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id ...'` -> release SHA/run id captured.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> `7/0`.
- `curl -fsS https://noor.starec.ai/api/v1/health` -> ok.
- `curl ... /dashboard/` and `/api/v1/conversations/` anonymously -> `401` and `403`.
- `curl -fsS 'https://noor.starec.ai/api/v1/products/?page_size=5'` -> active SKU evidence captured.
- `scripts/bot_test.py --wait 90 --phone '79262810921#tj-prl26-chat-20260426a' ... SKU 00-07024023 ...` -> webhook accepted, correlated bot reply received, blocker reproduced.
- Read-only SQL SELECTs in production app container -> SKU row, pending count, outbound audit rows.
- Authenticated Conversation API readback with exact/default/fuzzy phone filters -> passed.
- `bd create ...` -> created `tj-prl26.5`.

One preliminary `scripts/bot_test.py` invocation for the discovery prompt accepted the webhook but failed polling with `403` because the local command sourced the wrong API key format. Readback after correction found only the single suffix conversation above; the discovery prompt was not counted as covered evidence.

# Skipped Guardrail Actions

Skipped as explicitly forbidden:

- `scripts/verify_wazzup.py`.
- Scheduled AI Quality Controls.
- Broad production suites.
- Unsolicited media tests outside quotation PDF/caption.
- Deploys, config changes, secret changes.
- DB/Redis `UPDATE`/`DELETE`/manual `INSERT` outside normal app writes caused by the synthetic message.

Skipped because the stock-path blocker stopped widening:

- Greeting/product discovery completion.
- Objection/clarification response.
- Active escalation fallback.
- Approved quotation flow, PDF/text delivery, order-status copy.
- Rejected quotation flow and rejected/no-active-order status copy.
- Telegram private manager reply to customer and persisted manager-reply message.
- Order confirm/reject/PDF media/caption outbound audit rows.

Quotation numbers:

- None generated. Quotation flows were not started after the blocker.

# Risks / Follow-ups / Explicit Defers

- Launch blocker: active public catalog SKU `00-07024023` is not reachable by the bot exact stock/SKU path. Track and fix via `tj-prl26.5`.
- `tj-prl26.2` should be rerun from the product/stock scenario after `tj-prl26.5` is fixed; do not treat quotation or manager flows as accepted from this run.
