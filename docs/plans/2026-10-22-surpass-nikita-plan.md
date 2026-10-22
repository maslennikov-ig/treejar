# Surpass «Nikita» Bot — Implementation Plan (`tj-asty`)

Canonical specification and acceptance criteria (`AC01`–`AC10`):
- Specification: `docs/specs/surpass-nikita/spec.md`
- Benchmark evidence: `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md`
- Raw shadow-test payloads: `docs/reports/2026-10-22-nikita-shadow-test-raw.jsonl`
- Beads Epic: `tj-asty` (`tj-asty.1` .. `tj-asty.5`)

## Execution Order

1. **`tj-asty.1` — Grounded Turnkey Package Math & Explicit 5% UAE VAT Transparency**
   - Add `amount_with_uae_vat` in `src/llm/money.py`.
   - Extend `_restatable_numbers` and `row_from_catalog_product` in `src/dialogue/claim_contract.py` so `excl. 5% VAT`, `+ 5% VAT` (`× 1.05` / `× 0.05`), `Qty × Unit Price` line subtotals, and multi-family turnkey package totals (`Workstation + N × Chairs`) are grounded and never stripped.
   - Enrich `search_products` and `get_stock` in `src/llm/engine.py` and response contracts in `src/llm/catalog_planning.py` with explicit `(excl. 5% VAT; X.XX AED incl. 5% VAT)` pricing, deterministic multi-unit line math, turnkey bundle totals for $N$-seat office requests, and exact budget-cap comparisons (fixing Nikita's `5,931 > 6,000` math failure).
   - Verify with `uv run pytest tests/test_claim_contract.py tests/test_llm_engine.py -k "vat or bundle or package or luma" -q`.

2. **`tj-asty.2` — Treejar B2B Handoff Routes (`Wholesale 20+ Units`, `Custom Made-to-Order`, `Specialist Out-of-Catalog`) with In-Stock Reference Options + Mini-Brief**
   - Update `critical_escalation_decision` in `src/llm/escalation_policy.py` and prompt rules in `src/llm/prompts.py` to authorize `escalate_to_manager` for:
     1. `wholesale_or_bulk_project` ($N \ge 20$ units/seats or explicit bulk/wholesale commercial discount request),
     2. `custom_made_to_order` (bespoke dimensions like 4.5m table, custom materials, built-in power modules),
     3. `specialist_out_of_catalog_scope` (non-office industrial/lab/medical equipment like laboratory fume hoods),
     while keeping ordinary office furniture searches and `"No quotation yet"` non-escalating.
   - Add `b2b_handoff_reference_directive` in `src/dialogue/claim_contract.py` / `src/llm/engine.py` so wholesale/custom handoffs call `search_products` first to present 2–3 in-stock standard reference options (with prices and native WhatsApp photos) alongside the manager handoff and 1-sentence brief qualification.
   - Ensure deferred product media is still delivered on the turn that initiates a B2B handoff when reference options are named in the reply.
   - Verify with `uv run pytest tests/test_escalation_policy.py tests/test_chat_escalation.py -q`.

3. **`tj-asty.3` — Verified Canonical Product Page Links (`treejartrading.ae/product/<slug>`) Alongside WhatsApp Product Photos**
   - Add `product_canonical_url(product)` in `src/models/product.py` using `attributes.treejar_url` / `attributes.treejar_slug` with deterministic slug fallback for snapshot fixtures.
   - Expose `Product page: https://treejartrading.ae/product/<slug>` in `search_products` (`src/llm/engine.py`) and `claim_rows` extras while keeping raw R2 asset URLs (`r2.dev`) forbidden in text and native WhatsApp image sending active.
   - Verify with focused unit tests in `tests/test_llm_engine.py`.

4. **`tj-asty.4` — Configurable First-Turn Manager Grace Window (`instant` vs `weekday_grace_window`) with Automatic Manager Takeover Detection**
   - Add `resolve_inbound_batch_defer_seconds` in `src/services/inbound_batch.py` reading `SystemConfig` keys `first_turn_manager_grace_seconds` (default `0`) and `first_turn_grace_weekdays_only` (default `"true"`).
   - Wire into `src/api/v1/webhook.py` so only Turn 1 of a brand-new conversation uses the grace window when configured, while Turn 2+ always uses the fast 5s batch window.
   - Update `src/services/chat.py` so `authorType == "manager"` marks manager takeover (`escalation_status = "pending"`) and suppresses duplicate bot generation if a human manager stepped in during the grace window.
   - Verify with `uv run pytest tests/test_webhook.py tests/test_services_chat_batch.py -q`.

5. **`tj-asty.5` — Head-to-Head Benchmark Replay Suite (`A`, `B`, `C`, `D`) & Comparison Report Update**
   - Add `tests/fixtures/scenarios/c_layan_arabic_6p_wholesale.json` and `tests/fixtures/scenarios/d_rami_fume_hood_luma_budget.json`.
   - Extend `scripts/scenario_replay/checks.py` and `scripts/scenario_replay/llm_seam.py` to validate all 4 scenarios (`A`, `B`, `C`, `D`).
   - Run `uv run python scripts/scenario_replay.py --dry` (and `--live --max-cost-usd 0.08 --receipt docs/reports/2026-10-22-surpass-nikita-replay.json` when `OPENROUTER_API_KEY` is configured).
   - Update `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md` and run `uv run ruff check src/ tests/ scripts/`, `uv run ruff format --check src/ tests/ scripts/`, `uv run mypy src/`, and focused `pytest`.
