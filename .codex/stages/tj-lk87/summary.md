# Stage tj-lk87 — Admin dashboard interactive onboarding tour, Help & Guide view, and client manual

- Branch `codex/tj-lk87-admin-onboarding`, worktree `.worktrees/tj-lk87-admin-onboarding`,
  base `main` `d93cfeb`.
- Pinned RAG files (`src/models/product.py`, `src/rag/embeddings.py`,
  `src/rag/pipeline.py`, `src/schemas/product.py`) unchanged vs `main`.

## Delivered
- **Interactive Product Tour (`driver.js@1.10.2`)**:
  - `frontend/admin/src/components/OnboardingTour.tsx` (`useOnboardingTour`, `TOUR_SEEN_STORAGE_KEY = 'treejar_admin_tour_seen_v1'`, `resolveTourTrackParam`).
  - Auto-launches the 10-step full walkthrough on first browser visit or via `?tour=1` / `?tour=<track>`, with cross-view spotlight navigation and Light/Dark `.noor-tour-popover` styling in `frontend/admin/src/index.css`.
  - Header 1-click replay button (`[data-tour-trigger]`) and 3 focused 4-step role mini-tours (`daily_ops`, `teach_bot`, `quality_settings`).
- **Built-in Help & Guide Section (`?view=guide` / `?view=help` / `?view=docs`)**:
  - `frontend/admin/src/views/GuideView.tsx` + `frontend/admin/src/data/adminGuideData.ts` + 39 bilingual `RU | EN` keys in `frontend/admin/src/i18n.tsx`.
  - Accessible from the sidebar footer (`[data-nav-item="guide"]`) and top header (`[data-header-guide-btn]`), searchable via the header search box, with interactive tour launchpad, real-time pipeline strip, `/dashboard/` vs `/admin/` comparison, and 4 tabs (`playbooks`, `sections`, `glossary`, `faq`) with 1-click deep-link buttons.
- **Standalone Client Manual on AiDevTeam Portal**:
  - `docs/reports/2026-10-24-treejar-admin-dashboard-guide.html` (`0 ошибок, 0 предупреждений` on `artifact.sh lint`; 6/6 viewport × theme checks passed on `artifact.sh shots`).
  - Published under `--project treejar --label "Виктор"`: `https://aidevteam.ru/a/GaZJfnrjnN5VKtU2wLJdu1nFlqJq3xYO` (pending owner review before sending; `/dashboard/` code awaits owner push/deploy authorization).

## Verification
- `npm --prefix frontend/admin run lint` (`tsc --noEmit`): passed.
- `npm --prefix frontend/admin test`: 14/14 frontend regression scripts passed (including new `onboarding_guide_regression.mjs`).
- `npm --prefix frontend/admin run build`: passed (`vite build`).
- `uv run ruff check tests/test_admin_dashboard_frontend.py` & `ruff format --check`: passed.
- `uv run pytest tests/test_admin_dashboard_frontend.py -v --tb=short`: 16/16 passed.
- Live headless Chromium verification against `vite preview`: verified first-visit auto-welcome popover, cross-view spotlight transitions, Light/Dark `GuideView`, and EN mini-tour spotlight.
- `docs-reviewed: updated - added stage summary, handoff entry, and client portal guide; documentation-decision: driver.js@1.10.2 verified against installed package typings and official driverjs.com docs`.
- `graph-reviewed: no-change-needed - frontend/admin SPA UI slice; no backend module graph changes`.
