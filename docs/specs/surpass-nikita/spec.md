# Specification & Implementation Plan: Surpass «Nikita» Bot Across All Sales, Pricing, VAT, B2B Handoff, and Latency Criteria (`tj-asty`)

- **Date:** 2026-10-22
- **Beads Epic:** `tj-asty` (`tj-asty.1` .. `tj-asty.5`)
- **Benchmark Evidence:** `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md` and `docs/reports/2026-10-22-nikita-shadow-test-raw.jsonl`
- **Client Workflow Requirements:** `docs/client-answers/responses-2026-10-22.md`

---

## 1. Problem Statement & Empirical Baseline

On 2026-10-22 we ran a blind head-to-head shadow benchmark of the client's current WhatsApp AI bot **«Nikita»** (`+971 52 320 9235`, `audit.treejartrading.ae`) against **Noor** (`https://noor.starec.ai`, `openai/gpt-6-luna`) across 4 realistic multi-turn B2B buyer scenarios (`A`: Nadia 4-person Dubai office `LUMA 9719-4` vs `NOVO 2400`; `B`: Aisha `CH 616 NEW black` + `CH 460 black`; `C`: Layan Arabic 6-person office budget 10,000 AED + 55-workstation & 4.5m custom walnut table escalation; `D`: Rami lab fume hoods out-of-scope + 3×`LUMA 9719-4` delivery/assembly in Dubai within 6,000 AED budget).

### Where Noor Already Beats Nikita Decisively (Must Preserve)
1. **Response Speed:** 15–40s per turn vs Nikita's 7m 31s first reply + 5m 18s per subsequent turn.
2. **Native WhatsApp Product Photos (`type: image`):** Noor sends real product photos in WhatsApp; Nikita sends `0` photos.
3. **Zero Attribute Hallucinations:** Noor accurately reports `NOVO 2400` grey fabric divider panels and `LUMA 9719-4` included screen dividers + four 3-drawer mobile pedestals; Nikita hallucinated that `NOVO 2400` has "zero separation" and falsely claimed `LUMA 9719-4` dividers are a paid add-on without pedestals.
4. **Live Zoho Stock & PDF Quotations:** Noor reads authoritative Zoho stock (`CH 616 NEW black` = 1 unit) and generates Zoho PDF quotes; Nikita confused `CH 616 NEW black` with `CH 616 black` (claiming 3 units) and cannot generate PDF quotes.
5. **Multilingual Name & Context Extraction:** Noor recognizes `"Hi, I'm Nadia"` and `"مرحباً، اسمي ليان"` on Turn 1; Nikita failed both.

### Where Nikita Showed Strengths That Noor Must Surpass (`tj-asty.1` – `tj-asty.5`)
1. **Turnkey Bundle & Line Arithmetic (`tj-asty.1`):**
   - When a customer asks for $K$ units of a product (e.g. `3 × LUMA 9719-4`) or a complete $N$-person office setup (workstations + chairs), Nikita writes out explicit line arithmetic (`Qty × Unit Price = Subtotal`) and package totals (`Workstation Subtotal + Chairs Subtotal = Package Total`) compared against the customer's budget.
   - Noor currently lists unit prices (`1,883.00 AED`, `2,598.00 AED`) and relies on the LLM to compute arithmetic, or withholds ungrounded derived numbers under the claim contract.
2. **Explicit 5% UAE VAT Transparency & Accurate Budget Comparison (`tj-asty.1`):**
   - Treejar catalog prices exclude 5% UAE VAT (`priceExclVAT`). Nikita labels prices `excl. 5% VAT` and computes the VAT-inclusive total (`+ 5% VAT (AED 282.45) = AED 5,931.45`) when checking a customer's budget (though Nikita then failed elementary math by claiming `5,931 AED` is *"above your 6,000 AED budget"*).
   - Noor must state `(excl. 5% VAT)`, surface deterministic excl./incl. 5% VAT totals in tool evidence, allowlist `× 1.05` / `× 0.05` in `src/dialogue/claim_contract.py`, and compare both excl. and incl. VAT totals against `budget_cap` with 100% mathematical accuracy (`5,931.45 AED <= 6,000.00 AED`).
