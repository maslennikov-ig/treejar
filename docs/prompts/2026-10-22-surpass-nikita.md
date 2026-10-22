# Executor Handoff: `tj-asty` (Surpass «Nikita» Bot Across All Criteria)

Target: `/home/me/code/treejar`, Beads epic `tj-asty` (`tj-asty.1` .. `tj-asty.5`); implement in a dedicated `codex/tj-asty-surpass-nikita` worktree or branch based on current `main` (while preserving untracked reports/spec files in the primary checkout).
Audience: a coding executor agent in this repository; native model/effort controls remain unchanged. Do not create a new chat or goal automatically.

## Goal

Implement and immediately verify the 5 cohesive improvements in `tj-asty` (`tj-asty.1` through `tj-asty.5`) so Noor (`openai/gpt-6-luna`) strictly outperforms the client's current bot «Nikita» (`+971 52 320 9235`) across every single dimension measured in the 2026-10-22 shadow benchmark (`docs/reports/2026-10-22-nikita-vs-noor-benchmark.md`):
1. Grounded turnkey package math (`Qty × Unit Price = Subtotal` + `Workstation + Chairs = Package Total`) and explicit 5% UAE VAT (`excl. 5% VAT` / `incl. 5% VAT`) with accurate budget-cap comparisons (`tj-asty.1`);
2. Treejar's 3 B2B manager handoff routes (`wholesale_or_bulk_project` for 20+ units/bulk terms, `custom_made_to_order` for bespoke dimensions/power fabrication, and `specialist_out_of_catalog_scope` for non-office equipment like lab fume hoods) with 2–3 in-stock standard catalog reference options, WhatsApp product photos, and a 1-sentence brief-qualification question (`tj-asty.2`);
3. Canonical product page URLs (`https://treejartrading.ae/product/<slug>`) surfaced alongside native WhatsApp product photos while keeping raw R2 asset URLs forbidden in text (`tj-asty.3`);
4. Configurable first-turn manager grace window (`first_turn_manager_grace_seconds`, default `0` for instant 20s response; optional weekday grace window on Turn 1 only, fast 5s batching on Turn 2+, and automatic manager takeover when `authorType == "manager"` replies) (`tj-asty.4`);
5. Full 4-scenario benchmark replay suite (`A`, `B`, `C`, `D`) in `scripts/scenario_replay.py` and updated evidence in `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md` (`tj-asty.5`).

## Context

Read `AGENTS.md`, `.codex/orchestrator.toml`, and `.codex/handoff.md` first, then read:
- `/home/me/code/treejar/docs/specs/surpass-nikita/spec.md` (canonical specification and acceptance criteria `AC01`–`AC10`);
- `/home/me/code/treejar/docs/plans/2026-10-22-surpass-nikita-plan.md` (execution order);
- `/home/me/code/treejar/docs/reports/2026-10-22-nikita-vs-noor-benchmark.md` (head-to-head shadow benchmark report);
- `/home/me/code/treejar/docs/client-answers/responses-2026-10-22.md` (Victor's workflow requirements);
- Run `export PATH="$HOME/.local/bin:$PATH"; bd show tj-asty` and `bd children tj-asty`.

## Success Criteria

- Deliver `AC01`–`AC10` from `docs/specs/surpass-nikita/spec.md`:
  - **AC01–AC03 (`tj-asty.1`):** `src/llm/money.py`, `src/dialogue/claim_contract.py`, `src/llm/catalog_planning.py`, and `src/llm/engine.py` expose `(excl. 5% VAT; X.XX AED incl. 5% VAT)` unit prices, deterministic multi-unit line subtotals, and multi-family turnkey package totals (`Workstation + N × Chairs`), allowlist 5% VAT (`× 1.05` and `× 0.05`) in `_restatable_numbers`, and accurately verify `3 × LUMA 9719-4` (`5,649.00 AED` excl. VAT / `5,931.45 AED` incl. 5% VAT) as fitting within a `6,000 AED` budget.
  - **AC04–AC06 (`tj-asty.2`):** `src/llm/escalation_policy.py`, `src/llm/escalation_tools.py`, `src/dialogue/claim_contract.py`, `src/llm/prompts.py`, and `src/llm/engine.py` authorize `escalate_to_manager` for `wholesale_or_bulk_project` (20+ units or bulk project discount), `custom_made_to_order` (e.g. 4.5m walnut table with built-in power modules), and `specialist_out_of_catalog_scope` (e.g. laboratory fume hoods), never escalating ordinary office furniture searches or `"No quotation yet"`, and presenting 2–3 in-stock catalog reference options + photos + a 1-sentence brief question on wholesale/custom handoffs.
  - **AC07 (`tj-asty.3`):** `product_canonical_url(product)` in `src/models/product.py` resolves `https://treejartrading.ae/product/<slug>` and `search_products` includes `Product page: https://treejartrading.ae/product/<slug>` while keeping native WhatsApp product photos active and raw R2 storage URLs forbidden in text.
  - **AC08 (`tj-asty.4`):** `src/services/inbound_batch.py`, `src/api/v1/webhook.py`, and `src/services/chat.py` implement `first_turn_manager_grace_seconds` (default `0`) and `first_turn_grace_weekdays_only` (default `"true"`) on Turn 1 only, keeping Turn 2+ at 5s and automatically yielding (`escalation_status = "pending"`) if `authorType == "manager"` sends a message.
  - **AC09–AC10 (`tj-asty.5`):** Add `tests/fixtures/scenarios/c_layan_arabic_6p_wholesale.json` and `tests/fixtures/scenarios/d_rami_fume_hood_luma_budget.json`, update `scripts/scenario_replay/`, pass `uv run python scripts/scenario_replay.py --dry` across all scenarios (and `--live --max-cost-usd 0.08 --receipt docs/reports/2026-10-22-surpass-nikita-replay.json` if `OPENROUTER_API_KEY` is configured in `.env`), update `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md`, and pass `uv run ruff check src/ tests/ scripts/`, `uv run ruff format --check src/ tests/ scripts/`, `uv run mypy src/`, and focused `pytest` suites.

## Constraints

- Write zone: section 4 of `docs/specs/surpass-nikita/spec.md`.
- Preserve all existing untracked files in `docs/reports/`, `docs/client-answers/`, `docs/specs/`, `docs/plans/`, and `docs/prompts/`.
- Preserve all existing Noor capabilities (15–40s response speed, native WhatsApp product photos, Zoho live stock snapshot, Zoho PDF quotations, zero attribute hallucinations, EN/AR name recognition, and `test0665` isolation).
- Local edits, tests, scenario replays (including bounded `--live` replay up to `$0.08` if `.env` has `OPENROUTER_API_KEY`), Beads status updates, and local commits are authorized.
- Do **not** deploy to production (`https://noor.starec.ai`), mutate production `.env`, or send live Wazzup WhatsApp messages without separate post-review owner approval.

## Output

- Commit locally on your implementation branch/worktree (or current checkout if working in-place with untracked docs preserved), update Beads task statuses (`tj-asty.1` .. `tj-asty.5` and `tj-asty`), export `.beads/issues.jsonl`, and update `docs/reports/2026-10-22-nikita-vs-noor-benchmark.md`.
- Final response in Russian: summarize what was implemented for `tj-asty.1`–`tj-asty.5`, exact verification commands and scenario replay results, commit SHA, and confirm that the workspace is ready for our final review and client presentation.

## Stop

Stop only after completing the full local implementation, unit tests, scenario replay verification (`AC01`–`AC10`), and benchmark report update, or if blocked by a genuine external authority boundary. Do not stop at a plan.
