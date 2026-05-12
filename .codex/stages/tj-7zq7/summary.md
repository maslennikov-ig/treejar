# Stage tj-7zq7 - Communication Rules Runtime Policy

## Scope

- Locate the client-provided Russian sales communication rules.
- Preserve the original source unchanged.
- Add a compact English runtime policy to the actual LLM prompt assembly path.
- Keep factual KB/FAQ separate from behavioral/style rules.
- Add focused regression tests and run repo verification.

## Source Assessment

- Canonical repo source: `docs/04-sales-dialogue-guidelines.md`.
- Contract source pointer: `docs/02-tz-extended.md` links the client Google Doc for dialogue rules.
- Supporting derivatives: `docs/06-dialogue-evaluation-checklist.md`, `docs/dialogue-examples/README.md`, and client evidence docs.
- Ambiguity: some docs call this "17 rules"; the canonical file contains 15 numbered rules plus 3 unnumbered addenda.
- Direct Google Docs text export for the contract URL returned a sign-in/storage-access page, so this stage relies on the repo-preserved client source and keeps the external pointer for traceability.

## Delivery

- Merged to `main` as `8312661c7e4f5468999355520d9c5eb349913868`.
- Pushed feature branch `codex/communication-rules-policy` and `main`.
- GitHub Actions run `25748539979` passed `changes`, `lint`, `test`, `type-check`, and `deploy`.
- Runtime `/opt/noor/.release-sha` matched `8312661c7e4f5468999355520d9c5eb349913868`; `/opt/noor/.release-run-id` was `25748539979`.
- Post-deploy smoke passed: `verify_api.py` 7/0, health 200, dashboard anonymous 401, admin metrics anonymous 401, Telegram bad secret 403.
- No live WhatsApp testing or admin prompt/config mutation was performed.
- Admin `SystemPrompt` row creation was not necessary: `communication_rules_policy` is supplied as code default and remains overrideable by an active DB row if one is intentionally created later.

## Implementation Notes

- Built-in subagents were not used.
- Context7 PydanticAI docs were checked for static/dynamic system prompt assembly behavior.
- Source-alignment review tightened the compact policy for the genuine compliment rule, Treejar tailored-solutions value, and the 24h/3d/7d follow-up addendum.

## Runtime Path

- `src/llm/prompts.py::build_system_prompt` assembles base prompt, communication policy, language directive, and stage rule.
- `src/llm/engine.py::inject_system_prompt` injects that prompt into the PydanticAI sales agent and then appends admin behavior rules, FAQ facts, CRM context, and per-route runtime directives.
- Follow-up generation also uses `sales_agent`, so it receives the same communication policy through dynamic system prompt injection.

## Verification

- `uv run --extra dev python -m pytest tests/test_llm_prompts.py -v --tb=short` -> red before implementation (`2 failed, 7 passed`), then passed (`9 passed`).
- `uv run --extra dev python -m pytest tests/test_llm_prompts.py::test_build_system_prompt_includes_compact_communication_policy -q` -> red after source-alignment tightening, then passed (`1 passed`).
- `uv run pytest tests/test_llm_prompts.py tests/test_bot_behavior_rules.py tests/test_llm_engine.py::test_inject_system_prompt_appends_runtime_directives tests/test_llm_engine.py::test_inject_system_prompt_appends_bot_operating_rules tests/test_llm_engine.py::test_process_message_price_objection_uses_compact_sales_fallback -v --tb=short` -> passed (`14 passed`).
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run pytest tests/ -v --tb=short` -> first failed because fresh worktree lacked `frontend/admin/node_modules/esbuild`; after `npm ci` in `frontend/admin`, passed (`957 passed, 19 skipped`).
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `python3 scripts/orchestration/run_stage_closeout.py --stage tj-7zq7` -> passed; it reran code gates, full pytest (`957 passed, 19 skipped`), process verification, artifact validation, and stage-ready checks.
- `gh run watch 25748539979 --exit-status` -> passed.
- `uv run python scripts/verify_api.py --base-url https://noor.starec.ai` -> passed (`7 passed, 0 failed`).
- `ssh noor-server 'cd /opt/noor && cat .release-sha && cat .release-run-id'` -> `8312661c7e4f5468999355520d9c5eb349913868`, `25748539979`.
- Production guard checks -> health 200, dashboard anonymous 401, admin metrics anonymous 401, Telegram bad secret 403.