3. **Treejar's 3 B2B Manager Handoff Routes with In-Stock Reference Options + Mini-Brief (`tj-asty.2`):**
   - Victor explicitly specified Nikita's mandatory handoff rules on `+971 52 320 9235`:
     > *"передает клиента менеджеру - оптовый заказ, товары на заказ, не уверен в ответе."*
   - Currently `src/llm/escalation_policy.py` (`critical_escalation_decision`) blocks `escalate_to_manager` for wholesale/bulk orders, custom-made dimensions, and out-of-catalog specialist equipment.
   - Furthermore, when Nikita escalates a wholesale/custom request (e.g. 55 workstations + 4.5m custom walnut boardroom table), it **also** gives 2–3 in-stock catalog reference options with prices and asks 1–2 brief-qualification questions (company name, timeline, Dubai delivery) so the manager receives a warm brief. Noor must do all of this **plus** attach the WhatsApp photos of those reference options.
4. **Canonical Product Page Links (`treejartrading.ae/product/<slug>`) Alongside WhatsApp Photos (`tj-asty.3`):**
   - Nikita includes clickable product page links (`https://treejartrading.ae/product/<slug>`) so B2B buyers can open the web spec sheet on desktop. Noor already stores `attributes.treejar_slug` / `attributes.treejar_url` in PostgreSQL (`src/integrations/inventory/sync.py:134-135`), so Noor can provide **both** the native WhatsApp photo and the canonical product URL (`https://treejartrading.ae/product/<slug>`), while still forbidding raw R2 image URLs (`pub-...r2.dev`) in text.
5. **Configurable First-Turn Manager Grace Window (`instant` vs `weekday_grace_window`) (`tj-asty.4`):**
   - Treejar uses a 15-minute weekday grace window on `+971 52 320 9235` so a live manager can answer a brand-new chat first on weekdays, while the bot answers immediately if no manager steps in (or on weekends). Nikita's implementation is broken because (a) after waiting 15 minutes it sends a dumb template ignoring the customer's question, and (b) it delays every subsequent turn by 5.3 minutes.
   - Noor will support an optional `SystemConfig` setting (`first_turn_manager_grace_seconds`, default `0` for instant 20s response, configurable in `/dashboard/` for weekdays) that applies **only** to Turn 1 of a brand-new conversation, automatically yields (`escalation_status = "pending"`) if `authorType == "manager"` replies during the window, and keeps all subsequent turns at the fast 5-second batch window.

---

## 2. Acceptance Criteria (`AC01` – `AC10`)

