# Treejar dead-code / legacy / hygiene audit — origin/main @712a905

Read-only. Checkout: /home/me/code/treejar/.worktrees/tj-audit-20261101.
Method: vulture60 list re-verified with `git grep -w` over src/tests/scripts/migrations (+ docs/.codex counted separately); a name-based AST reachability pass over src/
(roots = module-level code, decorated defs [FastAPI/pydantic/PydanticAI tools/dataclass], WorkerSettings; string literals count as references; imports alone do not).
Raw lists: scratch/reach.py, scratch/reach_base.txt (as-is), scratch/reach_noroutes2.txt (with the never-invoked legacy adapters cut).

Headline: 6,188 lines of top-level defs in src/ are unreachable from runtime roots as the code stands. Cutting the two legacy adapters that
`process_message_impl` accepts and documents as "never invoked" brings that to 11,530 lines (engine.py 5,324 of 11,409; catalog_planning.py 1,851;
order_quote_routes.py 991 of 1,180; fact_extractor.py 786; verified_answers.py 525; claim_contract.py 438).

## Findings (prioritized)

### F1 P1 dead-code — Legacy order/quote + pending-reference adapters are passed in but never invoked (~5.3k lines)
- src/llm/engine.py:11390-11394 wraps `_pending_reference_route_for_turn` (engine.py:3573) and `_order_quote_route_for_turn` (order_quote_routes.py:388, 793-line function) and passes them to `process_message_impl`.
- src/llm/message_processor.py:374-375 stores them on `_Turn`; `git grep -F "turn.order_quote_route"` / `"turn.pending_reference_route"` / `"order_quote_route("` → 0 call sites.
- message_processor.py:1336-1340 docstring: "Legacy adapters are accepted only for API compatibility and are never invoked."
- Kept alive by: `_MESSAGE_PROCESSOR_RUNTIME_DEPENDENCIES` tuple (engine.py:378-400, ruff-silencer), `_ENGINE_BIND_NAMES` (order_quote_routes.py ~45-136, ~60 engine names bound via globals()), and AST tests tests/test_llm_engine.py:65 and :133, tests/test_deterministic_routes.py:25 (`_ROUTE_SOURCES` reads order_quote_routes.py).
- Transitive dead (only reachable from these): _quote_candidates_from_last_assistant_selection (engine.py:7208, 260 lines), _build_purchase_selection_confirmation_text (4568), _variant_options_response (4420), _extract_purchase_selection (2039), _resolve_exact_quote_candidate_sku (3772), _resolve_purchase_selection* (2263, 4218, 4078, 4119), _store_pending_* (4901, 4976, 5034, 7508), _suspend_quote_workflow (7997), catalog_planning `_verified_prose_response/_render/_directive/_mask` (3314, 3209, 3268, 3156), order_handoff.is_high_confidence_first_turn_order (order_handoff.py:65), dialogue/order_runtime.run_order_runtime (46) … full list in reach_noroutes2.txt.
- Only `QuotationItem` (order_quote_routes.py:146) is live (engine.py:232, quotation_completion.py:28, quotation_retry.py:243).
- .codex/project-index.md:22 already calls them "legacy order adapters (not called by incoming chat)".
- Action: move QuotationItem (e.g. to response_runtime or a small quotation module), delete order_quote_routes.py, `_pending_reference_route_for_turn` and the transitive set, drop the `pending_reference_route/order_quote_route` params from process_message_impl/_load_turn/_Turn, rewrite/delete the 2 AST tests + route-registry test sources. Size L. Risk: large test churn (test_llm_engine.py references 65 now-dead names); deterministic_routes registry entries for removed routes must go; behavior risk nil at runtime (provably uncalled), but owner decision recommended because tests/AST guards were deliberately written around these (tj-rt7w lineage).

