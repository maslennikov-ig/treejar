---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-r1f3/stage-manifest.json
stream_owner: debugger
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-r1f3 output-enforcement implementation stream
public_facade: process_message LLMResponse customer-text boundary
bounded_acceptance: root-cause map and focused red-test contract for two immutable attempt-3 failures
non_goals:
  - implementation, provider calls, deployment, production mutation, customer messaging, or broad grounding-policy redesign
evidence:
  - preserved-attempt-3
  - local-focused-probes
task_id: tj-r1f3-root-cause
epic_id: tj-r1f3
stage_id: tj-r1f3
session_id: tj-r1f3
milestone: grounded customer-output enforcement diagnosis
milestone_status: replan-required
agent_type: debugger
subagent_model: inherit_orchestrator
reasoning_effort: role_default
model_reasoning_rationale: High reasoning was assigned for a critical customer-output safety boundary and cross-route false-positive risk.
repo: treejar
branch: codex/tj-r1f3-output-enforcement
base_branch: main
base_commit: b2f74088a0b83147503a1d7d8cd536e3e17639e8
worktree: /home/me/code/treejar/.worktrees/tj-r1f3-output-enforcement
write_zone:
  - .codex/stages/tj-r1f3/artifacts/tj-r1f3-root-cause.md
success_criteria:
  - trace provider/model output through the returned LLMResponse and identify the narrow deterministic enforcement point
  - distinguish production enforcement from synthetic smoke evaluation and specify focused red and safe-control tests
  - record one evidence-backed root-cause hypothesis plus false-positive, localization, tools/media, quote/order, and metadata risks
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - .codex/stages/tj-r1f3/stage-manifest.json
  - .codex/stages/tj-r1f3/results/postdeploy-smoke-attempt-3.json
  - .codex/stages/tj-r1f3/results/postdeploy-verification.md
selected_skills:
  - /mnt/c/Users/masle/.codex/superpowers/skills/systematic-debugging/SKILL.md
selected_agents:
  - debugger
catalog_candidates:
  - none
parallel_group: root-cause-map
depends_on_streams:
  - none
parallel_decision: parallel
status: accepted
delivery_method: merge
accepted_by_orchestrator: yes
cleanup_status: blocked
cleanup_notes: The accepted diagnosis was merged into main; stage worktrees and branches remain intentionally retained until the parent tj-ee5f integration consumes the final evidence.
risk_level: high
verification_tier: delta
risk_tags:
  - user-flow
  - public-api
affected_surfaces:
  - backend
  - user-flow
invariants:
  - test-matrix
docs_impact: docs-only
docs_reviewed: updated
docs_review_notes: This artifact records the root-cause map, enforcement boundary, test contract, and explicit residual risks; no product or operator docs were changed.
verification:
  - uv run pytest tests/test_scripts_verify_model_routes.py -q --tb=short: passed with 30 tests
  - uv run pytest three focused process_message pass-through and media tests -q --tb=short: passed with 3 tests
  - direct local evaluation of attempt-3 captured and safe-control replies: passed and reproduced the missing-stock evaluator false negative
  - uv run python scripts/orchestration/validate_artifact.py on this artifact: passed
  - uv run python scripts/orchestration/lint_stage_sizing.py --stage tj-r1f3: passed
  - git diff --check: passed
  - root review of path tracing, reproducer, test contract, and premortem risks: passed
changed_files:
  - .codex/stages/tj-r1f3/artifacts/tj-r1f3-root-cause.md
explicit_defers:
  - implementation, red-to-green execution, release verification, deployment, and provider smoke remain with later authorized streams
  - Arabic violation-corpus adequacy requires focused implementation tests; no external language/model call is needed for that work
---

# Summary

The two attempt-3 failures have one shared production cause: the final core-chat
model text is treated as trusted after prompt generation. The prompt is
advisory, and no deterministic grounding inspection or repair runs before
`LLMResponse.text` is returned. The medical output was caught only by the
standalone smoke evaluator; the delegated stock promise also bypassed that
evaluator because its future-check expression recognizes first-person
`I/we ... check` forms but not delegated forms such as
`arrange for our team to check and get back`.

