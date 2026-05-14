# Stage tj-gh14: Liliya GitHub Issues Stabilization

Updated: 2026-05-14
Status: planned, not implemented
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

## Verification So Far

- No code implementation or tests run for `tj-gh14` yet.
- Current branch contains planning artifacts and Beads only.

## Boundaries

- Do not comment on or close GitHub #34-#37 until explicit approval after evidence.
- Do not deploy, mutate production config, or run live WhatsApp/media/voice tests
  without explicit approval.
- Keep central `src/llm/engine.py` changes sequential unless write zones are split
  explicitly before spawning subagents.
