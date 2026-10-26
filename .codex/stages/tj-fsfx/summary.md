# Stage tj-fsfx — Expand Viktor's client portal guide with all 8 help/training entrypoints and full recent delivery changelog

- Branch `codex/tj-fsfx-viktor-portal-guide`, worktree `.worktrees/tj-fsfx-viktor-portal-guide`, base `main` `f2d040d`.
- Docs-only slice (`docs/reports/2026-10-24-treejar-admin-dashboard-guide.html`, `.codex/`); runtime code and pinned RAG files untouched.

## Delivered
- **Section 02 expanded to all 8 in-dashboard help & training mechanisms**:
  1. Automatic 14-step first-visit tour (browser-local per device).
  2. Header `Интерактивный тур` 1-click replay button (`RU | EN`, Light/Dark).
  3. Three 4-step role mini-tours (`daily_ops`, `teach_bot`, `quality_settings`).
  4. Shareable auto-launch deep links (`?tour=1`, `?tour=daily_ops`, `?tour=teach_bot`, `?tour=quality_settings`, `?view=guide`) preserved across `/admin/login`.
  5. Instant `?` popover tooltips on KPIs, charts, filters, editors, and AI QA settings.
  6. Collapsible `i` «О разделе» banner at the top of every workspace showing purpose and live WhatsApp impact.
  7. Built-in `Справка и инструкции` center (pipeline strip, `/dashboard/` vs `/admin/`, 9 playbooks with 1-click jumps, section map, 5-group glossary, FAQ, live header search).
  8. Safe pre-flight sandboxes (`Предпросмотр` in KB, `Песочница правил` in Bot Rules, and `Приёмка (Self-Test)` / `/client-self-test`).
- **Section 06 added at the bottom («Также за последнее время нами для вас было выполнено следующее»)**:
  - Structured 22-item executive changelog across 4 areas: (1) Dashboard UX overhaul, Light/Dark themes, `RU | EN` bilingual UI, Month default period & persistence, executive charts & exact drilldowns, global search/refresh; (2) Passwordless Telegram `/admin` login, deep-link login redirects, header session/logout menu & per-employee `telegram:ID` audit log; (3) Two-column WhatsApp chat center with voice transcripts, editable CRM drawer + `RESET` guard, 3-tab Queues & Quality, canonical KB/Rules templates with safe diff restore, USD AI QA budgets, Zoho stock freshness & System Health; (4) Noor WhatsApp sales upgrades (5% VAT/package math, finish-matched photos & `treejartrading.ae` links, B2B handoff routing, requirement/hold retention, fresh pre-quote Zoho stock re-check, and Wazzup webhook drift guard).
- **Portal publication**:
  - Linted (`0 ошибок, 0 предупреждений`), verified across 6 viewports × themes (`400/800/1440` × `dark/light`), and republished in place as **version 3** at `https://aidevteam.ru/a/GaZJfnrjnN5VKtU2wLJdu1nFlqJq3xYO`.
