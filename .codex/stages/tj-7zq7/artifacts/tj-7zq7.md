---
task_id: tj-7zq7
stage_id: tj-7zq7
repo: treejar
branch: codex/communication-rules-policy
base_branch: origin/main
base_commit: 6848bd26f2040227b8ec7940901c3413990fa2f6
worktree: /home/me/code/treejar/.worktrees/communication-rules-policy
status: returned
verification:
  - uv run --extra dev python -m pytest tests/test_llm_prompts.py -v --tb=short: red before implementation, then passed
  - uv run --extra dev python -m pytest tests/test_llm_prompts.py::test_build_system_prompt_includes_compact_communication_policy -q: red after source-alignment tightening, then passed
  - uv run pytest tests/test_llm_prompts.py tests/test_bot_behavior_rules.py tests/test_llm_engine.py::test_inject_system_prompt_appends_runtime_directives tests/test_llm_engine.py::test_inject_system_prompt_appends_bot_operating_rules tests/test_llm_engine.py::test_process_message_price_objection_uses_compact_sales_fallback -v --tb=short: passed
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed
  - uv run mypy src/: passed
  - uv run pytest tests/ -v --tb=short: passed after npm ci in frontend/admin
  - scripts/orchestration/run_process_verification.sh: passed
  - python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-7zq7/artifacts/tj-7zq7.md: passed
  - python3 scripts/orchestration/check_stage_ready.py tj-7zq7: passed
  - python3 scripts/orchestration/run_stage_closeout.py --stage tj-7zq7: passed
changed_files:
  - .codex/handoff.md
  - .codex/project-index.md
  - .codex/stages/tj-7zq7/artifacts/tj-7zq7.md
  - .codex/stages/tj-7zq7/summary.md
  - src/llm/communication_policy.py
  - src/llm/prompts.py
  - tests/test_llm_prompts.py
---

# Summary

The client-provided Russian communication rules were located and preserved unchanged in `docs/04-sales-dialogue-guidelines.md`. `docs/02-tz-extended.md` is the contract pointer to the source Google Doc, while `docs/06-dialogue-evaluation-checklist.md`, `docs/dialogue-examples/README.md`, and client evidence docs are supporting derivatives rather than the canonical runtime source. A direct Google Docs text export was attempted for `1wPOL3H4zg1qwyJ33FF_kLzICI7nTpEpnVUialJ-JXuA`, but Google returned a sign-in/storage-access page, so this stage relies on the repo-preserved client source plus the contract pointer.

The runtime implementation adds `src/llm/communication_policy.py` with a 1580-character compact English policy derived from the Russian rules. It explicitly covers the client rules for Siyyad/Treejar greeting, preferred form of address, friendly active listening, genuine specific compliment, Treejar-as-tailored-solutions positioning, needs discovery, drill-and-hole principle, quote variants, complete-package benefit, contact collection, closing/next step, and the 24h/3d/7d follow-up cadence through allowed templates. `src/llm/prompts.py::build_system_prompt` now loads this as a separate `communication_rules_policy` SystemPrompt component between the base prompt and language/stage directives. This keeps behavior/style policy separate from FAQ/KB facts and keeps it present even when `base_prompt` or stage prompts are overridden through SystemPrompt storage.

# Verification

- `uv run --extra dev python -m pytest tests/test_llm_prompts.py -v --tb=short` -> red before implementation (`2 failed, 7 passed`), then passed (`9 passed`).
- `uv run --extra dev python -m pytest tests/test_llm_prompts.py::test_build_system_prompt_includes_compact_communication_policy -q` -> red after source-alignment tightening, then passed (`1 passed`).
- `uv run pytest tests/test_llm_prompts.py tests/test_bot_behavior_rules.py tests/test_llm_engine.py::test_inject_system_prompt_appends_runtime_directives tests/test_llm_engine.py::test_inject_system_prompt_appends_bot_operating_rules tests/test_llm_engine.py::test_process_message_price_objection_uses_compact_sales_fallback -v --tb=short` -> passed (`14 passed`).
- `uv run ruff check src/ tests/` -> passed.
- `uv run ruff format --check src/ tests/` -> passed.
- `uv run mypy src/` -> passed.
- `uv run pytest tests/ -v --tb=short` -> initially failed on missing local frontend dependency `esbuild` in the fresh worktree; after `npm ci` in `frontend/admin`, passed (`957 passed, 19 skipped`).
- `scripts/orchestration/run_process_verification.sh` -> passed.
- `python3 scripts/orchestration/validate_artifact.py .codex/stages/tj-7zq7/artifacts/tj-7zq7.md` -> passed.
- `python3 scripts/orchestration/check_stage_ready.py tj-7zq7` -> passed.
- `python3 scripts/orchestration/run_stage_closeout.py --stage tj-7zq7` -> passed; it reran `ruff`, format check, `mypy`, full pytest (`957 passed, 19 skipped`), process verification, artifact validation, and stage-ready checks.

# Risks / Follow-ups / Explicit Defers

- Ambiguity: some repo docs call the dialogue source "17 rules", while `docs/04-sales-dialogue-guidelines.md` contains 15 numbered rules plus 3 unnumbered addenda. This stage treats that file as canonical because later client evidence docs explicitly describe it as 15 plus 3 addenda.
- The policy is ready for code review and owner sign-off. It is not deployed, pushed, merged, or applied to production/admin settings.
