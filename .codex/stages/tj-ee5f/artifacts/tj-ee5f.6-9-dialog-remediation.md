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
branch: codex/tj-ee5f-dialog-final-review
base_branch: codex/tj-ee5f-remediation
base_commit: 26e963d10d18bba52bf9b5c1263ce89b21c202bb
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
  - bounded typed catalog state preserves capacity and family across EN/AR turns
  - exact structured matching also honors explicit product line and finish constraints
  - a cross-sell is returned only when the verified selected total leaves enough budget
  - unknown explicit product and finish discriminators fail closed without an allowlist
  - an independent product intent starts a new planning epoch while an explicit continuation retains state
  - new, add, and replace actions have explicit precedence without treating another option as another order
  - explicit new intent outranks a bare reference word while a plan-specific reference retains the current epoch
  - Arabic catalog families accept conjunction and definite-article prefixes without substring matching
  - per-item and total budget limits are typed and retained independently in either clause order
  - exact product-model identifiers remain atomic across hyphens, digits, and case
  - budgeted cross-sell output cannot exceed the remainder in aggregate
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
  - independent-review RED for bounded planning state, exact discriminators, token boundaries, budget enforcement, and short horizons: failed 9 of 10 as expected
  - independent-review focused correction set: passed 25
  - second-review RED for unknown discriminators, planning lifecycle, aggregate cross-sell, and per-item caps: failed 7 of 9 as expected
  - early-review RED for generic disjoint-family reset and explicit family addition: failed 2 of 2 as expected
  - second-review confirmation RED for a hyphenated unknown model: failed 1 of 1 as expected
  - second-review focused correction set: passed 36
  - final-review RED for action precedence, mixed budget clauses, atomic model identifiers, and general privacy wording: failed 13 of 20 as expected
  - final-review reviewer RED for another-option continuation and explicit disjoint intent with a bare reference: failed as expected
  - final-review focused affected set: passed 35
  - final micro-review RED for overlapping-family intent and plan-specific continuation: failed 2 of 2 as expected
  - final micro-review transition set: passed 13
  - final micro-review Ruff, format, Mypy, diff, and artifact checks: passed
  - final Arabic micro-review RED for definite-form replacement: failed as expected
  - final Arabic micro-review focused EN/AR transition and boundary set: passed 9
  - final Arabic micro-review Ruff, format, Mypy, diff, and artifact checks: passed
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

Independent review found five remaining acceptance gaps. A bounded, versioned
catalog-planning state now carries requested capacity, product families,
complete-coverage intent, budget cap, and verified per-family totals across
turns, including Arabic requests. Family detection uses token/phrase boundaries,
so unrelated words cannot match `table`. Structured exact matching requires
explicit product-line and finish discriminators to agree and no longer treats
`dedicated` as privacy evidence.

Cross-sell eligibility is now calculated from catalog-backed selection totals
and enforced before an item is returned; an unknown or insufficient remainder
fails closed. One-day, same-day, and hourly decision horizons use a neutral
contact-time question rather than claiming a follow-up occurs before the
decision.

The second independent review removed the remaining allowlist dependency from
structured exact matching. Explicit identifiers, model/series fields, and
finish/color modifiers are extracted generically and must be confirmed by the
candidate. Catalog planning now has a bounded epoch: a new or disjoint product
intent clears stale capacity, families, total budget, and selected totals,
while referential continuation keeps the epoch and can add another family.
Per-item price limits are excluded from the total-budget field. When a verified
remainder exists, configured cross-sell candidates are reduced
deterministically to one fitting item, so their aggregate cannot exceed it.

The final review made catalog-state transitions explicit. A genuinely new
request outranks generic reference words, while `add` keeps and unions families
and `instead` replaces the family and discards stale family totals. Asking for
another cheaper option stays in the current epoch. Per-item and total caps are
parsed from every local clause, stored separately in a backward-readable
versioned state, and retained regardless of clause order.

The final micro-review separated ordinary pronouns from plan references. An
explicit `I/we need` request starts a new epoch even when it says `this home
office` and the requested family overlaps the old plan. A phrase such as `this
configuration`, `same selection`, or its Arabic equivalent retains the current
plan; explicit add and replace actions still take precedence.

The final Arabic micro-review added token-bounded support for the conjunction
and definite article on catalog-family terms. Natural forms such as
`الكراسي`, `المكاتب`, and `والمكاتب` now resolve to their typed families,
while longer unrelated words such as `المكتبة` still fail closed.

Structured product matching now keeps model identifiers such as `COMP-4`
atomic, including mixed case, so `COMP-5`, `COMP`, and `COMP-40` cannot satisfy
that request. General wording such as `with individual privacy panels` is no
longer misclassified as an explicit product discriminator.

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

The independent-review correction set passed 25 focused tests, covering prior
catalog behavior plus a real multi-turn Arabic planning context, family token
boundaries, LUMA/NOVO and finish mismatches, deterministic cross-sell budget
rejection, and neutral one-day/today/hourly follow-up wording.

The second-review correction set passed 36 focused tests, including generic
unknown line/finish mismatches, legacy-state epoch compatibility, new and
disjoint-family resets, explicit continuation with family addition, per-item
price caps, and cumulative cross-sell budget enforcement.

The final-review affected set passed 35 tests covering action precedence,
same-epoch option alternatives, explicit new intent despite a bare reference,
family replacement cleanup, both mixed-budget clause orders, atomic model
identifiers, general privacy wording, and the prior catalog/cross-sell
contracts. Targeted Ruff lint and format checks and targeted Mypy for both
production modules also passed.

The final micro-review transition set passed 13 tests covering the
overlapping-family reproduction, plan-specific continuation, prior independent
intent, EN/AR new intent, regular continuation, add, replace, and option
alternative behavior.

The final Arabic micro-review set passed nine tests covering definite-form
replacement, Arabic and English family addition, regular continuation, new
intent, and catalog-term substring boundaries.

# Delivery / Cleanup

Returned the final micro-correction as one commit on
`codex/tj-ee5f-dialog-final-review`. No push, deploy, production mutation, paid
call, or external message was performed.

# Risks / Follow-ups / Explicit Defers

The parent integration stage must run the one combined release gate, independent
review, canonical deploy/readback, and protected provider-originated production
acceptance before closing the epic. This stream supplies local proof only and
does not claim production acceptance.
