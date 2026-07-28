---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-r1f3/stage-manifest.json
stream_owner: ai-engineer-output-enforcement
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: root-orchestrator
public_facade: process_message LLMResponse customer-text boundary
bounded_acceptance: deterministic enforcement and shared smoke classification for the two immutable attempt-3 failures
non_goals:
  - broad factual-claim filtering, prompt changes, second model calls, provider smoke, deploy, production mutation, customer messaging, CRM, Zoho, quotation, or order actions
evidence:
  - preserved-attempt-3
  - local-red-green
task_id: tj-r1f3-implementation
epic_id: tj-r1f3
stage_id: tj-r1f3
session_id: tj-r1f3
milestone: grounded customer-output enforcement implementation
milestone_status: accepted
agent_type: ai_engineer
subagent_model: inherit_orchestrator
reasoning_effort: high
model_reasoning_rationale: High reasoning was used for a critical LLM customer-output contract and cross-language false-positive risk.
repo: treejar
branch: codex/tj-r1f3-output-enforcement
base_branch: main
base_commit: f9db816d9faf3dce94954ad69d900a9681af9e17
worktree: /home/me/code/treejar/.worktrees/tj-r1f3-output-enforcement
write_zone:
  - src/llm/grounding_output.py
  - src/llm/engine.py
  - scripts/verify_model_routes.py
  - tests/test_llm_grounding_output.py
  - tests/test_llm_engine.py
  - tests/test_scripts_verify_model_routes.py
  - .codex/stages/tj-r1f3/stage-manifest.json
  - .codex/stages/tj-r1f3/artifacts/tj-r1f3-implementation.md
  - .superpowers/sdd/tj-r1f3-implementation-report.md
success_criteria:
  - exact attempt-3 model outputs are repaired before frame and media capture
  - smoke evaluation imports the production classifier and rejects exact and equivalent delegated phrasing
  - EN and AR safe controls, fail-closed fallback, metadata, media, and stock tool evidence remain correct
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-r1f3/artifacts/tj-r1f3-root-cause.md
  - .codex/goals/tj-r1f3/scope-criterion-snapshot.json
  - .codex/stages/tj-r1f3/stage-manifest.json
  - .codex/stages/tj-r1f3/results/postdeploy-smoke-attempt-3.json
selected_skills:
  - /mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md
  - /mnt/c/Users/masle/.codex/superpowers/skills/test-driven-development/SKILL.md
selected_agents:
  - ai_engineer
catalog_candidates:
  - none
parallel_group: output-enforcement-implementation
depends_on_streams:
  - tj-r1f3-root-cause
parallel_decision: sequential
status: accepted
delivery_method: n/a
accepted_by_orchestrator: yes
cleanup_status: pending
cleanup_notes: Implementation and review fixes are returned for orchestrator review; orchestrator owns acceptance and worktree cleanup.
risk_level: high
verification_tier: delta
risk_tags:
  - public-api
  - user-flow
affected_surfaces:
  - backend
  - user-flow
invariants:
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: Added the tracked implementation artifact and TDD report; Graphify remains optional and is not configured.
verification:
  - exact attempt-3 process_message and smoke RED reproducers: failed for the intended raw-output and false-negative reasons before implementation
  - three independent review regression reproducers: failed for the intended evidence-context and classifier-grammar reasons before review fixes
  - uv run pytest the eight focused review regression cases -q --tb=short: passed with 8 tests
  - three re-review clause-boundary reproducers with negative controls: nine intended failures and eight passes before fixes
  - uv run pytest the seventeen focused re-review cases -q --tb=short: passed with 17 tests
  - third re-review structural stock matrices: pure failed 12 cases, runtime failed 6 cases, and smoke failed 12 cases for the intended typed-present, natural-phrasing, and warehouse/delivery boundary reasons before fixes
  - third re-review focused GREEN: pure passed 40 tests, runtime passed 18 selected tests, and smoke passed 18 selected tests
  - fourth re-review RED: pure, runtime, and smoke each failed 12 cases for the intended status-order, direct-SKU, and plural unrelated-object reasons; coordination follow-up failed 2 pure, 2 runtime, and 3 smoke cases
  - fourth re-review focused GREEN: pure passed 64 tests, runtime passed 49 selected tests, and smoke passed 37 selected tests
  - final bounded review RED: pure, runtime, and smoke each failed 12 cases for contracted copulas, dash/newline/list boundaries, and single-quoted future text
  - final bounded review focused GREEN: pure passed 80 tests, runtime passed 65 selected tests, and smoke passed 37 selected tests
  - bounded interaction RED: three immediate conditional-list cases failed in pure and runtime; smoke additionally false-rejected one quoted present claim
  - bounded interaction focused GREEN: 43 pure, 41 runtime-selected, and 59 smoke-selected tests passed with ordinary unquoted/list assertions retained as negative controls
  - final broad-smoke RED: the public quote masker was absent and three otherwise-valid unquoted broad stock assertions passed smoke while three quoted controls passed
  - final broad-smoke focused GREEN: public helper passed its offset/apostrophe test and 47 quote-aware broad/SKU smoke cases passed
  - uv run pytest focused grounding-output, engine, stock-tool, and smoke cases -q --tb=short: passed with 57 tests
  - uv run pytest tests/test_llm_grounding_output.py tests/test_llm_engine.py tests/test_scripts_verify_model_routes.py -q --tb=short: passed with 612 tests
  - independent delta review of 8b9ece6..d616463: APPROVED with no critical findings
  - postdeploy smoke attempt 4 on exact release 0dd9615 and CI/deploy run 30330683062: immutable script result 4/5 with exactly five paid synthetic calls and no business mutation
  - exact attempt-4 medical reply local production-path characterization: classified specific_product_showroom_trial, repaired to the safe medical refusal, and reclassified with no violations
  - smoke prompt-tail RED: the synthetic system prompt did not end with the immutable grounding policy
  - smoke prompt-tail GREEN: the shared runtime finalizer preserves exactly one immutable policy copy at the final tail
  - uv run pytest tests/test_scripts_verify_model_routes.py tests/test_llm_grounding_output.py -q --tb=short: passed with 185 tests
  - independent attempt-4 delta review: APPROVED after correcting the delivery-lane audit trail; no remaining P0-P3 findings
  - uv run ruff check focused changed Python files: passed
  - uv run ruff format --check focused changed Python files: passed
  - uv run mypy src/: passed with 163 source files
  - uv run ruff check src/ tests/: passed
  - uv run ruff format --check src/ tests/: passed with 306 files already formatted
  - uv run pytest tests/ -q --tb=short: passed with 1878 tests and 19 skipped
  - scripts/orchestration/run_process_verification.sh: passed
  - uv run python scripts/orchestration/validate_artifact.py on this artifact: passed
  - uv run python scripts/orchestration/lint_stage_sizing.py --stage tj-r1f3: passed
  - git diff --check: passed