### F2 P1 dead-code — LangGraph "dialogue kernel" is wired out; langgraph dep only serves dead code
- `run_dialogue_kernel` (dialogue/runner.py:102) referenced only in engine.py:91 import and the `_MESSAGE_PROCESSOR_RUNTIME_DEPENDENCIES` tuple (engine.py:388). No caller.
- `_COMPILED_GRAPH = _build_graph().compile()` (runner.py:896) is built at import time, used only by run_dialogue_kernel (runner.py:133). `_decide_node` (241, 266 lines) etc. all dead.
- `record_legacy_route` (runner.py:171) is called from message_processor.py:528 but `self.dialogue_kernel_result` is never assigned (only default None at message_processor.py:400) → always returns early → no-op.
- Settings never read in src: dialogue_kernel_mode, dialogue_kernel_trace_enabled, dialogue_kernel_enforced_flows (config.py:68-70); only tests read them (tests/test_dialogue_config.py, test_dialogue_runner.py, test_llm_engine*.py).
- Live remnants: `quote_consent_signal` (runner.py:624, used by engine.py:6240) + its helpers; DialogueState/expected_answers types are still used by engine.
- dialogue/order_runtime.py has a second compiled graph (384) used only via run_order_runtime → dead once F1/F3 land. After both, `langgraph` (pyproject.toml:46) has no runtime user.
- Test-only: tests/test_dialogue_runner.py (1043 lines), test_dialogue_config.py, test_dialogue_state.py (reducer helpers set_last_question/mark_frame_interrupted/push_expected_answer_frame/build_trace/append_trace_bounded, reducer.py:154-275), test_dialogue_order_runtime.py.
- Action: move quote_consent_signal (+helpers) to its own module, delete the graph, record_legacy_route + call site, dialogue_kernel_result field, 3 settings, tests; then drop langgraph. Size M-L. Owner decision (kernel was a rollout feature, metadata key `dialogue_kernel` still read by DialogueState.load — keep reader for old rows or accept ignore).

### F3 P1 dead-code — Customer-facts fast extractor layer unreachable (~1k lines)
- `_run_customer_facts_layer` engine.py:6621 (104 lines) → zero src callers (tests only: test_llm_engine_customer_facts.py, test_customer_detail_address_regression.py).
- It is the only caller of fact_extractor.extract_customer_facts (fact_extractor.py:319) and customer_memory.apply_extracted_facts (services/customer_memory.py:212) → fact_extractor.py 786 of 1311 lines dead (PydanticAIFastCustomerFactExtractor:277, _extract_*_facts 380-1016), customer_memory.py 142 lines, engine helpers _record_customer_facts_trace (6402), _customer_facts_past_order_response (6516), _quote_details_from_customer_facts (6346), _apply_customer_facts_to_legacy_quote_details (6373).
- Settings never read: customer_facts_trace_enabled, customer_facts_fast_extractor_enabled (config.py:74-75). customer_facts_mode IS read (customer_intent_tools.py:448/531, message_processor.py:887) — keep.
- Action: delete chain + tests/test_fact_extractor.py parts that only cover it. Size M. Owner decision: confirm customer memory is now written only via model-owned intent tools (customer_intent_tools).

### F4 P1 dead-code — `_turn_runtime_directives` (engine.py:690) and the consultation directive family are test-only
- 0 src callers; 23 test refs + 4 script refs (model_battle). It is the only caller of claim_contract.consultative_opening_directive (claim_contract.py:882, 157 lines), solution/comparison/sizing/project/b2b/next_contact/substantive directives (claim_contract.py:743-1385, ~438 lines total) and opening_guard.canonical_opening (opening_guard.py:99).
- Tests that only cover dead code: test_dialogue_consultative_opening.py, test_dialogue_solution_consultation.py, test_dialogue_comparison_consultation.py, test_dialogue_sizing_assumption.py.
- Action: delete or re-home if the owner wants these directives back in the live prompt (they may have been intentionally retired when the model-owned flow landed). Size M. Owner decision.

### F5 P2 test-only-legacy — verified_answers policy engine mostly unused (~525 lines)
- evaluate_verified_answer_policy (verified_answers.py:1012) only used by engine.py:5679 inside `_is_substantive_name_gate_request` (dead, tests only). Dead with it: classify_question (753), classify_social_intent (701), requires_manager_commitment (838), detect_sales_fallback_intent (892), build_service_* / build_sales_fallback_response / build_clarification_response (1103-1211), is_social_greeting_query (667), is_order_status_query (662).
- is_quote_or_proposal_request (874) is imported by order_quote_routes only → dies with F1.
- tests/test_verified_answers.py covers these.
- Action: delete after F1. Size M.

