---
schema_version: orchestration-artifact/v3
artifact_type: delegated-stream
stage_manifest: .codex/stages/tj-ee5f/stage-manifest.json
stream_owner: tj-ee5f-dialog-remediation
orchestration_level: slice_acceptance
scope_kind: product_slice
immediate_consumer: tj-ee5f.1 integration and release acceptance
public_facade: Noor text dialogue routing and create_quotation tool
bounded_acceptance: focused local EN/AR name-gate, catalog, quote-consent, parser, and Zoho-effect regressions
non_goals:
  - voice/STT, production transport, deploy, paid calls, Beads updates, or live side effects
evidence:
  - none
task_id: tj-ee5f.6-.9
epic_id: tj-ee5f
stage_id: tj-ee5f
session_id: tj-ee5f-dialog-remediation
milestone: dialogue and quotation remediation
milestone_status: accepted
agent_type: worker
subagent_model: inherit_orchestrator
reasoning_effort: inherit_orchestrator
model_reasoning_rationale: stateful sales routing and idempotent external effects require careful focused verification
repo: treejar
branch: codex/tj-ee5f-dialog-acceptance
base_branch: codex/tj-ee5f-remediation
base_commit: 9234909
worktree: /home/me/code/treejar/.worktrees/tj-ee5f-dialog-remediation
write_zone:
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/llm/verified_answers.py
  - src/integrations/inventory/zoho_inventory.py
  - tests/test_llm_engine.py
  - tests/test_llm_quotation.py
  - tests/test_verified_answers.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.6-9-dialog-remediation.md
success_criteria:
  - name gate resumes the typed original intent with language and captured identity
  - legitimate EN/AR furniture discovery and honest no-match stay on the catalog path
  - quote details are collected only after opt-in and interruptions or quote holds take precedence
  - an explicitly named exact SKU is not expanded to similar variants without a request
  - inline customer fields preserve company digits and the complete delivery address
  - retries of one inbound quote operation reuse its Zoho order and PDF while a distinct inbound can create a new quote
  - an ambiguous provider success followed by a lost response cannot deliver the quotation PDF twice
  - verified capacity and privacy constraints prevent false exact-match denial
  - comparison claims expose missing acoustic and footprint evidence and keep multi-seat prices at the SKU-unit basis
  - catalog configurations cannot claim full coverage across mixed or under-stocked product families
  - a verified opportunity with a decision horizon proposes a concrete follow-up before that horizon
selected_docs:
  - AGENTS.md
  - .codex/orchestrator.toml
  - .codex/handoff.md
  - docs/client/noor-live-sales-tool-e2e-2026-07-28.md
selected_skills:
  - orchestrator-stage
  - superpowers:receiving-code-review
  - superpowers:systematic-debugging
  - superpowers:test-driven-development
  - superpowers:using-git-worktrees
selected_agents:
  - none
catalog_candidates:
  - none
parallel_group: tj-ee5f-remediation
depends_on_streams:
  - none
parallel_decision: parallel
status: returned
delivery_method: cherry-pick
accepted_by_orchestrator: no
cleanup_status: pending
cleanup_notes: parent orchestrator owns integration and later worktree cleanup
risk_level: high
verification_tier: delta
risk_tags:
  - state-transition
  - idempotency
  - retry
  - data
  - user-flow
affected_surfaces:
  - backend
  - user-flow
invariants:
  - state-transition
  - idempotency
  - test-matrix
docs_impact: behavior
docs_reviewed: updated
docs_review_notes: this artifact records the changed behavior; release and operator documentation remain with tj-ee5f.1
verification:
  - focused RED for Arabic catalog and furniture no-match routing: failed as expected
  - focused RED for typed name-gate resume, quote hold, interruption, exact SKU, and inline fields: failed as expected
  - focused RED for duplicate quotation effects: failed with two create_sale_order calls as expected
  - correction RED for distinct inbound quote operations: failed by returning the prior SA-001 instead of creating SA-002
  - correction RED for lost provider response after accepted PDF: failed by attempting a second customer-visible send
  - focused dialogue, parser, Zoho, and idempotency pytest set: passed 14
  - correction focused same-message, distinct-message, legacy-v1, and process propagation set: passed 4
  - correction focused quotation retry and compatibility set: passed 7
  - acceptance correction RED for catalog match, evidence, coverage, cross-sell, and timed follow-up: failed as expected
  - acceptance correction focused catalog and opportunity set: passed 19
  - targeted Ruff check: passed
  - targeted Ruff format check: passed
  - targeted Mypy for engine and Zoho Inventory client: passed
  - git diff --check: passed
  - product system-prompt delta and captured-identity source scan: empty
  - artifact validator: passed
