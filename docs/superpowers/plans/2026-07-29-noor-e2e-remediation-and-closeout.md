# Noor E2E Remediation and Closeout Plan

**Goal:** Close `tj-ee5f.1` and epic `tj-ee5f` through one release-level stage
without changing the frozen `AC-01..AC-30` scope.

**Source evidence:** `docs/client/noor-live-sales-tool-e2e-2026-07-28.md`

## Streams

1. **Production trust (`tj-ee5f.5`)**
   - Add permit-bound real transports, producers, collectors, readbacks, and
     runnable preflight/execute-resume/finalize paths.
   - Derive duration, cost, audit identity, and side-effect reconciliation from
     protected production sources.
2. **Dialogue and quotation (`tj-ee5f.6-.9`)**
   - Preserve typed pending intent across name capture.
   - Correct EN/AR catalog and no-match routing.
   - Introduce explicit quote phases and interruption/no-quote precedence.
   - Correct exact-SKU behavior, customer parsing, Zoho payloads,
     idempotency, order/PDF delivery, and readback.
3. **Voice (`tj-ee5f.10`)**
   - Move to dedicated STT, detect actual media format, preserve usage/cost,
     and deduplicate by inbound message identity.
4. **Integration and evidence (`tj-ee5f.1`)**
   - Integrate the three streams, update Beads and the scope ledger, run one
     final acceptance set, deliver, execute production scenarios, report, and
     close out the stage.

All streams share one acceptance owner, rollback boundary, production target,
and release proof. They remain parallel implementation streams inside one
stage, not separate acceptance stages.

## Work order

1. Create the remediation spec, this plan, compact orchestrator prompt, and
   Beads blocking edges.
2. For every observable change, use a focused red-green TDD loop. Do not run
   broad intermediate suites.
3. Integrate stream commits into the owning worktree; resolve shared contracts
   centrally and preserve user-owned files.
4. Run one risk-selected independent review, correct the combined delta, then
   run the release commands from `.codex/orchestrator.toml` and process
   verification.
5. Before any remote/live action, check the current authority boundary. With
   authority, fresh-fetch `main`, perform a safe non-force delivery, canonical
   deploy, and exact readback. Roll back to the prior exact release on a health
   or core-smoke regression without altering failed evidence.
6. Run the existing application-native scenarios sequentially. Ask the owner
   once for provider-originated EN/AR/voice messages when that canary is ready.
7. Reconcile test-only Wazzup, Zoho/CRM, quotation/PDF, callback, and escalation
   effects. A missing or unknown terminal state blocks completion.
8. Update the redacted Russian report, Beads, stage ledger, summary, and
   handoff. Render and inspect PDF only after Markdown content acceptance.
9. Run `scripts/orchestration/run_stage_closeout.py --stage tj-ee5f` only after
   every blocker and side effect is terminal.

## Focused regression targets

- Name gate: EN, AR, name-only follow-up, inline name/company, and pending
  discovery/exact-SKU intent.
- Catalog: Arabic private workstation, honest no-match, true unsupported fact,
  and no unnecessary escalation.
- Quote state: discovery, objection, correction, delivery interruption,
  exact-SKU/no-quote, CRM opportunity without quotation, and idempotent retry.
- Zoho: one-line labeled fields, company digits, full address, duplicate
  contact, non-duplicate HTTP 400, exact line reconciliation, and PDF delivery.
- Voice: valid FLAC and Wazzup OGG/Opus, mismatched/unknown media, same-message
  retry, and distinct-message fallbacks.
- Trust boundary: authorization drift, altered/reordered/empty transcripts,
  zero-turn typed blockers, quota/permit reuse, missing readback, and
  nonterminal/unlisted side effects.

## Final verification

Run once after the combined implementation is green:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/
uv run pytest tests/ -v --tb=short
scripts/orchestration/run_process_verification.sh
```

Production acceptance requires:

- at least ten completed text scenarios and provider EN/AR/voice canaries;
- each text score `>=20/30`, mean `>=24/30`;
- no functional `FAIL`, unresolved P0/P1, or zero on an applicable critical
  sales rule;
- verified quotation tool trace, exact line totals, delivered PDF, readback,
  and terminal cleanup;
- protected raw evidence outside Git and a secret-free tracked report.

If provider-originated messages cannot be supplied, record that criterion as
`BLOCKED` and leave the epic open while completing every independent result.