changed_files:
  - src/llm/grounding_output.py
  - src/llm/engine.py
  - scripts/verify_model_routes.py
  - tests/test_llm_grounding_output.py
  - tests/test_llm_engine.py
  - tests/test_scripts_verify_model_routes.py
  - .codex/stages/tj-r1f3/results/postdeploy-smoke-attempt-4.json
  - .codex/stages/tj-r1f3/results/postdeploy-verification.md
  - .codex/stages/tj-r1f3/stage-manifest.json
  - .codex/stages/tj-r1f3/artifacts/tj-r1f3-implementation.md
  - .superpowers/sdd/tj-r1f3-implementation-report.md
explicit_defers:
  - the attempt-4 smoke-harness correction still requires independent review, deployment, exact readback, and a new separately quota-bound provider retest; attempt 4 remains immutable failed evidence
  - mixed-language and unseen paraphrase coverage remains a bounded residual risk; expansion to broad factual validation requires a separately reviewed scope
---

# Summary

Added a pure deterministic customer-output guard for two bounded semantics:
specific-product showroom trials and direct or delegated future stock checks.
`process_message()` now enforces model text after unmasking and existing repairs,
but before assistant-frame and deferred-media capture. Unsafe sentences are
removed when bounded repair is certain; otherwise a localized EN/AR response
fails closed. Static, quotation, and handoff response builders are unchanged.

The model-route smoke evaluator imports the production classifier, so the exact
attempt-3 delegated-stock false negative and equivalent team/staff forms cannot
drift from runtime enforcement.

Postdeploy attempt 4 proved the deployed runtime guard recognizes and repairs
the new specific-chair sentence, but also exposed a separate harness mismatch:
the synthetic system prompt placed case material after the immutable grounding
policy. The local correction now uses the same prompt finalizer as production,
preserving exactly one policy copy at the final prompt tail. The failed attempt
and its five-call quota remain immutable evidence; no provider retry was made.

The review correction makes present stock confirmation evidence-aware: the
customer text is preserved only after successful current-turn inventory tool
evidence, including routes that run with copied dependency objects. Without
that evidence the same claim fails closed. Explicit inventory-team promises and
SKU-only showroom trials are now covered by the same shared classifier.

The re-review correction generalizes that evidence allowance across bounded
SKU/quantity present-confirmation forms while keeping it clause-local. Any later
future-check clause is still removed, even in the same sentence. For delegated
mixed-object checks, explicit stock or inventory now takes precedence over
unrelated delivery wording; standalone delivery, dimension, and colour checks
remain unchanged.

The third review correction makes that distinction explicit in the output
contract. A bounded present stock statement now has its own
`UNVERIFIED_STOCK_CONFIRMATION` reason and is classified independently from a
future/delegated check. Current-turn inventory evidence authorizes only the
present statement; it never suppresses a later promise. Natural positive and
negative present forms are covered. Strong stock words such as stock,
inventory, availability, available, unavailable, and out-of-stock wording
remain unsafe in future checks. Warehouse is weak context, so an explicit
delivery-only check is preserved while mixed stock-and-delivery remains unsafe.

