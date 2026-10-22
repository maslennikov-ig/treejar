# Stage tj-asty — Surpass Nikita (2026-10-22)

Branch: codex/tj-asty-surpass-nikita (local only, not deployed).

- tj-asty.1: src/llm/package_math.py (pure VAT/line/package/budget math),
  src/llm/package_evidence.py (per-turn priced lines, package blocks, get_stock
  enrichment); claim contract restates ×1.05/×0.05; budget phrasing parsed for
  the budget check only (search constraints stay model tool arguments).
- tj-asty.2: escalation_policy B2B routes; specialist_out_of_catalog_scope is a
  non-pausing lead (notify_manager_escalation pause_bot=False); reference +
  brief directive; handoff_brief_allowed in the reply policy; prompt updated.
- tj-asty.3: src/models/product_links.py (outside product.py so the corpus
  retrieval-contract digest stays pinned).
- tj-asty.4: inbound_batch/webhook grace window (default 0); manager message
  keeps manual_takeover (spec said pending; pending sends a fallback reply).
- tj-asty.5: scenarios C-Layan, D-Rami; checks tool_evidence, escalation_route,
  b2b_handoff_with_references; live_only reply checks; plan-driven dry stub.

Acceptance: ruff/format/mypy green; pytest 4464 passed, 20 skipped; dry replay
22 pass / 0 fail; live $0.062 total, final receipts pass
(docs/reports/2026-10-22-surpass-nikita-replay*.json).
Explicit defer: tj-z3hw — delivery-fee facts absent from docs/faq.md.