### F6 P2 dead-code — catalog_planning re-export shim and dead planners
- catalog_planning.py:4179-4348 `__all__` lists 168 names (mostly private) and engine.py:351-373 re-binds them all into engine globals "so src.llm.engine.* test patch points remain authoritative". Many are dead: _try_verified_catalog_plan (3845, 271 lines), _materialize_verified_catalog_recovery (3431, 261 lines), catalog_anchor / catalog_anchor_line / anchor_* (852-990), validate_catalog_decision family (441-730), coverage solver (1392-1690), opening catalog options (2884-3053).
- tests/test_llm_catalog_decision.py imports these through engine.
- Action: delete dead planners; shrink __all__ to real exports; migrate tests to patch catalog_planning directly. Size M-L.

### F7 P2 dead-code — small truly-dead functions (no reference anywhere outside their def; safe)
| file:line | symbol | lines |
|---|---|---|
| src/llm/engine.py:1963 | is_exact_quote_request | 3 |
| src/llm/engine.py:7846 | _exact_quote_followup_candidates | ~ |
| src/llm/engine.py:5865 | _UnlabeledQuoteBrief (class) | ~ |
| src/llm/order_quote_routes.py:169 | build_declared_static_response | ~ |
| src/llm/message_processor.py:194 | _has_escalation | 2 |
| src/llm/sales_turn_guard.py:152 | _question_lines | 2 |
| src/llm/verified_answers.py:667 | is_social_greeting_query | 3 |
| src/llm/conversation_summary.py:129 | needs_conversation_summary_refresh | 6 |
| src/dialogue/runner.py:48 | expected_answer_match_payload | 25 |
| src/dialogue/order_state.py:191 | has_complete_lines (property) | ~ |
| src/integrations/catalog/treejar_catalog.py:110 | TreejarCatalogClient.get_stats | 2 |
| src/integrations/inventory/zoho_inventory.py:201 | _stock_snapshot_record | 7 |
| src/integrations/inventory/zoho_inventory.py:69,74 | STOCK_SNAPSHOT_FRESH_SECONDS, STOCK_SNAPSHOT_LOCK_TTL_SECONDS (only a docstring mention in sync.py:472) | 2 |
| src/quality/evaluator.py:652 | _build_rule_applicability | 8 |
| src/quality/evaluator.py:732 | _build_dialogue_prompt | 10 |
| src/quality/service.py:135 | get_unreviewed_completed_conversations | 28 |
| src/quality/service.py:172 | get_recent_conversation_ids_with_assistant_activity | 18 |
| src/rag/pipeline.py:19 | PgVectorStore (class, 83 lines) | 83 |
| src/integrations/vector/base.py:6 (+ package) | VectorStore Protocol — only PgVectorStore implements it | 24 |
| src/services/canonical_admin_seed.py:831 | ensure_canonical_seed | 25 |
| src/services/followup.py:943 | run_payment_reminders (not in worker; _run_payment_reminders_with_db is driven by run_automatic_followups at followup.py:970) | 14 |
| src/services/notifications.py:75 | _mask_phone | 5 |
| src/services/auto_faq.py:132,338 | _normalize_to_english (test-only), save_confirmed_faq_candidate (only via save_to_faq, test-only) | 78 |
| src/schemas/common.py:83, schemas/conversation.py:19,50 | ErrorResponse, ConversationCreate, MessageCreate | 11 |
Action: delete. Size S. Risk: none at runtime; run ruff/mypy/pytest.