changed_files:
  - src/integrations/inventory/zoho_inventory.py
  - src/llm/engine.py
  - src/llm/order_quote_routes.py
  - src/llm/verified_answers.py
  - tests/test_llm_engine.py
  - tests/test_llm_quotation.py
  - tests/test_verified_answers.py
  - .codex/stages/tj-ee5f/artifacts/tj-ee5f.6-9-dialog-remediation.md
explicit_defers:
  - tj-ee5f.1 owns combined full release gates, independent review, deployment, and production readback
  - no live Zoho or WhatsApp effect was performed in this local stream
---

# Summary

Fixed four connected sales-dialogue failures without adding captured scenario
sentences to product logic or growing the product system prompt.

The name gate now stores a versioned pending intent with language and captured
identity, then resumes that intent after the customer supplies a name. Arabic
and English furniture discovery uses general catalog signals instead of false
service escalation.

Quotation flow now respects explicit quote holds, objections, corrections, and
delivery questions before continuing quote collection. Product selection asks
for quote consent before customer/PDF details, and an explicitly named full SKU
is not widened to similar variants.

Customer details use delimiter-aware labeled-field parsing. Zoho contact and
sales-order payloads have typed shapes, preserve full delivery addresses, reuse
exact existing contacts after duplicate conflicts, and store a versioned
quotation-effect fingerprint. Repeating the same quote request returns the
already-sent result without creating another order or sending another PDF. The
fingerprint is scoped to the stable inbound message ID when available, and a
bounded versioned journal lets an older inbound retry remain idempotent even
after a newer quote was created. A different inbound message may create a new
quote for unchanged lines. Direct tool calls keep a conservative content-based
fallback; legacy v1 content-only effects are never trusted for a real identified
inbound. A retry after draft creation must verify the stored Zoho order before
resuming.

PDF delivery now derives a stable, hashed CRM idempotency key from the inbound-
scoped quotation effect, without storing the raw provider message ID. The
`pdf_sending` state is committed before dispatch, and delivery uses the audited
media path while retaining generic messaging-provider compatibility. On a lost
response after provider acceptance, the retry reconciles the provider duplicate
and produces only one customer-visible PDF.

Production acceptance feedback also exposed four catalog-consultation gaps.
Capacity and privacy constraints now stay attached to catalog searches, so a
verified four-person private workstation is not denied as missing. Product
results expose compact fact-status flags for requested but unsupported acoustic
or footprint claims and identify a multi-seat catalog price as one complete SKU
unit, not a per-seat amount.

For complete or cheaper configurations, the search may inspect up to five
catalog candidates and reports stock coverage only for one unambiguous requested
product family. Mixed chair/desk results are never summed into a false complete
configuration. When configured cross-sell rules return nothing, one
complementary in-stock catalog item may be selected through the existing catalog
search, with no invented product or price. A verified CRM opportunity with a
known decision horizon now asks to agree a specific earlier follow-up.

# Scope / Routing

The production changes are limited to deterministic routing, typed metadata,
catalog vocabulary, parsing, and external-effect idempotency. Exact production
transcripts appear only in tests. No chat model prompt, voice path, configuration,
database schema, REST/webhook contract, Beads state, or stage manifest changed.

# Verification

The final focused set passed 14 tests covering Arabic discovery, honest
furniture no-match, typed name-gate resume, delimiter-safe inline details,
quote opt-in, general quote holds, delivery interruption, exact-SKU filtering,
address payloads, duplicate-contact recovery, Zoho payload creation, and
quotation idempotency.

The correction set additionally passed four focused tests for immediate
same-message retry, a distinct-message new quote, retrying the first message
after the second, legacy-v1 isolation for a real inbound, and propagation of the
source message ID through `process_message` into `SalesDeps`.

Targeted Ruff lint and formatting checks passed for all seven changed source and
test files. Targeted Mypy passed for the two changed production modules, and
`git diff --check` passed. The product prompt file has no delta, and the
production-source scan found none of the captured customer identities used by
the regression tests. Artifact validation passed against the owning stage
manifest.

The final correction set passed seven focused quotation tests, including
provider-success/lost-response retry, same- and distinct-message behavior,
legacy-effect isolation, the standard quotation path, missing catalog images,
and preservation of real Zoho order identifiers.

The production-acceptance correction set passed 19 focused tests covering the
existing catalog contracts plus structured private/capacity matching, compact
evidence limits, SKU-unit pricing, per-family stock coverage, mixed-family
fail-closed behavior, verified cross-sell fallback, and a one-week follow-up for
a two-week decision horizon.

# Delivery / Cleanup

Returned to the parent orchestrator as a single correction commit on
`codex/tj-ee5f-dialog-acceptance`. No push, deploy, production mutation, paid
call, or external message was performed.

# Risks / Follow-ups / Explicit Defers

The parent integration stage must run the one combined release gate, independent
review, canonical deploy/readback, and protected provider-originated production
acceptance before closing the epic. This stream supplies local proof only and
does not claim production acceptance.
