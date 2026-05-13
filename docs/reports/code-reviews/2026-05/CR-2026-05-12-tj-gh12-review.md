# Code Review: tj-gh12

**Date**: 2026-05-12
**Scope**: `/home/me/code/treejar/.worktrees/codex-tj-gh12-new-issues` vs `origin/main@838d3d65887947452b2e77e75c633848a37fa2b9`
**Verdict**: NEEDS WORK

## Summary

| Category | Critical | High | Medium | Low |
|---|---:|---:|---:|---:|
| Issues | 0 | 1 | 2 | 0 |
| Improvements | - | 2 | 2 | 1 |

The main implementation is coherent, but several review findings should be fixed before delivery. The highest risk is that the exact quote fallback can discard the new missing-details gate and escalate instead of asking for required customer data.

## Issues

### High

#### 1. Exact quote fallback discards the missing required details block

- **File**: `src/llm/engine.py:4039`
- **Problem**: `create_quotation()` returns the new missing-details prompt before Zoho/PDF/send, but the exact quote fallback only returns `fallback_text` when `quotation_created` or escalation is true.
- **Impact**: A customer with exact SKU and quantity but missing address/company can get a manager fail-closed escalation instead of the intended "please share missing details" prompt.
- **Fix**: Treat missing required details as a valid exact-quote response. Store the pending quote selection and return `_quote_missing_required_details_message(...)` before fail-closed escalation.

### Medium

#### 2. Stage closeout and cleanup lost the tomllib runtime fallback

- **File**: `scripts/orchestration/run_stage_closeout.py:6`, `scripts/orchestration/cleanup_stage_workspace.py:6`
- **Problem**: `tomllib` is imported directly. `origin/main` bootstrapped through `runtime_support.ensure_tomllib_runtime(...)`.
- **Impact**: Canonical orchestration entrypoints crash on Python 3.10 before they can re-exec through the repo runtime.
- **Fix**: Restore the runtime-support bootstrap before importing `tomllib`.

#### 3. Quotation item gate accepts mixed valid and invalid item lists

- **File**: `src/llm/engine.py:1638`
- **Problem**: `_quote_missing_required_details()` only requires any item to have a SKU and positive quantity. Other lines with blank SKU or non-positive quantity can still reach Zoho line construction.
- **Impact**: Malformed tool args can create invalid line items or confusing failures after the required-data gate appears to have passed.
- **Fix**: Require every item line to have a SKU and quantity greater than zero.

## Improvements

### High

#### 1. Proposal follow-up has state and send planning, but no executor path

- **File**: `src/services/proposal_followup.py:348`
- **Current**: `next_due_followup_step()` and `build_followup_send_plan()` are covered by tests, but runtime only records proposal sent and stops on customer reply.
- **Impact**: Once templates/config are provided, enabling follow-ups still will not send FU1-FU4.
- **Recommended**: Add a disabled-by-default ARQ worker job that scans due conversations, sends template/freeform messages with outbound audit/idempotency, and records sent steps.

#### 2. Proposal read status is not wired into follow-up metadata

- **File**: `src/api/v1/webhook.py:102`, `src/services/proposal_followup.py:290`
- **Current**: `record_proposal_read()` exists, but Wazzup status webhooks only update outbound audit rows.
- **Impact**: FU1 remains scheduled on the unread 24h path even if Wazzup reports that the proposal message was read.
- **Recommended**: Apply Wazzup `read` statuses to conversations whose proposal metadata stores the same provider message id.

### Medium

#### 3. Wazzup typing no-op should not run a refresh loop every 4 seconds

- **File**: `src/services/chat.py:366`, `src/integrations/messaging/wazzup.py:221`
- **Current**: The refresh loop repeatedly calls `send_typing()`, but `WazzupProvider` intentionally no-ops because public Wazzup docs do not expose a supported typing endpoint.
- **Impact**: No customer-visible benefit, but extra task churn and info logs on every LLM response.
- **Recommended**: Expose a capability flag or return value and skip the loop for unsupported providers.

#### 4. Add regression coverage for exact quote missing-details path through `process_message()`

- **File**: `tests/test_llm_engine.py:3990`
- **Current**: Direct `create_quotation()` missing-data tests exist, but the exact quote orchestrated path can discard that result.
- **Recommended**: Add a test where exact SKU + quantity resolves, customer details are incomplete, and `process_message()` returns the missing-details prompt without manager escalation.

### Low

#### 5. Use a stable, shorter Maps URL

- **File**: `src/llm/engine.py:83`
- **Current**: The Google Maps URL includes tracking/session parameters.
- **Impact**: It works, but is less plain and more brittle than a stable place URL.
- **Recommended**: Keep a clean Google Maps place URL without `entry=...` or `g_ep=...` parameters.

## Positive Patterns

- `docs/04-sales-dialogue-guidelines.md` remains unchanged, so the branch does not conflict with the preserved RU client source from `tj-7zq7`.
- `search_products(ctx, query, max_price=None, min_price=None)` matches current PydanticAI behavior: `RunContext` is excluded from the tool schema, normal params are included. Checked through Context7 against PydanticAI tools documentation.
- PDF compaction uses WeasyPrint-compatible `@page`, margins, and break controls. Checked through Context7 against WeasyPrint stable documentation.
- Wazzup typing is correctly blocked/no-op instead of guessing an undocumented endpoint.

## Validation

- Reviewer ran read-only commands: `git status --short --branch`, `git diff --stat origin/main`, `git diff --check origin/main`.
- Reviewer ran syntax check for orchestration scripts: `python3 -m py_compile ...` passed.
- Full verification must be rerun after fixes.