### F8 P2 test-only-legacy — functions whose only references are tests (or scripts)
- core/security.py:7 compute_signature — whole module test-only (tests/test_security.py); real HMAC code lives in telegram_webhook.py:26 and inbound_batch.py:104.
- dialogue/catalog_refs.py:181/264/314 parse_catalog_reference, resolve_catalog_references, resolve_catalog_references_from_db (+_find_by_variants 325, _find_unique_by_sku_stem 343) — tests/test_dialogue_catalog_refs.py only.
- zoho_inventory.py:137 reset_rate_limit_cooldown (7 test refs — test helper living in src; keep or move to tests/support), ZOHO_STOCK_SNAPSHOT_LOCK_KEY (67) test-only and duplicated by stock_state.LOCK_KEY (stock_state.py:17).
- engine.py: _capture_expected_answer_frames_from_assistant_response (1914), _is_name_gate_completion_reply (5521), _store_name_gate_pending_request (5623), _quote_offer_allowed_for_turn (6254), _is_neutral_detail_capture_update (6854), _guard_premature_quote_detail_collection (6871), _last_assistant_offered_quote_for_selection (7470), _sales_opportunity_title (9918; pinned by test_llm_engine.py "readers" assertion ~l.120), _sales_opportunity_response (10262), _extract_terse_quote_customer_details (5972).
- sales_turn_guard.py:559 commit_to_what_you_deferred (+_sentence_bounds 594) — 11 test refs.
- rag/indexer.py (whole module, 278 lines; index_documents:20) — tests/test_indexer.py only; company_faq.py:3 notes KB had no FAQ rows. rag/embeddings.py:121 index_knowledge_base — tests only. (search_knowledge itself is live: message_processor.py:1276.)
- services/owner_presentation.py:158/165/177 format_criterion_status, quality_rule_name, manager_rule_name; owner_review_formatters.format_detailed_quality_review (97, 121 lines) used only by notifications.format_quality_alert_message (200) → notify_quality_alert (461), which has 0 src callers ("Legacy notify_quality_alert should remain callable for compatibility", tests/test_telegram_notifications.py:803).
- quality/schemas.py:254/279 raw_total, attainable_weighted_score — tests + e2e scripts (keep if scripts are kept).
- quality/job.py:542 evaluate_completed_conversations — "Backward-compatible wrapper", only scripts/verify_quality.py:42 import-checks it.
- services/chat_latency.py:115-226 parse_chat_latency_line/summarize_chat_latency — tests + scripts/analyze_chat_latency.py (script-only; fine to move to scripts/).
- services/escalation_state.py:70-160 classify_pending_escalation/classify_record_source — tests + scripts/escalation_guard.py (script-only).
- grounding_output.py:637-652 contains_specific_product_showroom_trial / contains_future_stock_check / contains_unverified_stock_confirmation — script-only (e2e acceptance).
- integrations/voice/__init__.py re-exports transcribe_audio (voxtral.py:137) — runtime uses transcribe_audio_with_metadata (chat.py:1176); old wrapper is test/script only. config.voxtral_model property (config.py:164, "Deprecated Python alias") — 0 src uses (1 test, 2 scripts).
- src/llm/__init__.py lazy __getattr__ (LLMResponse/process_message) — 0 src/script users of `from src.llm import LLMResponse`; 15 test imports. Compatibility shim for tests.
- src/llm/deterministic_routes.py (297 lines) — imported only by tests/test_deterministic_routes.py (governance registry). Keep+document or move under tests/ after F1.
Action: delete or move into tests/support/scripts. Size M. Owner decision for notify_quality_alert, indexer, deterministic_routes.

### F9 P2 config-drift — settings nobody reads
- config.py:34-35 app_host/app_port — 0 readers in src/Docker/compose (still in .env.example).
- config.py:68-70 dialogue_kernel_* (F2), 74-75 customer_facts_trace_enabled / customer_facts_fast_extractor_enabled (F3) — tests only.
- config.py:127 embedding_dimension — only scripts/verify_rag_pipeline.py.
- config.py:164 voxtral_model property — deprecated alias (F8).
- .env.example: every key maps to a Settings field (no orphan env vars).
- Hardcoded manager contact in engine.py:10780-10784 (name/phone/email in quotation PDF context) — should be config/system_config.
- zoho_inventory.py:600 hardcodes "https://accounts.zoho.eu/oauth/v2/token" while zoho_crm.py:122 uses settings.zoho_crm_accounts_url (drift inside a duplicated function, see F10).
Action: delete unused fields (+ .env.example lines); move contact to config. Size S. Risk: low — Settings uses extra="ignore" (config.py:22-26), so leftover keys in prod .env will not break startup.

