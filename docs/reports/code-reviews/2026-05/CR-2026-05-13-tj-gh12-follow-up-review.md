# Code Review: tj-gh12 follow-up review

**Date**: 2026-05-13
**Scope**: Follow-up review only for new/remaining risks after the closed 2026-05-12 report. Reviewed changed areas in `src/llm/engine.py`, proposal follow-up integration, Wazzup typing no-op, quotation template, webhook/worker wiring, and orchestration scripts.
**Verdict**: NEEDS WORK

## Summary

| Area | Critical | High | Medium | Low |
|---|---:|---:|---:|---:|
| Issues | 0 | 0 | 2 | 0 |
| Improvements | 0 | 0 | 1 | 0 |

## Issues

### Medium

#### 1. Price ranges can be parsed as SKUs and hijack normal quote/search flow

- **File**: `src/llm/engine.py:194`
- **Evidence**: `_SKU_SIGNAL_RE` accepts 1-4 letters followed by optional space/hyphen and 2-8 digits. In `extract_exact_quote_candidate`, the item tail after quantity is scanned for SKU at `src/llm/engine.py:702-710`.
- **Problem**: Natural price text like `quote 2 chairs from 500 to 600 AED` can yield `sku='FROM-500'`; `quote 2 desk 500 AED` can yield `sku='DESK-500'`.
- **Impact**: Customers asking for a quotation with budget/range can get an exact SKU fallback, missing-detail gate, or fail-closed manager escalation instead of recommendations.
- **Fix**: Reject price phrase matches before canonicalizing SKU signals.

#### 2. Stage closeout no longer enforces tracked artifacts despite contract requiring them

- **File**: `scripts/orchestration/run_stage_closeout.py:89`
- **Evidence**: `load_stage_artifacts()` returns `[]` when `.codex/stages/<stage>/artifacts` is missing, and `main()` continues. `check_stage_ready.py` also skips validation when no artifacts exist.
- **Problem**: `.codex/orchestrator.toml` still declares `artifact_required_for_stage_close = true`, but closeout can pass without any artifact.
- **Impact**: A future stage can close with no delegated artifact trail, weakening handoff/review guarantees.
- **Fix**: Restore a hard failure when `artifact_required_for_stage_close` is true and no artifacts exist.

## Improvements

### Medium

#### 1. Follow-up template sending still depends on placeholder Wazzup template payload

- **File**: `src/services/proposal_followup.py:745`
- **Current**: Proposal follow-up template mode calls `send_wazzup_template_with_audit()`, which delegates to `WazzupProvider.send_template()`.
- **Evidence**: `src/integrations/messaging/wazzup.py:335-347` explicitly says the schema is an example and assumes text-mapped templates.
- **Recommended**: Keep template sends blocked until the real Wazzup approved-template request schema is implemented and covered by tests using the confirmed payload shape.

## Positive Patterns

- Proposal follow-up sends are disabled by default and bounded by `max_per_run` / `scan_cap`.
- Wazzup typing is intentionally a no-op instead of calling undocumented provider APIs.
- Quote creation now blocks missing customer/company/address/quantity before Zoho/PDF/send.

## Escalation

- Orchestration contract behavior changed; the closeout code should match the repo contract.
- Wazzup template-send schema needs provider confirmation before enabling proposal follow-up template sends.

## Validation

- Subagent performed a narrowed read-only follow-up review.
- Full verification was not run inside the reviewer; fixes and final verification are handled by the orchestrator.
