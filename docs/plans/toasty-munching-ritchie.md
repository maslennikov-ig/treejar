# Tester feedback 2026-09-23 (Angela): triage and repair plan

## Context

Angela ran scenario routes A (Nadia, 4-person office, LUMA/NOVO) and B (Aisha, CH 616 chairs)
from `docs/client-answers/angela-noor-live-demo-2026-09.html` on test WhatsApp 0665 against release
`071b0e3`. Production evidence (read-only DB + worker logs, times UTC):

- Route A: conversation `207f7c10…` (14:43–15:10), repeated as `fa224cab…` (15:43–).
- Route B: conversation `d24c5360…` (15:14–15:17).

All four complaints are real defects. Root causes are confirmed from logs, not guessed.

| # | Symptom | Root cause (evidence) |
|---|---------|-----------------------|
| 1 | Two workstations offered, photo sent for LUMA only | Media reference filter `_product_media_is_referenced` (`src/llm/response_runtime.py:138-166`) requires the full `name_en`/SKU words in the reply. NOVO's catalog name is `4 Person Face to Face Table SKYLAND NOVO 2400`; the reply said `SKYLAND NOVO 2400` → dropped. Log: `Suppressed 8 deferred product media item(s) not referenced` (14:44:21). |
| 2 | "Exact item isn't confirmed in the catalog" even though it found LUMA/NOVO; repeated in every turn | `classify_product_match` (`src/llm/verified_answers.py:1306-1355`) marks as exact only when every query word occurs in name/description/category. Model queries are verbose ("Compare … for privacy, collaboration, and current price"), and `_catalog_search_query_with_constraints` (`src/llm/catalog_planning.py:1171-1197`) also appends the persisted `requested_seats=4` → "4 person". Result is "nearby". `engine.py:10254-10263` + contract `catalog_planning.py:2151-2162` then order the model to say "exact item not confirmed". The customer-selected SKU is never treated as resolved. |
| 3 | After LUMA was chosen, bot re-lists both products with prices again, asks already-answered priority | Selection not treated as closing the comparison: 14:55 "For the LUMA setup, is your main priority collaboration or separation?" (asked right after she chose LUMA), 14:57 re-lists LUMA + NOVO with price/stock. Drivers: `substantive_reply_directive` (`src/dialogue/claim_contract.py:1252-1267`) demands a verified product/price each reply; search contract "lead with up to 3 concrete options" (`catalog_planning.py:2190-2200`); no persisted "selected item" guard. Same shape at 15:05: "I need 2 workstations" after picking 9719-4 → bot re-offers 9719-1/-2. |
| 4 | CH 616 NEW black found, then "not confirmed" one message later, alternative offered | Local `products.stock` for `CH 616 NEW black` = 0; vector search filters `stock > 0` (`src/rag/pipeline.py:128`, `in_stock_only=True` default). Turn 1 found it only via `get_stock('CH 616 NEW black')` → Zoho live stock 1, price 295. Turn 2 the model did two `search_products` calls only (filtered out) → "not confirmed". Verified product facts are not carried across turns (`catalog_planning.py:2257-2313` rebuilds per turn). |

Side findings (same logs, lower priority):
- False-positive guard `Reply asserts a prepared quotation with no successful call` fired on "No quotation has been prepared" (both 616 turns).
- Local catalog stock (0) disagrees with Zoho live stock (1) for CH 616 NEW black.
- Latency: 1.5–2 min per reply (e.g. queue_wait 64 s + llm 35 s at 15:15). Not raised by the tester; record only.

Principle (Beads memory `treejar-dialogue-fundamental-fixes`): durable state/slot guards in shared
modules, no phrase-level hotfixes; cover related flows with tests.

## Plan

One stage, one worktree/branch from `main` (`codex/tj-<id>-tester-0923`), Beads epic with four child
tasks (one per defect) plus one for the side guard. Delivery/deploy only with fresh owner authority.

### T1. Product photos for every offered product
- In `src/llm/response_runtime.py` `_product_media_is_referenced`: also accept a match on the
  product's stable model reference, i.e. the brand + model-code tail of `name_en`
  (e.g. `SKYLAND NOVO 2400`, `LUMA 9719-4`, `CH 616 NEW`) and the SKU's model code. Reuse the existing
  model-code normalisation used by the Arabic test (`test_product_media_reference_matches_arabic_response_by_stable_model_code`).
  Guard against false positives: `NOVO 2400` must not match `MEETING TABLE SKYLAND NOVO 2400` when a
  closer candidate (the offered one) exists. Prefer the candidate whose price also appears in the reply.