The fourth review correction normalizes optional `currently`/`not` ordering,
extends the same evidence gate to direct SKU-shaped present assertions, and
pluralizes unrelated dimension/measurement/size/colour objects. Direct
assertions are recognized at assertion clause boundaries and coordination, but
not inside quoted or `if`/`whether`/`when` conditional clauses. This keeps the
parser bounded to SKU-shaped present stock states. An existing name-gate test
fixture was corrected from an unsupported no-tool `CH-620 is available` claim
to neutral request-continuation wording; no fabricated inventory evidence was
introduced.

The final bounded correction adds common `isn't`/`aren't` copulas, with curly
apostrophes normalized without changing span offsets. Assertion boundaries now
include em/en dashes, newlines, and newline list markers. Paired straight and
curly single-quoted text is masked while word-internal apostrophes remain
visible, so contractions and possessives cannot masquerade as quotations. The
smoke evaluator now passes raw reply text to all shared production grounding
classifiers; its normalized copy remains limited to legacy smoke checks.

The bounded interaction correction removes the smoke-only raw phrase loop for
SKU present claims, leaving the shared quote-aware production classifier as the
single decision source. Immediate `if`/`whether`/`when` scope now propagates
across one colon/newline list boundary. Ordinary newline/list SKU assertions
without that immediate conditional introducer remain evidence-gated.

The final smoke correction exposes the production quote masker as
`visible_grounding_text()`. Legacy broad non-SKU phrase and inventory patterns
now inspect its quote-masked normalized output. This restores rejection of
unquoted `product/chair is in stock` and `available now` assertions without
false-rejecting quoted equivalents or widening the SKU-bounded runtime guard.

# Scope / Routing

The changed AI path is `process_message()` → model/tool orchestration →
`_build_llm_response()` → unmask/closed-question/opening repairs → new
grounding enforcement → frame/media capture → `LLMResponse`. No prompt,
retrieval, provider, persistence, tool execution, or outbound delivery contract
was expanded. The guard adds no model call, network latency, or token cost.

The implementation followed the accepted debugger stream and used TDD
sequentially because code semantics depended on the diagnosed output boundary.
Graphify was not configured, and no catalog asset was selected.

# Verification

RED proved that both exact `process_message()` model outputs passed through
unchanged and that the exact delegated attempt-3 stock promise passed smoke.
GREEN covers exact outputs, EN/AR safe and unsafe matrices, safe negations,
general showroom quality, conditional samples, unconfirmed stock, real
tool-backed stock confirmation, quoted and unrelated checks, deterministic
fallback, preserved model/token/cost metadata, and media selection from the
enforced text. Review RED/GREEN additionally covers evidence-gated present
stock confirmation, an explicit inventory-team future promise, and a SKU-only
showroom trial at pure, `process_message()`, and smoke boundaries. Re-review
coverage locks two additional present-confirmation forms, same-sentence
present-plus-future repair, mixed stock/delivery classification, and standalone
unrelated-check controls. Third-review coverage adds typed unverified-present
classification, natural availability/quantity/positive/negative forms, strong
future-stock lexemes, and delivery-only warehouse controls at all three
boundaries. Fourth-review coverage adds optional modifier order, direct
SKU-status assertions after sentence/coordination boundaries, conditional and
non-SKU controls, and singular/plural unrelated warehouse checks. Final-review
coverage adds contracted negative states, dash/newline/list assertions, paired
single-quote safety, and contraction/possessive negative controls. Interaction
coverage locks quoted-present smoke alignment and immediate conditional-list
scope while retaining unquoted/list negative controls. Final broad-smoke
coverage locks quoted and unquoted non-SKU stock wording plus the public
masker's offset and word-apostrophe contract.

The original three affected test files passed 612 tests, and the independent
delta review approved the final quote-aware smoke correction with no critical
findings. After attempt 4, the prompt-tail correction passed 185 focused tests
and a fresh full local gate with 1878 tests and 19 skips, plus repository-wide
Ruff, format, `src/` Mypy, and process verification. The detailed commands and
failure evidence are in `.superpowers/sdd/tj-r1f3-implementation-report.md`.

# Delivery / Cleanup

The original implementation lane performed no provider smoke, deployment, live
call, customer send, production mutation, Zoho/CRM action, quotation, or order
action. In the later explicitly authorized delivery lane, exact release
`0dd9615a16fdf4eb17abe156551c53fb77f39c21` was deployed through CI run
`30330683062`, read back successfully, and one bounded synthetic OpenRouter
smoke consumed exactly five paid calls with no retry or business mutation.
That immutable attempt returned 4/5 and remains failed evidence.

The local smoke-harness prompt-tail correction is accepted for review but is
not yet delivered. Stage completion remains pending on its integration,
deployment/readback, and a new separately quota-bound passing smoke. Cleanup
remains owned by the orchestrator.

# Risks / Follow-ups / Explicit Defers

Residual risk is bounded to unseen paraphrases, especially mixed-language
outputs. The fail-closed path limits user-visible harm for recognized forms,
but broader factual-claim enforcement is intentionally outside this task. The
attempt-4 quota is exhausted. The harness correction still requires
deployment/readback and a new separately quota-bound provider smoke before
stage acceptance.
