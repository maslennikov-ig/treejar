# Stage tj-ierv — Admin dashboard polish (owner-authorized delivery)

- Branch `codex/tj-ierv-admin-dashboard`, worktree `.worktrees/tj-ierv-admin-dashboard`,
  base `origin/main` 2629bbb. Spec `docs/specs/admin-dashboard-polish/spec.md`,
  plan `docs/plans/2026-10-23-admin-dashboard-polish-plan.md`.
- Pinned RAG files (`src/models/product.py`, `src/rag/embeddings.py`,
  `src/rag/pipeline.py`, `src/schemas/product.py`) unchanged vs origin/main.

## Delivered
- tj-ierv.1: `src/services/canonical_admin_seed.py` (7 policy articles + 17
  verbatim `docs/faq.md` answers; 8 Noor operating rules), idempotent upsert
  with embeddings; `POST /api/v1/admin/{knowledge-base,bot-rules}/sync-canonical`
  (+ `/seed-defaults` spec alias); archived-status filter fix; synthetic
  `QA disposable/QA sentinel` rows hidden unless the search mentions `qa`.
  Sync is button-only (no auto-seed): syncing rules changes live prompts.
- tj-ierv.2: default criteria per scope (backfilled on read, overrides kept);
  gate carries criteria/retry/alert/budget; manual Bot QA / Manager QA /
  manager-review endpoint pass model, transcript mode, telemetry, criteria,
  retry, alert; daily call + `daily_budget_cents` enforced (Redis spend hash);
  `usage_today` in the controls response; `run_agent_with_safety` gained a
  capped (30 s) retry backoff.
- tj-ierv.3/.4/.5 (frontend): HelpTooltip/SectionInfoBanner on all 11 views,
  wired header search, reset preview card, RU|EN i18n (`treejar_admin_lang`,
  default ru), donut fix, EscalationReasons + FunnelEfficiency charts;
  backend `escalation_by_reason`, `sales_stage_distribution`.
- tj-nm8c (follow-up UI/UX fixes): Recharts tooltip `wrapperStyle={{ zIndex: 50 }}`
  and `SegmentPieChart` DOM stacking so donut center totals never bleed through
  hover tooltips; `HelpTooltip` portaled to `document.body` (`zIndex: 9999`,
  `opacity: 1`); `CanonicalSyncButton` persists in-flight/last sync state across
  tab switches, includes a `HelpTooltip` explaining sync semantics, and
  `KnowledgeBaseView`/`BotRulesView` auto-seed once per session on empty initial load.

## Deviations from spec/plan (resolved against repo facts)
- KB content: no free-assembly, 7-day return, warranty-term, working-hours or
  payment-method claims — no owner-approved source exists; FAQ 12/13/17 are
  manager-controlled (`src/llm/company_faq.py`). Articles defer those terms to
  the manager. Owner facts needed before adding them (explicit defer).
- Rule priorities use the runtime convention (lower number = applied first);
  canonical identity lives in `metadata.canonical_key` (no schema migration).
- Red-flag criteria keys equal the real flag codes; Manager QA has a fifth
  group `professional_tone` (rule 3).

## Verification
See the root acceptance results in the epic Beads notes.
