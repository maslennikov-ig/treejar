# Code Review: tj-gh14 Delivery

**Date**: 2026-05-14
**Scope**: Current `codex/tj-gh14-new-issues` runtime diff before push/merge
**Files**: 12 runtime/test/orchestration files | **Changes**: +674 / -55

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 0    | 0      | 0   |
| Improvements | -        | 0    | 0      | 0   |

**Verdict**: PASS

## Issues

No blocking issues found.

## Delivery Findings

- Independent explorer `Bacon` flagged a P0 delivery-process blocker before
  commit: `HEAD` still contained only prior planning documents while the runtime
  implementation lived in the dirty worktree. This is accepted and resolved by
  the delivery commit requirement: stage and commit all intended runtime, test,
  Beads, stage artifact, and review files before push/merge, then re-check
  `git diff origin/main...HEAD`.

## Improvements

No pre-merge improvements required.

## Reviewed Paths

- `src/llm/engine.py`: bare quantity+SKU exact-quote parsing, name-gate pending request store/consume, and `order_confirmation` escalation veto.
- `src/llm/order_handoff.py`: SKU-like product detection remains gated by delivery/install plus logistics evidence.
- `src/services/chat.py` and `src/services/outbound_audit.py`: product-media caption suppression keeps internal audit data while sending no customer-visible caption.
- `tests/test_llm_engine.py`, `tests/test_llm_order_handoff.py`, `tests/test_chat_escalation.py`, `tests/test_services_chat_batch.py`, `tests/test_outbound_audit.py`: regressions cover the reported GitHub #34-#37 paths and nearby negative cases.

## Evidence

- `src/llm/engine.py:646`: bare `qty x SKU` and `SKU x qty` candidates are canonicalized before exact-quote routing.
- `src/llm/engine.py:807`: `order_confirmation` rejection requires product/SKU plus quantity without fulfillment evidence, and `src/llm/engine.py:3867` blocks the tool before manager notification.
- `src/llm/engine.py:1775`: first-turn pending requests are stored with a 600-character cap and consumed at `src/llm/engine.py:4149` after the customer provides a name.
- `src/services/outbound_audit.py:489`: provider calls receive `caption=None` and no `caption_crm_message_id` when `send_caption=False`; the audit caption row is marked internal-only at `src/services/outbound_audit.py:562`.

## Validation

- Context7: `/pydantic/pydantic-ai` confirms `RunContext` is excluded from tool schema and non-context parameters are exposed as tool arguments.
- Targeted post-format suite: PASS, `29 passed`.
- Worker media/audit scope: PASS, `25 passed`.
- Wide modified LLM/escalation scope: PASS, `158 passed`.
- Full canonical gates before delivery: PASS for `ruff check`, `ruff format --check`, `mypy`, full pytest `1016 passed, 19 skipped`, process verification, and stage closeout.
- Additional spot checks: first direct import failed without `OPENROUTER_API_KEY`; rerun with `OPENROUTER_API_KEY=dummy` passed for compact SKU parsing, order-confirmation veto, and first-turn order handoff cases.

## Residual Risk

Live WhatsApp/media/voice and production deploy validation remain outside this review until explicit current-task approval for those external effects.
