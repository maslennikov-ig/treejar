# Stage tj-lgmg-catalog-discovery Summary

Status: local implementation complete and verified. Not committed, pushed,
deployed, or used to mutate GitHub issue state.

Scope: fix GH #55 class of premature manager handoffs where ordinary furniture
discovery turns, especially restaurant context, wardrobes after name gate, and
kids beds, were routed through verified-policy service handoff instead of
catalog/product discovery.

Current decision:
- Keep manager handoff for explicit/high-risk service or commercial topics.
- Treat common furniture category words as product signals using word-level
  matching for categories such as `wardrobe`, `bed`, `mattress`, and shelves.
- Treat furniture use-case context such as restaurant, living room, kids, cafe,
  hotel, and reception area as a bounded catalog-discovery context.
- Context-only turns without service risk now clarify instead of escalating.
- Context plus a discovery phrase such as `options` or `anything for` routes to
  product discovery.

Stage classification:
- Medium/complex staged bugfix.
- Beads task: `tj-lgmg`.
- Selected skills: orchestrator-stage, task-router, systematic-debugging,
  test-driven-development, writing-plans, verification-before-completion, and
  orchestration-closeout.
- Docs L1/L2: no external lookup needed; behavior is local deterministic
  classification and chat routing, not dependency/API/platform behavior.
- Graphify: no local graph is configured; `graphify-out/GRAPH_REPORT.md` is
  absent.

Parallel Decomposition Matrix:

| Stream | Goal | Agent | Write Zone | Dependencies | Verification | Decision | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | Issue/history/root-cause research | visible read-only Codex subagents | none | Beads/GitHub history | findings summarized before implementation | parallel completed | Independent research accelerated history comparison. |
| B | RED policy and process-message regressions | local orchestrator | `tests/` | Stream A findings | targeted pytest failures | sequential | Tests and implementation share one behavior boundary. |
| C | Verified-policy guard implementation | local orchestrator | `src/llm/verified_answers.py` | Stream B | targeted and full gates | sequential | Single write zone; avoids overlapping edits. |
| D | Stage docs and closeout | local orchestrator | `.codex/`, Beads | Streams B-C | closeout script | sequential | Requires fresh final evidence. |

Verification:
- RED:
  `OPENROUTER_API_KEY=test uv run --extra dev python -m pytest tests/test_verified_answers.py::test_policy_routes_common_furniture_categories_to_product_path tests/test_verified_answers.py::test_policy_treats_furniture_use_case_context_as_clarify_without_handoff tests/test_llm_engine.py::test_process_message_name_gate_resumes_wardrobe_request_without_handoff tests/test_llm_engine.py::test_process_message_known_customer_bed_request_uses_catalog_path_not_handoff -q`
  failed with `wardrobes/beds` classified as `service_low_risk`, restaurant
  context using `handoff`, and process-message returning `mock-model|verified-policy`.
- GREEN targeted:
  same command passed after implementation: `4 passed`.
- Guard and negative checks:
  `OPENROUTER_API_KEY=test uv run --extra dev python -m pytest tests/test_verified_answers.py::test_policy_routes_common_furniture_categories_to_product_path tests/test_verified_answers.py::test_policy_treats_furniture_use_case_context_as_clarify_without_handoff tests/test_verified_answers.py::test_policy_routes_contextual_catalog_discovery_question_to_product_path tests/test_verified_answers.py::test_policy_keeps_company_office_location_question_on_service_path tests/test_verified_answers.py::test_policy_keeps_payment_terms_on_manager_handoff tests/test_llm_engine.py::test_process_message_name_gate_resumes_wardrobe_request_without_handoff tests/test_llm_engine.py::test_process_message_known_customer_bed_request_uses_catalog_path_not_handoff tests/test_llm_engine.py::test_process_message_payment_terms_still_use_manager_handoff -q`
  passed: `8 passed`.
- Policy/order-handoff slice:
  `OPENROUTER_API_KEY=test uv run --extra dev python -m pytest tests/test_verified_answers.py tests/test_llm_order_handoff.py -q`
  passed: `48 passed`.
- New process-message regressions after formatting:
  `OPENROUTER_API_KEY=test uv run --extra dev python -m pytest tests/test_llm_engine.py::test_process_message_name_gate_resumes_wardrobe_request_without_handoff tests/test_llm_engine.py::test_process_message_known_customer_bed_request_uses_catalog_path_not_handoff -q`
  passed: `2 passed`.
- `uv run ruff check src/ tests/`: passed.
- `uv run ruff format --check src/ tests/`: passed after formatting the added
  test block.
- `uv run mypy src/`: passed, `Success: no issues found in 158 source files`.
- First full pytest failed because `frontend/admin` dependencies were not
  installed locally (`esbuild` missing), unrelated to this LLM change.
- After `npm --prefix frontend/admin ci --ignore-scripts`, the failing frontend
  file passed:
  `OPENROUTER_API_KEY=test uv run pytest tests/test_admin_dashboard_frontend.py -v --tb=short`
  -> `11 passed`.
- Final full pytest:
  `OPENROUTER_API_KEY=test env DYLD_FALLBACK_LIBRARY_PATH="${DYLD_FALLBACK_LIBRARY_PATH:-/opt/homebrew/lib}" uv run pytest tests/ -v --tb=short`
  passed: `1430 passed, 19 skipped`.
- Stage closeout:
  `scripts/orchestration/run_stage_closeout.py --stage tj-lgmg-catalog-discovery`
  passed, including ruff, format-check, mypy, full pytest, process
  verification, artifact validation, stage-ready check, documentation review,
  project-index review, and debt marker scan.

Documentation:
- docs-reviewed: updated - this stage summary, local implementation artifact,
  handoff, and stage plan record the behavior change and verification evidence.
- project-index: reviewed-no-change - no stable entrypoints, routes,
  subsystem ownership, integrations, or verification commands changed.
- graph-reviewed: no-change-needed - no Graphify report/config is present.

Residual / handoff:
- No live WhatsApp E2E, deploy, GitHub issue mutation, PR, push, or merge was
  performed in this stage.
- Local `frontend/admin/node_modules` was installed to satisfy existing
  frontend regression tests; it is ignored and not part of tracked changes.
- Beads `tj-lgmg` remains the task truth for GH #55 until delivery/issue
  closure is authorized.
