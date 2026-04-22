# Code Review: tj-ruue.7 Frontend AI Quality Controls

**Date**: 2026-04-22
**Scope**: Worker branch `codex/tj-ruue-frontend-ai-quality-controls` vs stage base `23f3784`
**Files**: 8 changed files
**Reviewer**: Orchestrator

## Summary

|              | Critical | High | Medium | Low |
| ------------ | -------- | ---- | ------ | --- |
| Issues       | 0        | 0    | 1      | 0   |
| Improvements | -        | 0    | 0      | 0   |

**Verdict**: PASS after local review fix.

## Issues

### Medium

#### 1. GLM-5 warning detector missed `glm5` aliases

- **File**: `frontend/admin/src/components/AIQualityControlsPanel.tsx:117`
- **Problem**: The frontend warning/override detector originally matched only `glm-5`, while backend validation in `src/llm/safety.py` treats both `glm-5` and `glm5` as GLM-5 model names. An admin entering a `glm5` model alias could get a backend 422 without seeing the required warning checkbox in the UI.
- **Impact**: Risky GLM-5 override UX was inconsistent with the backend contract, making the admin control harder to operate and debug.
- **Fix**: Fixed in review by normalizing the model string and matching both `glm-5` and `glm5`. The dashboard regression now uses `z-ai/glm5-20260211` to cover the alias.
- **Tracking**: `tj-azes` created and closed.

## Improvements

None requiring follow-up.

## Positive Patterns

- The UI uses the existing admin API contract instead of adding new backend trigger endpoints.
- Controls are scoped by `bot_qa`, `manager_qa`, and `red_flags`, matching the backend config model.
- Risky full transcript and GLM-5 settings require explicit acknowledgements and render backend warnings.
- Regression coverage exercises API payloads, default disabled state, warnings, tooltips, and manual trigger surface text.

## Escalation

No senior escalation required. This is an admin frontend addition over the already reviewed backend contract.

## Validation

- Context7 React docs checked for controlled `<select>`/checkbox patterns and nested state updates.
- `node frontend/admin/tests/ai_quality_controls_dashboard_regression.mjs` -> passed.
- `node frontend/admin/tests/ai_quality_controls_api_regression.mjs` -> passed.
- `uv run --extra dev python -m pytest -s tests/test_admin_dashboard_frontend.py -q` -> passed, 5 passed.
- `npm run lint` in `frontend/admin` -> passed.
- `npm run build` in `frontend/admin` -> passed.