- Tests in `tests/test_llm_engine.py` near 2614: two products offered, one named by short model name
  → both images; sibling-SKU (meeting table / two-person table NOVO 2400) not sent.

### T2. Exact-vs-nearby classification and the repeated caveat
- `src/llm/verified_answers.py` `classify_product_match`: treat a candidate as exact when the query
  contains its model code/SKU reference (brand+model or SKU), regardless of extra descriptive words.
  Extend the ignored-word set with non-product filler (`compare`, `price`, `current`, `setup`,
  `recommend`, `options`, `exact`, `catalog`, …) instead of relying on all-words match.
- `src/llm/catalog_planning.py` `_catalog_search_query_with_constraints`: do not append
  `N person`/`privacy panels` to a query that already names a specific model/SKU, or for non-seat
  categories (chairs).
- Generic needs ("furniture for four people") have no "exact item", so must not produce the
  "exact requested item not confirmed" header. Add a match kind (e.g. `generic`) or skip the caveat
  when the query contains no named product/brand/model. Contract text in
  `_product_search_response_contract` (`catalog_planning.py:2144-2215`) follows that kind; remove the
  "if only nearby … say honestly" line from the exact branch.
- Tests: `tests/test_verified_answers.py` (verbose compare query naming LUMA 9719-4 → exact; generic
  4-person request → no caveat kind), `tests/test_llm_engine.py` near 7664 and 20199 (no seat suffix for
  named SKU / chairs).

### T3. Selection closes the comparison
- When the customer confirms a listed option ("yes, LUMA would be perfect"), persist the selection in
  conversation state (reuse the existing pending-selection / quote-frame slot resolved via
  `_resolve_purchase_selection`, `src/llm/engine.py:4405-4418`) and expose it to the prompt as a
  closed decision: do not re-offer the unselected alternative, do not re-ask priorities that the choice
  already answered, restate price/stock only when it changed or at the quote step.
- Relax `substantive_reply_directive` (`claim_contract.py:1252-1267`) so a qualification/next-step reply
  after a selection counts as substantive without a new product/price row.
- Quantity change after selection ("I need 2 workstations") resolves to the selected SKU unless the
  customer names another variant; ask only if no selection exists.
- Tests: multi-turn replay of conversation `207f7c10` turns 14:51–15:06 with stubbed LLM/tool
  outputs asserting: selected SKU persisted; no NOVO re-list; quantity 2 applied to 9719-4.

### T4. Named product must stay resolvable across turns
- In `search_products` (`src/llm/engine.py` ~9987): when the query contains an exact SKU/model
  reference, resolve it by direct catalog lookup (existing `_find_catalog_product_by_sku` /
  `_find_catalog_products_by_sku_stem`, `engine.py:1280-1307, 3958-3982`) **before** the vector search
  and without the `stock > 0` filter; report stock from the live source (`get_stock`) with limited/zero
  stock stated honestly instead of "not confirmed".
- Carry verified product facts (SKU, name, price, last live stock) for customer-named/selected items in
  conversation metadata so the next turn does not depend on re-search ranking.
- Tests: CH 616 NEW black with local stock 0 and live stock 1 → turn 1 and turn 2 both resolve the
  exact product; selection `1 × CH 616 NEW black + 3 × CH 460 black` records both without an alternative.

### T5 (side). Quotation-assertion guard false positive
- Locate the "Reply asserts a prepared quotation" detector in `src/llm/engine.py`; negated statements
  ("No quotation has been prepared", "no quote yet") must not trigger. Add a unit test.
- Record the catalog-stock drift (local 0 vs Zoho 1) and latency in Beads as separate tracked items;
  no change in this stage.

## Verification

1. Focused tests per task (files above), then the repo gates:
   `uv run ruff check src/ tests/`, `uv run ruff format --check src/ tests/`, `uv run mypy src/`,
   `uv run pytest tests/ -v --tb=short` (full suite once, before delivery).
2. Offline replay of the three production conversations (`207f7c10`, `fa224cab`, `d24c5360`) through
   the local engine with recorded tool outputs: no "exact … not confirmed" on named/selected items,
   images queued for both offered workstations, no re-list after selection, CH 616 stays resolved.
3. Stage close: `scripts/orchestration/run_stage_closeout.py --stage <id> --level slice_acceptance`.
4. After owner-authorized deploy: Angela reruns routes A and B on test0665 (reset first); read-only log
   check for `Suppressed … not referenced` counts and absence of the caveat.