- **AC01 (Explicit VAT & Line Math in Tool Evidence):** `search_products` and `get_stock` include `(excl. 5% VAT; {incl_vat:.2f} AED incl. 5% VAT)` on verified unit prices. When the customer specifies an explicit item quantity $K \ge 1$ (e.g. `3 workstations`, `1 chair CH 616 NEW black and 3 chairs CH 460 black`) or a team headcount `requested_seats`, the tool output includes a deterministic `Verified line & package math` section with exact `Qty × Unit Price = Subtotal (excl. 5% VAT)` and `+ 5% VAT = Total (incl. 5% VAT)`.
- **AC02 (Turnkey Office Package Calculation):** When a customer asks to furnish an office/team for $N$ people (e.g. 4 or 6 people) and both `workspace` (workstations/desks) and `seating` (chairs) candidates are retrieved in the turn (or across the active turn's searches), Noor computes and exposes a grounded **Turnkey Package Total** (`Workstation configuration subtotal + N × Chair unit price = Package subtotal excl. 5% VAT / Package total incl. 5% VAT`) and compares it against the customer's `budget_cap` if present.
- **AC03 (Claim Contract Grounding for VAT & Multi-Line Sums):** `src/dialogue/claim_contract.py` (`_restatable_numbers` and `row_from_catalog_product`) treats 5% VAT derivations (`round(x * 1.05, 2)`, `round(x * 0.05, 2)`) and multi-item package subtotals/totals as grounded restatable numbers. In Scenario D Turn 2 (`3 × LUMA 9719-4` at `1,883.00 AED` under a `6,000 AED` budget), Noor states `3 × 1,883.00 AED = 5,649.00 AED excl. 5% VAT` and `5,931.45 AED incl. 5% VAT`, and explicitly confirms that **both** figures fit within the `6,000 AED` budget (`68.55 AED` under budget even after 5% VAT), plus states the verified Dubai delivery policy (`free in Dubai on orders >= 2,000 AED`, `130 AED` under `2,000 AED`) and free professional assembly from `docs/faq.md` Q9–Q10.
- **AC04 (Wholesale / Bulk 20+ Handoff Route):** `critical_escalation_decision` (`src/llm/escalation_policy.py`) authorizes `escalate_to_manager` with `reason_Bucket="wholesale_or_bulk_project"` when the customer requests a bulk/wholesale order ($N \ge 20$ workstations/chairs/seats or explicit wholesale project discount/tender pricing on a multi-unit commercial order).
- **AC05 (Custom Made-to-Order & Specialist Out-of-Catalog Handoff Routes):** `critical_escalation_decision` authorizes `escalate_to_manager` when the customer requests:
  - `custom_made_to_order`: bespoke/custom dimensions, custom materials, or built-in electrical/power fabrication not in the standard catalog (e.g., `"custom 4.5-meter solid walnut boardroom table with built-in power modules"`, `"تفصيل طاولة اجتماعات خاصة بطول 4.5 متر من خشب الجوز مع وحدات كهرباء مدمجة"`);
  - `specialist_out_of_catalog_scope`: non-office specialist/industrial equipment outside Treejar's catalog (e.g., `"laboratory fume hoods"`, `"medical autoclaves"`), while **never** escalating ordinary office furniture queries, generic no-match searches, or `"No quotation yet"` restrictions.
- **AC06 (Consultative Handoff with In-Stock Reference Options + Photos + Mini-Brief):** When a wholesale or custom-made request triggers handoff (such as Scenario C Turn 2), Noor:
  1. Calls `search_products` for the closest standard in-stock catalog items (e.g., standard workstations and `SKYLAND LUMA 9785` / `NOVO 3200` meeting tables) so the customer receives 2–3 immediate reference options with verified catalog prices **and native WhatsApp photos**;
  2. Calls `escalate_to_manager` to alert the manager in Telegram;
  3. Replies in the customer's language confirming the manager handoff, presenting the in-stock reference options, and asking one compact brief-qualification question (company name, target delivery timeline, or Dubai location).
- **AC07 (Canonical Product Page URLs Alongside WhatsApp Photos):** `product_canonical_url(product)` resolves `https://treejartrading.ae/product/<slug>` from `Product.attributes` (`treejar_url` / `treejar_slug`) or a deterministic slug fallback for snapshot fixtures. `search_products` exposes `Product page: https://treejartrading.ae/product/<slug>` in tool output and `claim_rows`, allowing the assistant to include clean `https://treejartrading.ae/product/<slug>` links in text while keeping native WhatsApp image delivery active and raw R2 storage URLs (`pub-...r2.dev`) forbidden in text.
- **AC08 (Configurable First-Turn Manager Grace Window & Manager Takeover):**
  - `src/services/inbound_batch.py` / `src/api/v1/webhook.py` / `src/services/chat.py` support `SystemConfig` keys `first_turn_manager_grace_seconds` (int, default `0`, max `1800`) and `first_turn_grace_weekdays_only` (bool, default `true`, UAE `Asia/Dubai` Mon–Fri).
  - When `first_turn_manager_grace_seconds == 0` (default), Turn 1 uses the standard `5`-second batch defer.
  - When `first_turn_manager_grace_seconds > 0` on an applicable day, **only** the first inbound client batch of a conversation with no prior assistant/manager messages is deferred by `first_turn_manager_grace_seconds`; all subsequent turns use `5` seconds.
  - When a Wazzup webhook arrives with `authorType == "manager"`, `src/services/chat.py` / `src/api/v1/webhook.py` records active manager takeover (`escalation_status = "pending"`) so any pending or future bot batch yields to the human manager without sending a duplicate bot reply.
- **AC09 (Full 4-Scenario Benchmark Replay Suite `A`, `B`, `C`, `D`):**
  - `tests/fixtures/scenarios/c_layan_arabic_6p_wholesale.json` and `tests/fixtures/scenarios/d_rami_fume_hood_luma_budget.json` are added alongside existing `a_207f7c10_luma_novo.json` and `b_d24c5360_ch616_ch460.json` (plus `c_fa224cab_luma_quote_consent.json`).
  - `scripts/scenario_replay.py --dry` passes all scenario checks across all scenarios.
  - If `OPENROUTER_API_KEY` is available and live replay is run within `--max-cost-usd 0.08`, `scripts/scenario_replay.py --live` produces a receipt at `docs/reports/2026-10-22-surpass-nikita-replay.json` with all checks passing.
- **AC10 (Updated Benchmark Report & Clean Repo Gates):**
  - `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md` is updated with the verified post-implementation capabilities and replay evidence showing Noor winning 100% of criteria.
  - `uv run ruff check src/ tests/ scripts/`, `uv run ruff format --check src/ tests/ scripts/`, `uv run mypy src/`, and focused pytest suites pass with zero errors.

---

## 3. Detailed Technical Design by Task

### Task 1 (`tj-asty.1`): Grounded Turnkey Package Math & Explicit 5% UAE VAT Transparency

#### Files to Modify
- `src/llm/money.py`
- `src/dialogue/claim_contract.py`
- `src/llm/catalog_planning.py`
- `src/llm/engine.py`
- `tests/test_claim_contract.py`
- `tests/test_llm_engine.py`

#### Design Details
1. **VAT & Line Math Helper in `src/llm/money.py`:**
   - Add deterministic helpers:
     ```python
     UAE_VAT_RATE = Decimal("0.05")
     UAE_VAT_MULTIPLIER = Decimal("1.05")

     def amount_with_uae_vat(amount: float | Decimal) -> tuple[float, float, float]:
         """Return (excl_vat, vat_amount, incl_vat) rounded to 2 decimal places."""
     ```
2. **Claim Contract VAT & Multi-Step Arithmetic Support in `src/dialogue/claim_contract.py`:**
   - In `_restatable_numbers(operation: str, inputs: tuple[ClaimInput, ...]) -> set[float]` (lines 427–456):
     - Whenever `allowed` numbers are computed from `inputs` (including `sum`, `difference`, `product`, or `comparison`), also add the 5% VAT-inclusive (`round(val * 1.05, 2)` and `round(val * 1.05, 6)`) and 5% VAT component (`round(val * 0.05, 2)` and `round(val * 0.05, 6)`) for each input and for the operation result, plus integer-rounded equivalents if `.00` (`round(val * 1.05)` only when exact or within standard cent rounding).
     - Also support multi-line `bundle` / `turnkey` derivations where inputs carry `qty` and `unit_price` (e.g., `sum` of `product` terms or pre-computed `line_subtotal_excl_vat` / `line_total_incl_vat` fields stored on `RetrievedRow`).
   - In `row_from_catalog_product` (`src/dialogue/claim_contract.py:631`):
     - When `extras` includes `"price"` (numeric), automatically populate normalized fields on `RetrievedRow`:
       - `"price_excl_vat"`: `f"{price:.2f}"`
       - `"price_incl_vat"`: `f"{round(price * 1.05, 2):.2f}"`
       - `"vat_amount"`: `f"{round(price * 0.05, 2):.2f}"`
3. **Tool Output Enrichment in `src/llm/engine.py` (`search_products` and `get_stock`):**
   - In `search_products` (`src/llm/engine.py:9980-10090`):
     - Change `price_line` from:
       `Customer-facing catalog price: {discounted_price:.2f} {r.currency} (segment-adjusted if applicable)`
       to:
       `Customer-facing catalog price: {discounted_price:.2f} {r.currency} (excl. 5% VAT; {incl_vat:.2f} {r.currency} incl. 5% VAT; segment-adjusted if applicable)`
     - When the customer turn specifies an explicit quantity $K$ for the queried item (or `requested_seats` when the item is a single-person chair/desk or multi-person workstation where `units_needed = ceil(requested_seats / product_capacity)`):
       - Compute `line_subtotal_excl = round(units_needed * discounted_price, 2)` and `line_total_incl = round(line_subtotal_excl * 1.05, 2)`.
       - Append to `desc`:
         `Verified line math ({units_needed} unit(s) for {covered_seats} seat(s)): {units_needed} × {discounted_price:.2f} {r.currency} = {line_subtotal_excl:.2f} {r.currency} excl. 5% VAT ({line_total_incl:.2f} {r.currency} incl. 5% VAT, 5% VAT = {vat_amt:.2f} {r.currency}).`
       - If `ctx.deps.catalog_planning.budget_cap` is set, append an exact budget check line:
         - If `line_total_incl <= budget_cap`:
           `Budget check (cap {budget_cap:.2f} AED): FITS within budget both excl. VAT ({line_subtotal_excl:.2f} AED) and incl. 5% VAT ({line_total_incl:.2f} AED; {round(budget_cap - line_total_incl, 2):.2f} AED remaining after VAT).`
         - Else if `line_subtotal_excl <= budget_cap < line_total_incl`:
           `Budget check (cap {budget_cap:.2f} AED): FITS excl. 5% VAT ({line_subtotal_excl:.2f} AED) and is {round(line_total_incl - budget_cap, 2):.2f} AED above cap once 5% VAT ({line_total_incl:.2f} AED) is added.`
       - Store `line_subtotal_excl_vat` and `line_total_incl_vat` in `row_from_catalog_product(..., extras=...)` so the claim contract recognizes them immediately as `KNOWN_VALUE` on that SKU row!
     - **Multi-Family Turnkey Bundle Summary across Searches in the Same Turn:**
       - Track top verified `workspace` and `seating` candidates seen in `ctx.deps` during the turn. When a turn has `requested_seats` (e.g., 4 or 6 people) and both a `workspace` option and a `seating` option have been retrieved in the turn, append a `Verified turnkey package math ({requested_seats} seats)` block to the tool result (and register a synthetic `_BUNDLE_` or per-row `package_total_excl_vat` / `package_total_incl_vat` in `claim_rows`) showing:
         `Turnkey {requested_seats}-person package example: {ws_units} × {ws_name} ({ws_subtotal:.2f} AED) + {chair_units} × {chair_name} ({chair_subtotal:.2f} AED) = {pkg_excl:.2f} AED excl. 5% VAT ({pkg_incl:.2f} AED incl. 5% VAT)` (plus comparison against `budget_cap` when present).
   - Do the same VAT + explicit quantity math enrichment in `get_stock` (`src/llm/engine.py:10312+`) and when multiple SKUs are checked in one turn (e.g., Scenario B Turn 2: `1 × CH 616 NEW black (295.00 AED) + 3 × CH 460 black (3 × 801.00 = 2,403.00 AED) = 2,698.00 AED excl. 5% VAT (2,832.90 AED incl. 5% VAT)`).
4. **Response Contract Updates in `src/llm/catalog_planning.py` & `src/dialogue/claim_contract.py`:**
   - In `_product_search_response_contract` (`src/llm/catalog_planning.py:2064`) and `project_consultation_directive` (`src/dialogue/claim_contract.py:1101`):
     - Instruct the model to state `(excl. 5% VAT)` alongside catalog prices, and whenever the customer specifies multiple units, a multi-item selection, a team headcount package, or a budget cap, to state the verified line/package subtotal (`excl. 5% VAT`) and VAT-inclusive total (`incl. 5% VAT`) from the tool output.

---

### Task 2 (`tj-asty.2`): Treejar B2B Handoff Routes (`Wholesale 20+ Units`, `Custom Made-to-Order`, `Specialist Out-of-Catalog`) with In-Stock Reference Options + Mini-Brief

#### Files to Modify
- `src/llm/escalation_policy.py`
- `src/llm/escalation_tools.py`
- `src/dialogue/claim_contract.py`
- `src/llm/prompts.py`
- `src/llm/engine.py`
- `tests/test_escalation_policy.py`
- `tests/test_llm_engine.py`

#### Design Details
1. **Expand `critical_escalation_decision` in `src/llm/escalation_policy.py`:**
   - Preserve all existing critical triggers (`explicit_human_request`, `order_payment_or_delivery_exception`, `post_sale_defect_or_return`, `security_or_abuse`).
   - Add three narrow, high-precision B2B handoff detectors aligned with Victor's rule (`"передает клиента менеджеру - оптовый заказ, товары на заказ, не уверен в ответе"`):
     - **`wholesale_or_bulk_project` (`_WHOLESALE_PROJECT_ESCALATION_RE` + quantity check):**
       - Matches when the customer requests a large bulk/wholesale order ($N \ge 20$ units/seats/workstations/chairs via `_PROJECT_QUANTITY_RE` or Arabic equivalent `55 محطة عمل` / `55 مكتب` / `50 كرسي`) **OR** explicitly asks for a wholesale/bulk project discount, special bulk pricing, or tender/BOQ commercial offer (`wholesale discount`, `bulk discount`, `special wholesale rate`, `خصم جملة`, `سعر الجملة`, `عرض سعر خاص للكميات`).
       - *Guard:* Simple small-quantity price inquiries (e.g., 4 chairs, 2 workstations, 6-person office under 10,000 AED) do **not** match `wholesale_or_bulk_project`.
     - **`custom_made_to_order` (`_CUSTOM_MADE_TO_ORDER_RE`):**
       - Matches when the customer asks for custom manufacturing, bespoke non-catalog dimensions (e.g. `4.5m` / `4500mm` table), custom carpentry/woodwork, or built-in electrical/power module fabrication (`custom 4.5`, `custom-made`, `made to order`, `bespoke`, `custom dimensions`, `built-in power modules`, `تفصيل خاص`, `حسب الطلب`, `مقاس خاص`, `4.5 متر`, `وحدات كهرباء مدمجة`).
     - **`specialist_out_of_catalog_scope` (`_SPECIALIST_OUT_OF_CATALOG_RE`):**
       - Matches when the customer asks for specialist non-office / industrial / laboratory / medical equipment that Treejar does not carry in its office furniture catalog (e.g., `laboratory fume hood`, `fume hoods`, `chemical hood`, `biosafety cabinet`, `autoclave`, `dental chair`, `hospital bed`, `خزانة أبخرة مختبر`).
       - *Guard:* Never triggers on office furniture terms (`chair`, `desk`, `workstation`, `table`, `cabinet`, `sofa`, `pod`, `booth`, `reception`, `partition`, `divider`, `delivery`, `assembly`, `LUMA`, `NOVO`, `SKYLAND`, `CH `), unless paired with an explicit `custom_made_to_order` or `wholesale_or_bulk_project` trigger.
2. **Consultative B2B Handoff Flow (`search_products` Reference Options + `escalate_to_manager` + Mini-Brief):**
   - In `src/llm/escalation_tools.py` (`escalate_to_manager`) and `src/llm/engine.py` (turn runtime directives):
     - When `critical_escalation_decision` returns `allow_escalation=True` with `reason_bucket in {"wholesale_or_bulk_project", "custom_made_to_order"}`:
       - Inject a runtime directive `b2b_handoff_reference_directive(reason_bucket)`:
         1. Instruct the model to **both** call `search_products` (to fetch 2–3 closest standard in-stock catalog options, e.g., standard workstations or largest standard meeting tables `SKYLAND LUMA 9785` 3600mm / `NOVO 3200` 3200mm) **and** call `escalate_to_manager`.
         2. If the model calls `escalate_to_manager` on a `wholesale_or_bulk_project` or `custom_made_to_order` turn without having called `search_products` yet, `escalate_to_manager` still records the escalation cleanly, and the tool return reminds the model to include any verified catalog reference options already retrieved (or if `search_products` ran in the same turn, present those 2–3 standard in-stock options with their verified prices `excl. 5% VAT` and let their WhatsApp photos attach!).
         3. Instruct the model to close the handoff reply with a compact 1-sentence brief qualification question (asking for company name, target delivery timeline, and delivery location in Dubai/UAE) so the human manager steps into a ready brief.
       - Crucial media behavior check: ensure `_send_deferred_product_media` in `src/services/chat.py` / `src/llm/response_runtime.py` still sends deferred product photos on the turn that *creates* a `wholesale_or_bulk_project` or `custom_made_to_order` escalation if the reply references those catalog products! (Check `src/services/chat.py` to make sure product media is not suppressed on the handoff turn itself when reference options are presented.)
   - Update `src/llm/prompts.py` (`CRITICAL-ONLY ESCALATION POLICY` section) so the prompt contract matches `escalation_policy.py` (allowing `escalate_to_manager` for wholesale 20+ unit projects, custom made-to-order manufacturing, and specialist out-of-catalog equipment, while keeping ordinary no-match queries non-escalating).

---

### Task 3 (`tj-asty.3`): Verified Canonical Product Page Links (`treejartrading.ae/product/<slug>`) Alongside WhatsApp Product Photos

#### Files to Modify
- `src/models/product.py`
- `src/llm/engine.py`
- `src/dialogue/claim_contract.py`
- `tests/fixtures/catalog_snapshot_2026-09-23.json` (or fallback slug resolver in `src/models/product.py`)
- `tests/test_llm_engine.py`

#### Design Details
1. **Canonical Product URL Resolver (`product_canonical_url` in `src/models/product.py`):**
   - Inspect `product.attributes` (if `Mapping`):
     - If `attributes.get("treejar_url")` is a non-empty string, normalize `https://new.treejartrading.ae/product/...` to `https://treejartrading.ae/product/...`.
     - Else if `attributes.get("treejar_slug")` is a non-empty string, return `f"https://treejartrading.ae/product/{slug}"`.
     - Fallback for snapshot/test rows where `attributes` is `None`: derive a clean URL-safe slug from `name_en` + `sku` or provide a deterministic lookup for known catalog rows if `attributes` is populated, or generate `https://treejartrading.ae/product/{slugify(name_en)}` when `attributes` is absent so offline snapshot replays also surface canonical URLs. (Even better: let's check if live DB products have `attributes.treejar_slug` — yes, `src/integrations/inventory/sync.py:134` writes `"treejar_slug": slug` on every synced product! And for `tests/fixtures/catalog_snapshot_2026-09-23.json`, we can populate `treejar_slug` or compute the canonical slug in `product_canonical_url`.)
2. **Expose in `search_products` (`src/llm/engine.py:9996-10156`):**
   - Add `Product page: {canonical_url}` to `desc` in `search_products` and `"product_url": canonical_url` to `row_from_catalog_product(..., extras=...)`.
   - Update the `[Note: Image of this product ...]` instruction in `src/llm/engine.py:10152-10156`:
     - Change `"Do not mention or include image URLs in your response."` to:
       `"Do not include raw image file URLs (such as r2.dev links) in your response; you may include the canonical Product page link (https://treejartrading.ae/product/...) when helpful."`

---

### Task 4 (`tj-asty.4`): Configurable First-Turn Manager Grace Window (`instant` vs `weekday_grace_window`) with Automatic Manager Takeover Detection

#### Files to Modify
- `src/services/inbound_batch.py`
- `src/api/v1/webhook.py`
- `src/services/chat.py`
- `tests/test_webhook.py`
- `tests/test_services_chat_batch.py`

#### Design Details
1. **Configurable First-Turn Grace Helper in `src/services/inbound_batch.py`:**
   - Define `SystemConfig` keys:
     - `FIRST_TURN_MANAGER_GRACE_SECONDS_KEY = "first_turn_manager_grace_seconds"` (default `0`, clamped to `0..1800`).
     - `FIRST_TURN_GRACE_WEEKDAYS_ONLY_KEY = "first_turn_grace_weekdays_only"` (default `"true"`).
   - Add `async def resolve_inbound_batch_defer_seconds(db: AsyncSession, *, phone: str, now_utc: datetime | None = None) -> int`:
     - Default return is `5` (fast 5-second batching window).
     - Reads `first_turn_manager_grace_seconds` from `SystemConfig` (or returns `5` immediately if `0` or absent).
     - If `> 0`:
       - Checks `first_turn_grace_weekdays_only`: in UAE time (`ZoneInfo("Asia/Dubai")`), if today is Saturday or Sunday (`weekday() in {5, 6}`), returns `5` (instant weekend response, matching Treejar's weekend rule).
       - Checks if there is already an active `Conversation` for `phone` with at least one message (`Message`). If the conversation already has prior messages (Turn 2+), returns `5` so **subsequent turns are never delayed** (fixing Nikita's 5.3-minute per-turn lag!).
       - Only on Turn 1 of a brand-new conversation on an eligible day, returns `max(5, grace_seconds)`.
2. **Manager Intervention / Takeover Detection (`authorType == "manager"`):**
   - In `src/services/chat.py` (`process_incoming_batch`), examine what happens when a batch contains a message with `author_type == "manager"` (or when a manager has sent a message in the conversation):
     - Currently in `src/services/chat.py`, manager messages are saved with `role="manager"`.
     - Enhance manager message handling: when an inbound Wazzup message has `authorType == "manager"`, mark the conversation as having active manager participation (`conversation.escalation_status = EscalationStatus.PENDING.value` if it was `"none"`, and record `metadata_["last_manager_message_at"] = now_iso`).
     - When `process_incoming_batch` processes queued client messages, if a `role == "manager"` message was recorded at or after the client messages in the batch (or `should_pause_bot_for_escalation(conversation.escalation_status)` is True), Noor saves the client messages to the DB for transcript completeness and **skips LLM generation**, cleanly yielding the chat to the human manager who stepped in during the grace window!

---

### Task 5 (`tj-asty.5`): Head-to-Head Benchmark Replay Suite (`A`, `B`, `C`, `D`) & Comparison Report Update

#### Files to Create / Modify
- `tests/fixtures/scenarios/c_layan_arabic_6p_wholesale.json` (new)
- `tests/fixtures/scenarios/d_rami_fume_hood_luma_budget.json` (new)
- `scripts/scenario_replay/checks.py`
- `scripts/scenario_replay/fakes.py`
- `scripts/scenario_replay/llm_seam.py`
- `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md`

#### Design Details
1. **Add Scenario C (`tests/fixtures/scenarios/c_layan_arabic_6p_wholesale.json`):**
   - Exact 2 turns sent to Nikita in our shadow test:
     - Turn 1: `"مرحباً، اسمي ليان. نجهز مكتباً جديداً في دبي لـ 6 موظفين ونحتاج محطة عمل لـ 6 أشخاص مع 6 كراسي مكتبية مريحة، والميزانية الإجمالية 10,000 درهم. لا نريد عرض سعر رسمي الآن، فقط اقترحوا الخيارات المتوفرة مع الأسعار."`
     - Turn 2: `"شكراً. لدينا أيضاً مشروع لتجهيز الطابق بالكامل: نحتاج 55 محطة عمل، بالإضافة إلى تفصيل طاولة اجتماعات خاصة بطول 4.5 متر من خشب الجوز مع وحدات كهرباء مدمجة، ونريد خصم جملة خاص. كيف نرتب ذلك؟"`
   - Checks:
     - `no_structured_leak` on turns 1, 2
     - `positive_answer` on Turn 1: Arabic reply recognizes Layan (`ليان`), presents 6-person workstation (`NOVO 3600` / `2,598`) + ergonomic chairs, states turnkey package math within the `10,000` AED budget, and queues product media (`media_count >= 1`).
     - `b2b_handoff_with_references` on Turn 2: calls `escalate_to_manager` (status transitions to `pending`), calls `search_products` and presents standard in-stock reference options, and asks a brief-qualification question.
2. **Add Scenario D (`tests/fixtures/scenarios/d_rami_fume_hood_luma_budget.json`):**
   - Exact 2 turns sent to Nikita in our shadow test:
     - Turn 1: `"Hi, I'm Rami. Do you sell laboratory fume hoods? Also, if we order 3 workstations of SKYLAND LUMA 9719-4 for our office in Dubai, do you provide delivery and assembly, and how much does delivery cost?"`
     - Turn 2: `"Wait, our total budget for the 3 LUMA 9719-4 workstations is 6,000 AED. Does that fit our budget, and can you confirm how many units are currently in stock? No quotation needed yet."`
   - Checks:
     - `no_structured_leak` on turns 1, 2
     - `positive_answer` on Turn 1: states clearly that laboratory fume hoods are not in Treejar's office furniture catalog, confirms `SKYLAND LUMA 9719-4` (`1,883` AED), states Dubai delivery (`2,000` AED free threshold / `130` AED below) and free installation/assembly per `docs/faq.md` Q9–Q10.
     - `positive_answer` on Turn 2: states exact 3-unit subtotal `5,649` AED excl. 5% VAT and `5,931.45` AED incl. 5% VAT, confirms **both** fit within the `6,000` AED budget (never says above budget!), confirms stock (`30` units), and creates no quotation.
3. **Update `scripts/scenario_replay/llm_seam.py` (`StubModel`) and `scripts/scenario_replay/checks.py`:**
   - Ensure `--dry` stub mode deterministically exercises the new scenarios C and D as well as A, B, and `c_fa224cab_luma_quote_consent.json`.
   - Run `uv run python scripts/scenario_replay.py --dry` (and `--live --receipt docs/reports/2026-10-22-surpass-nikita-replay.json` if authorized/configured).
   - Update `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md` with the completed verification table showing Noor ahead of or equal to Nikita on 100% of criteria.

---

## 4. Write Zone & Safety Boundaries

- **Allowed Write Zone:**
  - `src/llm/money.py`
  - `src/dialogue/claim_contract.py`
  - `src/llm/catalog_planning.py`
  - `src/llm/engine.py`
  - `src/llm/escalation_policy.py`
  - `src/llm/escalation_tools.py`
  - `src/llm/prompts.py`
  - `src/models/product.py`
  - `src/services/inbound_batch.py`
  - `src/services/chat.py`
  - `src/api/v1/webhook.py`
  - `scripts/scenario_replay/`
  - `tests/fixtures/scenarios/`
  - `tests/test_claim_contract.py`, `tests/test_escalation_policy.py`, `tests/test_llm_engine.py`, `tests/test_webhook.py`, `tests/test_services_chat_batch.py`
  - `docs/specs/surpass-nikita/spec.md`, `docs/plans/2026-10-22-surpass-nikita-plan.md`, `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md`, `.codex/handoff.md`, `.codex/stages/`
- **Safety Boundaries:**
  - Do **not** deploy to production (`https://noor.starec.ai`) or disable `TEST_CHANNEL_RESTORE_MODE` without explicit post-verification owner approval.
  - Preserve all untracked client reports and portal responses under `docs/reports/` and `docs/client-answers/`.
  - Keep one dedicated worktree/branch (`codex/tj-asty-surpass-nikita`) for implementation if working in a separate session.