### F10 P2 duplication — concrete pairs
- Zoho OAuth refresh-with-Redis-lock: zoho_crm.py:83-156 `_ensure_token` vs zoho_inventory.py:559-633 `_ensure_token` (~70 lines each, same lock/recheck/refresh/parse/report flow; differ only in settings prefix + URL). → shared helper in integrations/zoho_oauth.py.
- `_normalize_text` identical: engine.py:1264 == package_evidence.py:36 (`" ".join(text.casefold().split())`); catalog_planning.py:78 is a lazy proxy to engine's. Other `_normalize_text` with different semantics: dialogue/catalog_refs.py:365, dialogue/expected_answers.py:451 (name collision, not dup).
- Phone digits: zoho_inventory.py:338 `_phone_digits` == llm/inventory_customers.py:43 `_phone_digits`; zoho_inventory.py:331 `_normalize_phone`; conversation_reset.py:46 phone_reset_variants.
- Phone masking: notifications.py:75 `_mask_phone` (dead) vs llm/pii.py:27 mask_pii vs fact_extractor.py:1257 redact_phone (dies with F3).
- Cyrillic→Latin homoglyph tables ×4: dialogue/catalog_refs.py:20 `_HOMOGLYPHS`, zoho_inventory.py:93 `_SKU_HOMOGLYPHS`, catalog_planning.py:136 `_SKU_HOMOGLYPH_TRANSLATION` (reused by catalog_references.py:21), package_math.py:25 `_HOMOGLYPHS` (lower-case variant).
- Arabic-Indic digit translation ×3 identical: claim_contract.py:485, escalation_policy.py:234, package_math.py:51 (+ variant catalog_planning.py:1176 with separators).
- Arabic letter regex ×3 with different ranges (drift): claim_contract.py:499, language_guard.py:10, decision_state.py:97.
- Stock snapshot Redis keys defined twice: stock_state.py:17-18 LOCK_KEY/LEGACY_KEY vs zoho_inventory.py:66-67 ZOHO_STOCK_SNAPSHOT_KEY/ZOHO_STOCK_SNAPSHOT_LOCK_KEY.
- Greeting/thanks token sets in engine.py:~445-462, decision_state.py:~225-240, verified_answers.py:~252-265 (context-specific; low value to merge).
- httpx clients: 13 `httpx.AsyncClient(` sites; one-off unpooled clients in zoho_crm.py:119, zoho_inventory.py:596, wazzup.py:181/227, wazzup_webhook.py:115, voxtral.py:175, engine.py:3746 (latter is inside dead F1 code). Low priority.
Action: merge helpers into src/core/text.py / integrations/zoho_oauth.py. Size M. Risk: low; homoglyph/regex merges change matching semantics — test carefully.

### F11 P2 hygiene — giant functions
>300 lines: order_quote_routes.py:388 _order_quote_route_for_turn 793 (dead, F1); services/chat.py:1060 _process_batch_inner 726; engine.py:9073 search_products (tool) 653; engine.py:10403 _create_quotation 537; services/reports.py:86 generate_report 325; services/outbound_audit.py:343 send_wazzup_media_with_audit 304.
250-300: dashboard_metrics.py:134 (295), telegram_webhook.py:823 (272), catalog_planning.py:3845 (271, dead), dialogue/runner.py:241 (266, dead), catalog_planning.py:3431 (261, dead), engine.py:7208 (260, dead), engine.py:10008 (252).
Largest files: engine.py 11,409; catalog_planning 4,348; verified_answers 2,453; chat.py 1,785; zoho_inventory 1,743.
Action: after F1-F6 engine.py should drop to ~6k. Refactor _process_batch_inner/search_products/_create_quotation separately (L, behavior risk).

