# Stage tj-e2e16: Long-Dialog Detail Capture Hardening

Updated: 2026-05-15
Status: implementation ready, delivery pending
Branch: `codex/tj-e2e15-detail-capture-hardening`
Base: `origin/codex/tj-long-memory-e2e@9b2df496b38b4c55c296522dfa9c130e9a498b85`

## Goal

Fix the long-dialog blocker found in production E2E stage `tj-e2e15`: neutral
customer-detail updates inside an active sales/product dialogue must be captured
as durable context and must not trigger verified-policy manager handoff.

## Context

Production conversation `cb46ebcb-1c5a-41f4-a7d7-99e295f11ba7` showed that
`The company is Memory Test LLC.` was routed to `verified-policy`, created a
pending escalation, and blocked later address/product/quantity turns with
manager-notified fallback replies.

Read-only subagent analysis confirmed that this happened before the PydanticAI
agent run, so PydanticAI `message_history` alone could not fix it. Context7 docs
were checked for current PydanticAI multi-turn and testing behavior:

- https://github.com/pydantic/pydantic-ai/blob/main/docs/agent.md
- https://github.com/pydantic/pydantic-ai/blob/main/docs/testing.md
- https://github.com/pydantic/pydantic-ai/blob/main/docs/api/models/test.md

## Implementation

- Extract natural customer details such as `The company is ...` and
  `Delivery address is ...`.
- Store compact durable sales memory in conversation metadata for assembly,
  quote-hold, and latest product note.
- Inject escaped, explicitly untrusted captured sales context into the system
  prompt so later LLM turns can remember name/company/address/items/assembly.
- Add a narrow deterministic `detail-capture` acknowledgement only for neutral
  detail updates in an active sales context, before verified-policy handoff.
- Keep product/quantity updates on the normal product path instead of swallowing
  them as detail-only turns.
- Keep true handoff cases for payment terms, credit, discount, complaint,
  refund/return, manager/human requests, and other high-risk terms.

## Beads

- `tj-e2e16`: implementation epic.
- `tj-e2e16.1`: root-cause map, completed by read-only subagent.
- `tj-e2e16.2`: deterministic detail capture and anti-escalation implementation.
- `tj-e2e16.3`: repeatable stress evidence and stage documentation.
- `tj-e2e16.4`: remaining merge/deploy/live E2E task.
- `tj-e2e15.2`: original production blocker remains open until deployed and
  live E2E passes.

## Verification

- `uv run pytest tests/test_verified_answers.py tests/test_llm_engine.py -v --tb=short`: 191 passed.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed.
- `uv run mypy src/`: passed.
- `env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`: 1041 passed, 19 skipped.
- `scripts/orchestration/run_process_verification.sh`: passed.
- `scripts/orchestration/check_stage_ready.py tj-e2e16`: passed.

## Boundaries

- No production deploy was performed in this stage.
- No production database cleanup or live WhatsApp E2E retest was performed in
  this stage.
- Lili's real WhatsApp thread was not mutated.
