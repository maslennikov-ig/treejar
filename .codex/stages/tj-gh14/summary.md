# Stage tj-gh14: Liliya GitHub Issues Stabilization

Updated: 2026-05-14
Status: implemented and verified; delivery pending approval
Branch: `codex/tj-gh14-new-issues`
Base: `origin/main@27ac4fae74fe3fc201522b5ceedbf76477f58e4f`
Plan: `docs/plans/2026-05-14-liliya-gh34-37-stabilization.md`

## Goal

Stabilize GitHub issues #34-#37 from `liliya12m` without mutating GitHub issues,
production config, live WhatsApp state, or deployment state before explicit approval.

## Scope

- `tj-gh14.1` / #34: bare quantity+SKU such as `5 x CH 190` routes to exact_quote.
- `tj-gh14.2` / #37: product+quantity-only messages do not order_confirmation escalate.
- `tj-gh14.3` / #36: name-gate preserves and resumes the prior substantive request.
- `tj-gh14.4` / #35: product media sends no redundant customer-visible caption text.

## Evidence Gathered

- Read all four GitHub issue bodies and comments; #37 has an additional comment
  confirming repeated product+quantity-only escalation.
- Checked related closed work: `tj-gh12.2`, `tj-gh12.16`, `tj-gh12.18`,
  `tj-gh12.19`, plus GitHub #22/#28/#29/#33.
- Inspected current code in `src/llm/engine.py`, `src/llm/order_handoff.py`,
  `src/llm/prompts.py`, `src/services/chat.py`,
  `src/services/outbound_audit.py`, `src/integrations/messaging/wazzup.py`,
  and `src/services/conversation_reset.py`.
- Context7 checked `/pydantic/pydantic-ai` for agent tool behavior.

## Implementation

- #34 / `tj-gh14.1`: added deterministic bare quantity+SKU parsing for
  `5 x CH 190`, `CH 190 x 5`, and numeric hyphenated SKUs; order handoff now
  recognizes SKU-like products when delivery/logistics evidence is present.
- #37 / `tj-gh14.2`: added an `order_confirmation` tool guard so product/SKU
  plus quantity alone is not enough to notify a manager.
- #36 / `tj-gh14.3`: first-turn unknown-name requests store a bounded
  `name_gate_pending_request`; name-only replies consume it and resume normal
  routing instead of returning the generic opener. Resolved escalation now has
  a regression check that it does not mutate `sales_stage`.
- #35 / `tj-gh14.4`: deferred `product_media` sends images with no
  customer-visible caption while retaining internal caption audit metadata.

## Delegation

- Worker `Newton` implemented #35 in the messaging/outbound-audit zone; the
  orchestrator reviewed diff and reran the full worker test scope.
- Explorer `Kierkegaard` inspected #36 read-only; orchestrator verified the
  cited code paths and implemented the accepted minimal path.

## Verification So Far

- RED observed for #34/#37 parser/tool guard and #36 pending-request behavior.
- Targeted post-format suite: `29 passed`.
- Worker scope: `25 passed`.
- Wide modified LLM/escalation suite: `158 passed`.
- `ruff check` and `ruff format --check` passed for changed files.
- Canonical gates passed: full `ruff check`, full `ruff format --check`, `mypy`,
  full pytest `1016 passed, 19 skipped`, and process verification.
- Stage closeout passed with code-change verification and process verification.
- Local Beads `tj-gh14`, `tj-gh14.1`, `tj-gh14.2`, `tj-gh14.3`, and
  `tj-gh14.4` are closed.

## Boundaries

- Do not comment on or close GitHub #34-#37 until explicit approval after evidence.
- Do not deploy, mutate production config, or run live WhatsApp/media/voice tests
  without explicit approval.
- Keep central `src/llm/engine.py` changes sequential unless write zones are split
  explicitly before spawning subagents.