### F12 P3 hygiene — repo clutter
- Dockerfile:71 `COPY docs/ docs/` ships 403 docs files (6.8 MB) into the image; runtime reads only docs/faq.md (company_faq.py:23, canonical_admin_seed.py:49) and indexer reads 04-/05- docs (test-only module). → copy only needed files.
- docs/: 403 files; reports 106, research 51 + `docs/Research` 14 (case-colliding dirs — breaks on case-insensitive FS), superpowers 42, plans 30 (incl. Claude plan-mode names goofy-riding-pizza.md, hashed-booping-pebble.md, toasty-munching-ritchie.md, zesty-swimming-reddy.md), 37 root files incl. session-6/7 prompts, next-phase-prompt.md, task-plan.md, tz.md.
- Byte-identical duplicates: docs/deep-research-prompt.md == docs/Research/deep-research-prompt.md; docs/deep-think-prompt.md == docs/DeepThink/deep-think-prompt.md.
- output/pdf/*.pdf (6 tracked client PDFs, 1.6 MB) and .superpowers/sdd/*.md (8 tracked agent reports) — artifacts in git.
- Two template roots: templates/sqladmin/login.html (root) vs src/templates/quotation/template.html (pdf generator) — fine functionally, confusing.
- .agent/ (tracked, 44 files: skills/workflows/scripts deploy.sh, release.sh) vs .agents/ (gitignored, local-only). GEMINI.md on origin/main is the stale 79-line memory file (develop branch, dev env, `.agent/workflows/push.md → .agent/scripts/release.sh`). NOTE: the main checkout (/home/me/code/treejar, branch codex/tj-asty-surpass-nikita) has UNCOMMITTED edits/deletions in .agent/, GEMINI.md, .codex/*, scripts/orchestration/run_process_verification.sh, plus untracked docs/antigravity-operations-reference.md — an in-flight harness migration by another owner. Do not touch these paths in a cleanup branch.
- CLAUDE.md (28 lines) is a thin @AGENTS.md adapter — fine.
- frontend/landing IS live: Dockerfile:6-8/74 builds it, src/main.py:262-276 serves it at "/". Keep.
- docker-compose.dev.yml last touched 2026-03-04, models a dev env on `develop`; repo is main-only now — owner decision.
- .github/workflows/check-logs.yml and set-wazzup-channel.yml are self-described "(one-time)" manual ssh workflows → delete (owner ok).
- migrations: 24 files, single linear chain, one head (2026_10_13_fk_query_indexes); no empty upgrades, no merges. Mixed revision-id styles (001, fake-hex a1b2c3d4e5f6, date strings) — cosmetic, never rename.
- Unused ORM columns/relationships per vulture (models/referral.py:24,29; customer_memory.py:124,133-134,195-196; product.py:36 synced_at; outbound_message.py:49,58 — note error_details IS written by outbound_audit) — schema-level, needs migration; keep.

### F13 P3 hygiene — stale scripts
- Not referenced by CI/docs/tests/other scripts: scripts/model_battle_claim_pass_run.py, model_battle_counterset_run.py, model_battle_judge.py, model_battle_paraphrase_run.py (all 2026-08-05 one-off battle runs), repl_simulation.py (2026-04-02), test_wazzup_channels.py (calls private `_request`), test_openrouter.py (only aiohttp user — pyproject.toml:162 deptry DEP003 ignore for aiohttp exists for it; prints key prefix), verify_llm.py, verify_zoho.py.
- verify_*.py family (crm/db/followups/inventory/pdf/quality/rag/rag_pipeline/voice/telegram/wazzup/api) is driven only by scripts/verify_all.sh (not CI), mostly untouched since 2026-04; verify_quality.py only import-checks a compat wrapper.
- All script `from src… import` names resolve (engine re-exports catalog_planning __all__, so model_battle_claim_pass_run's `_claim_contract_directive` import works).
Action: delete unreferenced one-offs; keep verify_all family or move to scripts/smoke/. Size S.

### F14 P3 tests
- No xfail anywhere; skips are only env-gated (DB/Zoho/OpenRouter/Wazzup keys: tests/conftest.py:75, tests/integration/conftest.py:75-102, test_dialog_real_llm.py:56-60, test_corpus_bridge_semantic_catalog_evidence.py:244, test_wazzup_outbound_safety.py:339).
- No test imports a missing src module/name (namespace packages verified).
- Test files that (mostly) exercise only dead code: test_dialogue_runner.py, test_dialogue_config.py, test_dialogue_state.py (reducer half), test_dialogue_order_runtime.py, test_dialogue_catalog_refs.py (3 of 8 imports), test_dialogue_consultative_opening.py, test_dialogue_solution_consultation.py, test_dialogue_comparison_consultation.py, test_dialogue_sizing_assumption.py, test_indexer.py, test_security.py, test_llm_catalog_decision.py, test_llm_order_handoff.py, test_fact_extractor.py (mostly), test_llm_engine_customer_facts.py, test_customer_detail_address_regression.py, test_verified_answers.py (5 of 7), test_owner_review_formatters.py, test_faq_translation.py, test_chat_latency.py (script support), test_deterministic_routes.py; test_llm_engine.py imports 154 engine names, 65 of which are dead after F1.
