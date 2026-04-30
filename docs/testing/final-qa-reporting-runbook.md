# Final QA / Reporting Runbook

Scope: `tj-final27.7` QA/reporting final acceptance.

## Safety Rules

- Do not enable scheduled AI Quality Controls in production without explicit approval.
- Do not run a live QA sample against production conversations without explicit approval.
- Keep transcript mode at `summary` by default.
- Use `full` transcript only when the operator explicitly accepts the full-transcript warning override.
- Keep manual or daily-sample checks capped with low `daily_budget_cents`, `max_calls_per_run`, and `max_calls_per_day`.

## Local Verification

Run the focused QA/reporting suite:

```bash
uv run --extra dev python -m pytest -s tests/test_quality_job.py tests/test_manager_job.py tests/test_reports.py tests/test_reports_manager.py -q
```

Run the quality gates before handoff:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
git diff --check
```

## Admin Checks

1. Open the admin dashboard with an authenticated admin session.
2. Confirm AI Quality Controls load with all scopes set to `disabled`.
3. For a manual-only check, set only the intended scope to `manual`, keep transcript mode `summary`, and set low call caps.
4. Do not use `daily_sample` or `scheduled` in production unless that exact run is approved.
5. Generate the weekly operations report from the admin report action. This is read-only and returns report data/text without sending Telegram.
6. Confirm the report includes bot QA, manager QA, conversion/refusal, feedback, and LLM cost-control fields.

## Known Reporting Semantics

- Bot QA is reported through `avg_quality_score`.
- Manager QA is reported through manager review count, score, response time, conversion, and leaderboard fields.
- Refusal is a current-model proxy: cancelled deals plus closed conversations without a Zoho deal.
- Feedback uses `feedbacks` rows in the report period.
- Cost-control fields include chat message cost plus QA LLM attempt cost, tokens, cache tokens, and budget-block count from `llm_attempts`.