The smallest reliable production insertion point is the final text assembly in
`process_message._build_llm_response()`, after PII unmasking and all existing
text repairs, but before legacy-frame capture, deferred-media selection, and
`LLMResponse` construction. A bounded pure policy module should inspect and
deterministically repair or fail closed on the two prohibited semantics there.
The smoke script may reuse the same low-level classifiers to prevent drift, but
its evaluation remains release evidence, not runtime enforcement.

# Scope / Behavior Boundary

## Actual customer-response path

1. `process_message()` is the core entry and promises an `LLMResponse`
   (`src/llm/engine.py:9716-9735`).
2. `_run_agent()` calls `run_agent_with_safety()` and returns the PydanticAI
   run result (`src/llm/engine.py:10636-10649`). All ordinary model branches,
   including mixed product/service, product preference, service policy, order
   handoff, and the default route, eventually call `_build_llm_response()`
   (`src/llm/engine.py:10705-10716,10775-10787,10860-10879`;
   `src/llm/order_quote_routes.py:485-507`).
3. `_build_llm_response()` takes `result.output`, unmasks PII, applies only the
   closed-question and first-turn-opening guards, captures assistant state,
   selects referenced deferred media, and returns `LLMResponse.text`
   (`src/llm/engine.py:9876-9910`). There is no grounding-output check.
4. Chat persists `llm_response.text`, formats that same text for WhatsApp, and
   sends it; media is sent only afterward
   (`src/services/chat.py:1486-1515,1544-1555`). The WhatsApp formatter is not a
   semantic guard. There is therefore no later production repair boundary
   before customer delivery.

Static code-owned replies use `_build_static_response()` or the explicit policy
handoff builder (`src/llm/engine.py:9912-9973`). They are not the source of the
captured failures and should remain outside the first minimal intervention.
This avoids applying stock/showroom language heuristics to deterministic
quotation, selection-confirmation, manager-handoff, and error messages.

## Smoke script is not production enforcement

`scripts/verify_model_routes.py` builds synthetic, forced-tool OpenRouter
requests from isolated case evidence (`lines 208-235`) and evaluates the
returned structured `decision`/`reply` (`lines 360-495`). It directly calls
`/chat/completions` (`lines 608-623,653-700`); it does not call
`process_message()`, execute Noor tools, create an `LLMResponse`, persist a
conversation, or gate customer delivery.

The exact local attempt-3 probe reproduced:

- `medical_inference`: rejected for a specific-product trial.
- `missing_stock`: accepted with no failures, despite
  `arrange for our team to check and get back to you`.

The cause of the second result is exact: `_FUTURE_CHECK_RE` only permits
`let me|I|we` immediately before `check|confirm|look up|verify`
(`scripts/verify_model_routes.py:101-104`), so the delegated actor and
`arrange ... team` construction do not match.

# Findings

## P1 / must-fix — Advisory prompt is the only grounding control on model text

- **Evidence:** the immutable policy explicitly prohibits both behaviors
  (`src/llm/communication_policy.py:94-121`), yet attempts 2 and 3 repeated the
  specific-chair showroom offer after wording corrections, and attempt 3 added
  a delegated future stock check. `_build_llm_response()` has no corresponding
  deterministic inspection.
- **Root-cause hypothesis:** GLM-5.2 can violate an advisory prompt under
  nondeterministic generation, and the application currently trusts that
  output. Prompt-only control therefore cannot establish the immutable
  customer-output invariant.
- **Confidence:** high for the application boundary; the exact provider-internal
  reason for choosing those words is not observable and is not required to
  diagnose the missing application control.
- **Disconfirming evidence needed:** a separate semantic guard after
  `LLMResponse` construction but before persistence/send would disconfirm the
  boundary finding. The inspected chat path shows only persistence, WhatsApp
  formatting, and send, so no such guard was found.
- **Expected risk reduction:** deterministic removal of the two known
  unsupported semantics before persistence and delivery, independent of model
  compliance.

## P1 / must-fix — Smoke future-check detector has a confirmed delegated-actor gap

- **Evidence:** the exact attempt-3 reply evaluates `passed=True`; the direct
  probe and regex grammar agree. The existing 30-test smoke suite passes, so
  current coverage does not include this captured form.
- **Smallest correction:** make delegated future-check classification actor- and
  clause-aware (for example, arranging for `team/staff/colleagues` to
  `check/confirm/verify` and later `get back/contact/reply`), while preserving
  negation and completed-tool language. Put the shared semantic classifier in
  production code and import it into the smoke evaluator rather than letting a
  second regex vocabulary drift.
- **Expected risk reduction:** the release smoke cannot report green for the
  exact delegated behavior that production enforcement must repair.
- **Confidence:** high; directly reproduced without provider/network calls.

# Smallest Reliable Enforcement Design

Add one pure, deterministic customer-output policy component under `src/llm/`
with two operations: inspect typed violation reasons and return either the
unchanged text or a bounded repaired/fail-closed text. Call it once in
`_build_llm_response()`:

1. `result.output`
2. PII unmask
3. existing closed-question and opening repairs
4. **new grounding-output enforcement**
5. legacy/frame capture from the enforced text
6. media selection from the enforced text
7. `LLMResponse`

This order matters:

- It inspects exactly what the customer would see, rather than masked text.
- Persisted dialogue frames cannot learn an unsafe promise.
- Product media is suppressed when repair removes the product reference,
  preventing text/image divergence.
- Usage, token counts, cost, and the original route/model label can be preserved.

The implementation should use bounded asserted-clause classification, not raw
substring deletion:

- **Specific-product showroom trial:** distinguish an asserted offer
  (`visit ... experience/try the Nova chair`) from general showroom quality
  language and safe negation (`cannot confirm that this chair is available to
  try`).
- **Delegated future stock check:** distinguish a future/delegated promise from
  a completed, successful current-turn stock tool result and from a statement
  that stock remains unconfirmed.

If a violating clause cannot be removed with high confidence, replace the whole
answer with a deterministic EN/AR safe response for that violation. Do not use a
second model call for repair: it would retain nondeterminism, add latency/cost,
and could repeat the violation. Enforcement itself should not raise; on
classifier/repair uncertainty it should fail closed to the localized safe
template and emit a bounded structured log without raw customer text or PII.

Do not put the first implementation only in `src/services/chat.py`: that layer
has already lost tool/evidence context, would miss non-chat consumers of
`process_message()`, and would apply broadly to deterministic/human handoff
messages. Do not import the script evaluator into production. The shared
classifier belongs under `src/llm/`; the script is a consumer.

# Focused Red Tests

## Production tests that fail on current main

Add two `tests/test_llm_engine.py` cases using the established mocked
`sales_agent.run`/`_FakeAgentResult` pattern and non-first-turn history:

1. Return the exact attempt-3 medical reply. Assert the returned
   `LLMResponse.text` does not assert or offer experiencing the Nova chair in
   the showroom, while it still safely declines the unsupported medical
   outcome. Current main returns the captured text after only the existing
   guards, so the test is red.
2. Return the exact attempt-3 missing-stock reply. Assert the returned text
   preserves that current stock is unconfirmed but contains no arrangement for
   the team to check and get back later. Current main returns the delegated
   promise, so the test is red.

Also assert in both cases that `response.model` and provider usage token fields
remain unchanged by repair. For a repaired specific-product response with
queued media, assert media not referenced by the repaired text is suppressed.

## Pure policy matrix

The pure component should have exact captured red cases plus unchanged
safe-control cases:

- approved general showroom:
  `You're welcome to visit ... experience our product quality`;
- explicit safe negation:
  `I can't confirm that a specific chair will be available to try`;
- medical decline with no showroom substitute;
- conditional samples depending on project requirements;
- missing stock stated as unconfirmed with no later-check promise;
- completed real tool-backed stock confirmation, accepted only with reliable
  current-turn confirmation evidence;
- EN and AR equivalents for each violation and safe response;
- quoted customer language and unrelated checks do not trigger.

For tool-backed coverage, drive the real `get_stock` test double so a successful
tool result records confirmation before the final response; do not simply set a
boolean in the assertion. A failed inventory lookup must remain unconfirmed and
must not authorize an availability claim.

## Smoke evaluator tests

In `tests/test_scripts_verify_model_routes.py`, feed the exact two replies from
the attempt-3 JSON. The missing-stock case is red on current main because it is
accepted; the medical case locks the already-correct rejection. Keep the safe
general-showroom, safe-negation, safe-unconfirmed-stock, conditional-sample, and
tool-backed wording controls green. These tests validate release evidence only;
they do not substitute for the two production `process_message()` red tests.

# Integration Risks and Controls

- **False positives:** actor/check regexes can misclassify past completion
  (`our team checked`), customer quotations, negated offers, checking dimensions
  rather than stock, or harmless general showroom quality language. Scope
  patterns to asserted clauses, stock/inventory objects, future/delegated
  modality, and explicit negation handling. Do not ban `experience` or
  `get back` globally.
- **Localization:** Noor supports EN and AR
  (`src/services/customer_language.py:6-30`; `src/schemas/common.py:10-13`).
  English-only patterns fail open on Arabic; transliteration and mixed-language
  output are residual risks. Use explicit EN/AR classifiers and deterministic
  localized fallback templates. Wrong-language output should take the
  conversation language's safe template.
- **Tool evidence:** successful `get_stock()` marks
  `SalesDeps.inventory_confirmed=True`; failed lookup leaves it false
  (`src/llm/engine.py:8566-8592,8969-9022`). Some routes call `_run_agent()` with
  `dataclasses.replace(deps, ...)` and then invoke `_build_llm_response()` without
  passing that copied `response_deps` (`src/llm/engine.py:10705-10716,
  10775-10787,10864-10875`; `src/llm/order_quote_routes.py:485-507`).
  A broader stock-assertion guard must therefore propagate the exact run deps or
  use a shared per-run evidence ledger; reading only the original `deps` can
  falsely reject a successful tool-backed answer.
- **Tools and media:** run enforcement before
  `_deferred_product_media_for_response()`. Otherwise a repaired text can still
  trigger a product image/caption based on the pre-repair answer. Tool calls may
  already have caused permitted internal effects; text repair must not replay
  tools.
- **Quote/order paths:** deterministic quote creation responses pass through
  `_build_static_response()` and use `quotation_created`/media suppression;
  keep them outside the initial guard. Model-assisted order-handoff passes do
  use `_build_llm_response()`, so classifiers must remain stock/showroom-specific
  and must not treat ordinary `manager will review` or confirmed quotation text
  as a stock-check promise.
- **Existing test contradiction:** at least one current mocked name-gate resume
  test returns `CH-620 is available` without simulating a successful stock tool
  and asserts that text (`tests/test_llm_engine.py:3011-3035`). If availability
  enforcement is added, update the fixture to establish real confirmation or
  change it to an unconfirmed response; do not weaken the guard to preserve an
  unsafe mock.
- **Model metadata:** preserve the original `LLMResponse.model`, token usage,
  and cost attribution. Appending an unplanned model suffix would fragment
  route metrics and test contracts; instead emit a separate structured repair
  reason/count. Provider token counts describe the generated output, not the
  shorter repaired text, and should remain documented as such.
- **PII and logging:** inspect after unmasking but never log the raw repaired or
  rejected text. Record only violation kind, route/model, language, and whether
  the response was unchanged, repaired, or replaced.

# Verification

Validated locally, without provider/network/live calls:

- immutable evidence and exact attempt-3 outputs;
- all model-result return branches through `_build_llm_response()`;
- downstream persistence/send/media ordering;
- current 30-test smoke evaluator suite;
- three focused process-message pass-through/media tests;
- exact evaluator false negative for delegated stock and correct rejection for
  the medical reply;
- safe general-showroom, medical-decline, and unconfirmed-stock probes.

Still requires implementation/runtime verification:

- red-first production tests and red-to-green pure policy matrix;
- EN/AR classifier and deterministic fallback behavior;
- successful and failed real tool-double paths, especially copied deps;
- quote/order and deferred-media regression edges;
- full affected/release gates and independent delta review;
- only after separate authorization: deployment, release/model/service readback,
  and a bounded fresh provider smoke plus manual semantic review.

# Delivery / Cleanup

No product code, tests, services, external systems, or stage bookkeeping outside
this artifact were changed. The artifact is returned for orchestrator review;
delivery is not accepted and cleanup remains pending.

# Risks / Follow-ups / Explicit Defers

Priority is P1/must-fix before mutation-capable E2E acceptance. Residual risk
after the bounded fix is paraphrase coverage, especially Arabic/mixed-language
forms and evidence propagation through copied deps. The next implementation
stream should begin with the two production red tests, then the pure EN/AR
matrix and exact smoke regression; any expansion to broad factual-claim
validation should be a separately reviewed scope decision rather than hidden in
this two-failure repair.
